"""Bounded local process isolation for the loopback fixture, not a deployment benchmark.

The parent retains HTTP, byte-preserving relay, ledger and record-v1 client.
Spawn (not fork) prevents either producer from inheriting the other producer's
ports, the relay, or record client. Only the station child receives private key
bytes, through multiprocessing's private bootstrap pipe; no key file is written.
"""
from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
from pathlib import Path
import signal
import tempfile
import time
from types import SimpleNamespace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from canticle import runner, wire
from canticle.daemon import Daemon, DaemonConfig
from canticle.manifest import Manifest, StationEntry
from canticle.records import MAX_LINE, RECORD_V
from canticle.station import Station, StreamConfig

from .loopback import Bounds, Fixture, Relay


STARTUP_SECONDS = 5
TERM_SECONDS = 3
KILL_SECONDS = 1
CHILD_WALL_SECONDS = 65


def _child_main(role, payload, ready):
    """Spawn target: run the actual production coroutine on a fresh event loop."""
    async def run():
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        loop.add_signal_handler(signal.SIGTERM, stop.set)
        started_ns = time.monotonic_ns()

        def announce(**details):
            ready.send(dict(pid=os.getpid(), child_started_ns=started_ns, **details))
            ready.close()

        if role == "daemon":
            cfg = DaemonConfig(**payload, log=lambda _: None)
            daemon = Daemon(cfg)
            operation = daemon.run(stop, started=lambda d: announce(
                udp_port=d.udp.getsockname()[1]))
        elif role == "station":
            sk = Ed25519PrivateKey.from_private_bytes(payload.pop("private_key"))
            grant = StationEntry("k6-fixture", wire.public_key_bytes(sk),
                                 frozenset({1}), ("chatter",))
            station = Station(sk, [StreamConfig("chatter")], epoch=1,
                              now_ms=runner.now_ms(), grant=grant)

            def station_log(message):
                # Production emits this only after start_unix_server succeeds.
                if message.startswith("control socket "):
                    announce(key_id=station.key_id.hex(), sid=station.streams["chatter"].sid)

            operation = runner.run_station(station, [("127.0.0.1", payload["relay_port"])],
                                           payload["control"], stop, log=station_log)
        else:
            raise ValueError("unknown fixture child")
        try:
            code = await asyncio.wait_for(operation, CHILD_WALL_SECONDS)
            return 0 if code is None else code
        except TimeoutError:
            return 124

    try:
        code = asyncio.run(run())
    finally:
        ready.close()
    raise SystemExit(code)


class ProcessFixture(Fixture):
    """Same offer/identity/ledger contract as Fixture, with two owned OS children.

    `children` holds active Process handles for fault-injection tests (closed on cleanup);
    reports expose only bounded JSON receipts, never payloads or key material.
    `production_tasks_alive` includes both children and the record reader; a
    sticky early-exit observation prevents an earlier delivery from masking death.
    """
    def __init__(self, bounds=Bounds()):
        super().__init__(bounds)
        self.children = {}
        self.child_receipts = {}
        self.child_failures = set()
        self.readiness = {}
        self.context = multiprocessing.get_context("spawn")

    async def _start_child(self, role, payload):
        receive, send = self.context.Pipe(duplex=False)
        child = self.context.Process(target=_child_main, args=(role, payload, send),
                                     name="canticle-fixture-" + role)
        receipt = dict(pid=None, started=False, started_ns=None, ready=False, ready_ns=None,
                       child_started_ns=None, exit_code=None, alive=False,
                       term_sent=False, kill_sent=False, reaped=False,
                       exit_observed_ns=None, handle_closed=False)
        self.children[role] = child
        self.child_receipts[role] = receipt
        self.readiness[role] = receive
        try:
            requested_ns = time.monotonic_ns()
            child.start()
            receipt.update(pid=child.pid, started=True, started_ns=requested_ns)
        except BaseException:
            receive.close()
            raise
        finally:
            send.close()
            payload.pop("private_key", None)  # spawn has serialized its private copy
        try:
            async with asyncio.timeout(STARTUP_SECONDS):
                while True:
                    if receive.poll():
                        try:
                            data = receive.recv()
                        except EOFError:
                            raise RuntimeError(role + " exited before readiness") from None
                        if not isinstance(data, dict) or data.get("pid") != child.pid:
                            raise RuntimeError(role + " invalid readiness receipt")
                        if not child.is_alive():
                            raise RuntimeError(role + " died at readiness")
                        receipt.update(ready=True, ready_ns=time.monotonic_ns(),
                                       child_started_ns=data["child_started_ns"], alive=True)
                        return data
                    if not child.is_alive():
                        raise RuntimeError(role + " exited before readiness")
                    await asyncio.sleep(.01)
        finally:
            receive.close()

    async def start(self):
        # Keep AF_UNIX paths below Linux's 108-byte limit, even with a long TMPDIR.
        self.temp = tempfile.TemporaryDirectory(prefix="canticle-k6-process-", dir="/tmp")
        self.root = Path(self.temp.name)  # TemporaryDirectory creates mode 0700.
        sk = Ed25519PrivateKey.generate()
        grant = StationEntry("k6-fixture", wire.public_key_bytes(sk), frozenset({1}), ("chatter",))
        self.manifest = Manifest([grant])
        manifest_path = self.root / "fleet.json"
        manifest_path.write_text(json.dumps(self.manifest.to_json()))
        control = str(self.root / "station.sock")
        daemon_socket = str(self.root / "run" / "daemon.sock")
        daemon = await self._start_child("daemon", dict(
            manifest=str(manifest_path), bind="127.0.0.1:0", socket_path=daemon_socket,
            state_dir=str(self.root / "state"), multicast=False,
            health_interval_ms=None, tick_ms=50))
        self.ports["daemon_udp"] = daemon["udp_port"]
        self.relay = Relay(self.ledger, self.manifest, ("127.0.0.1", self.ports["daemon_udp"]))
        self.relay_transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            lambda: self.relay, local_addr=("127.0.0.1", 0))
        self.ports["relay_udp"] = self.relay_transport.get_extra_info("sockname")[1]
        reader, self.client_writer = await asyncio.open_unix_connection(daemon_socket, limit=MAX_LINE)
        for expected in ("hello", "landing_state"):
            rec = json.loads(await reader.readline())
            if rec.get("v") != RECORD_V or rec.get("type") != expected:
                raise RuntimeError("invalid record-v1 bootstrap")
        self.record_run, self.rec_seq = rec["run"], rec["rec_seq"]
        self.task(self.read_records(reader), "record-v1-listener")
        self.control = control
        data = await self._start_child("station", dict(
            private_key=sk.private_bytes(serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw, serialization.NoEncryption()),
            control=control, relay_port=self.ports["relay_udp"]))
        if data["key_id"] != grant.key_id.hex():
            raise RuntimeError("station readiness identity mismatch")
        # Parent metadata only: production Station and private key stay in child.
        self.station = SimpleNamespace(key_id=grant.key_id,
            streams={"chatter": SimpleNamespace(sid=data["sid"])})
        del sk
        self.task(self._watch_children(), "production-process-monitor")
        self.server = await asyncio.start_server(self.http, "127.0.0.1", 0, limit=4096, backlog=4)
        self.ports["http_tcp"] = self.server.sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{self.ports['http_tcp']}"

    def _observe_children(self):
        for role, child in self.children.items():
            receipt = self.child_receipts[role]
            if not receipt["started"] or receipt["handle_closed"]:
                continue
            alive = child.is_alive()
            receipt.update(alive=alive, exit_code=child.exitcode)
            if not alive and receipt["exit_observed_ns"] is None:
                receipt["exit_observed_ns"] = time.monotonic_ns()
            if not alive and not self.stopping and role not in self.child_failures:
                self.child_failures.add(role)
                self.ledger.errors.append(role + " child exited before cleanup")
                self.changed.set()

    async def _watch_children(self):
        while not self.stopping:
            self._observe_children()
            await asyncio.sleep(.02)

    def report(self):
        self._observe_children()
        report = super().report()
        report["fixture_mode"] = "processes"
        report["process_mode"] = True
        report["parent_pid"] = os.getpid()
        report["processes"] = {k: dict(v) for k, v in self.child_receipts.items()}
        report["production_tasks_alive"] = (report["production_tasks_alive"]
            and set(self.children) == {"station", "daemon"}
            and all(r["ready"] and r["alive"] for r in self.child_receipts.values())
            and not self.child_failures)
        return report

    async def _reap_child(self, role, errors):
        child = self.children.get(role)
        if child is None:
            return
        receipt = self.child_receipts[role]
        if not receipt["started"]:
            self.readiness[role].close()
            child.close()
            receipt["handle_closed"] = True
            return
        try:
            if not child.is_alive() and receipt["ready"] and not receipt["term_sent"]:
                errors.append(role + " child exited before requested termination")
            if child.is_alive():
                receipt["term_sent"] = True
                try:
                    child.terminate()  # SIGTERM handler sets production stop Event
                except OSError as exc:
                    errors.append(role + " TERM: " + type(exc).__name__)
                until = time.monotonic() + TERM_SECONDS
                while child.is_alive() and time.monotonic() < until:
                    await asyncio.sleep(.01)
            if child.is_alive():
                receipt["kill_sent"] = True
                try:
                    child.kill()
                except OSError as exc:
                    errors.append(role + " KILL: " + type(exc).__name__)
                until = time.monotonic() + KILL_SECONDS
                while child.is_alive() and time.monotonic() < until:
                    await asyncio.sleep(.01)
            # Nonblocking join after observed death: no unbounded event-loop wait.
            child.join(timeout=0)
            receipt.update(alive=child.is_alive(), exit_code=child.exitcode,
                           reaped=not child.is_alive() and child.exitcode is not None,
                           reaped_ns=time.monotonic_ns())
            if receipt["reaped"] and receipt["exit_observed_ns"] is None:
                receipt["exit_observed_ns"] = time.monotonic_ns()
            if not receipt["reaped"]:
                errors.append(role + " child not reaped after KILL bound")
            if receipt["exit_code"] != 0:
                errors.append(role + " child exit nonzero: " + str(receipt["exit_code"]))
            if receipt["kill_sent"]:
                errors.append(role + " child required KILL")
            if receipt["reaped"]:
                child.close()  # release multiprocessing sentinel/process descriptors
                receipt["handle_closed"] = True
        except (OSError, ValueError, AssertionError) as exc:
            errors.append(role + " child cleanup: " + type(exc).__name__)
        finally:
            pipe = self.readiness.get(role)
            if pipe is not None:
                pipe.close()

    async def close(self):
        if self.cleanup is not None:
            return self.cleanup
        # Observe before suppressing expected EOF/death during ordered shutdown.
        self._observe_children()
        self.stopping = True
        errors = []
        if self.server:
            self.server.close()
        for handler in list(self.handlers):
            handler.cancel()
        # Base cleanup then owns record-reader/relay/task/port/state cleanup.
        # Keep reader alive until daemon sends bye and EOF, after station stop.
        for role in ("station", "daemon"):
            await self._reap_child(role, errors)
        cleanup = await super().close()
        cleanup["processes"] = {k: dict(v) for k, v in self.child_receipts.items()}
        cleanup["processes_reaped"] = all(
            not r["started"] or r["reaped"] for r in self.child_receipts.values())
        cleanup["errors"].extend(errors)
        cleanup["errors"].extend(role + " child died before cleanup"
                                 for role in sorted(self.child_failures))
        cleanup["ok"] = (cleanup["ok"] and cleanup["processes_reaped"]
                         and not cleanup["errors"])
        return cleanup
