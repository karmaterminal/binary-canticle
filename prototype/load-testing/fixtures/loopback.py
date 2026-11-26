"""Bounded test-control adapter; the data plane is real UDP and record-v1 Unix IO."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import socket
import tempfile
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from canticle import runner, wire
from canticle.daemon import Daemon, DaemonConfig
from canticle.manifest import Manifest, StationEntry
from canticle.records import MAX_LINE, RECORD_V
from canticle.station import Station, StreamConfig


def bounded_int(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return value


@dataclass(frozen=True)
class Bounds:
    items: int = 6
    vus: int = 1
    deadline_ms: int = 1000
    pace_ms: int = 250
    drop_first: bool = False

    def __post_init__(self):
        bounded_int(self.items, 1, 16, "items")
        bounded_int(self.vus, 1, 2, "vus")
        bounded_int(self.deadline_ms, 500, 2000, "deadline_ms")
        bounded_int(self.pace_ms, 250, 1000, "pace_ms")
        if type(self.drop_first) is not bool:
            raise ValueError("drop_first must be a boolean")


def identity(frame):
    return (frame["key_id"], int(frame["epoch"]), int(frame["stream_id"]), int(frame["seq"]))


class Ledger:
    """The offer population is registered before submission, never after successful receipt."""
    def __init__(self, bounds):
        self.bounds = bounds
        self.rows = {}
        self.arrivals = {}
        self.records = {}
        self.record_counts = {}
        self.errors = deque(maxlen=16)
        self.packets = dict(received=0, forwarded=0, intentionally_dropped=0, invalid=0, send_errors=0)

    def offer(self, item_id, now_ns):
        bounded_int(item_id, 0, self.bounds.items - 1, "id")
        if item_id in self.rows or len(self.rows) >= self.bounds.items:
            raise ValueError("duplicate id or offer budget exhausted")
        row = dict(id=item_id, offered_ns=now_ns,
                   deadline_ns=now_ns + self.bounds.deadline_ms * 1_000_000,
                   identity=None, submit_error=None)
        self.rows[item_id] = row
        return row

    def result(self, row, now_ns):
        key = row["identity"]
        arrival = self.arrivals.get(key)
        record = self.records.get(key)
        on_time = bool(record and arrival and record[0] <= row["deadline_ns"]
                       and arrival[0] <= record[0] and record[1] == arrival[1])
        settled = on_time or now_ns >= row["deadline_ns"]
        end = record[0] if on_time else row["deadline_ns"]
        return dict(id=row["id"], identity=key,
                    offered_ns=row["offered_ns"], deadline_ns=row["deadline_ns"],
                    first_arrival_ns=arrival[0] if arrival else None,
                    complete_record_ns=record[0] if record else None,
                    frame_sha256=arrival[1] if arrival else None,
                    record_frame_sha256=record[1] if record else None,
                    accepted=key is not None, settled=settled,
                    delivered=on_time, missed=settled and not on_time,
                    arrived=arrival is not None,
                    late=bool(record and record[0] > row["deadline_ns"]),
                    submit_error=row["submit_error"],
                    offer_to_record_or_deadline_ms=(end-row["offered_ns"])/1e6,
                    arrival_to_record_ms=(record[0]-arrival[0])/1e6 if on_time else None,
                    arrival_to_record_or_deadline_ms=(end-arrival[0])/1e6
                    if arrival and arrival[0] <= end else None)

    def report(self, now_ns):
        rows = [self.result(r, now_ns) for r in self.rows.values()]
        counts = dict(offered=len(rows), accepted=sum(r["accepted"] for r in rows),
                      delivered=sum(r["delivered"] for r in rows),
                      missed=sum(r["missed"] for r in rows),
                      pending=sum(not r["settled"] for r in rows),
                      arrived=sum(r["arrived"] for r in rows),
                      late=sum(r["late"] for r in rows),
                      submit_errors=sum(r["submit_error"] is not None for r in rows),
                      duplicate_surface_records=sum(max(0, n-1) for n in self.record_counts.values()))
        p = self.packets
        accounting = (counts["offered"] == counts["accepted"] + counts["submit_errors"]
                      and counts["offered"] == counts["delivered"] + counts["missed"] + counts["pending"]
                      and p["received"] == sum(p[k] for k in p if k != "received")
                      and counts["arrived"] <= counts["accepted"])
        return dict(counts=counts, packets=dict(p), accounting=accounting,
                    errors=list(self.errors), rows=rows)


class Relay(asyncio.DatagramProtocol):
    """Instrumentation at first loopback arrival, then byte-identical UDP forwarding.

    Signature parsing here adds orchestration overhead to the arrival metric. The
    production daemon independently verifies the original, unchanged datagram.
    """
    def __init__(self, ledger, manifest, target):
        self.ledger, self.manifest, self.target = ledger, manifest, target
        self.transport = None
        self.sender_port = None
        self.closed = asyncio.Event()
        self.changed = asyncio.Event()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        arrived = time.monotonic_ns()  # before decoding/verification/forwarding
        p = self.ledger.packets
        p["received"] += 1
        try:
            f = wire.parse(data, self.manifest.resolve, now_ms=runner.now_ms())
            if self.sender_port is None:
                self.sender_port = addr[1]
            if f.kind == wire.KIND_ITEM:
                key = (f.key_id.hex(), f.body.epoch, f.body.stream, f.body.seq)
                # Only this fixture's bounded station and stream are accepted.
                if not 1 <= f.body.seq <= self.ledger.bounds.items:
                    raise ValueError("unexpected item sequence")
                self.ledger.arrivals.setdefault(key, (arrived, hashlib.sha256(data).hexdigest()))
                if self.ledger.bounds.drop_first and f.body.seq == 1:
                    p["intentionally_dropped"] += 1
                    self.changed.set()
                    return  # drop EVERY repeat, not just the initial datagram
            self.transport.sendto(data, self.target)
            p["forwarded"] += 1
        except wire.Reject:
            p["invalid"] += 1
        except (ValueError, OSError):
            p["send_errors"] += 1
        self.changed.set()

    def error_received(self, exc):
        self.ledger.errors.append("relay UDP error: " + type(exc).__name__)

    def connection_lost(self, exc):
        self.closed.set()


class Fixture:
    def __init__(self, bounds=Bounds()):
        self.bounds = bounds
        self.ledger = Ledger(bounds)
        self.run_id = secrets.token_hex(16)
        self.expected_ids = list(range(bounds.items))  # producer plan, before any submissions
        self.token = secrets.token_hex(24)
        self.temp = None
        self.root = None
        self.tasks = []
        self.handlers = set()
        self.writers = set()
        self.stopping = False
        self.station_stop = asyncio.Event()
        self.daemon_stop = asyncio.Event()
        self.changed = asyncio.Event()
        self.server = self.relay = self.relay_transport = self.client_writer = None
        self.ports = {}
        self.cleanup = None
        self.submit_lock = asyncio.Lock()

    async def __aenter__(self):
        try:
            await asyncio.wait_for(self.start(), 5)
            return self
        except BaseException:
            await self.close()
            raise

    async def __aexit__(self, *args):
        await self.close()

    def task(self, coroutine, name):
        t = asyncio.create_task(coroutine, name=name)
        self.tasks.append(t)
        return t

    async def start(self):
        # Keep AF_UNIX paths below Linux's 108-byte limit, even with a long TMPDIR.
        self.temp = tempfile.TemporaryDirectory(prefix="canticle-k6-", dir="/tmp")
        self.root = Path(self.temp.name)
        sk = Ed25519PrivateKey.generate()  # never serialized or retained
        grant = StationEntry("k6-fixture", wire.public_key_bytes(sk), frozenset({1}), ("chatter",))
        self.manifest = Manifest([grant])
        manifest_path = self.root / "fleet.json"
        manifest_path.write_text(json.dumps(self.manifest.to_json()))
        cfg = DaemonConfig(manifest=str(manifest_path), bind="127.0.0.1:0",
                           socket_path=str(self.root / "run" / "daemon.sock"),
                           state_dir=str(self.root / "state"), multicast=False,
                           health_interval_ms=None, tick_ms=50, log=lambda _: None)
        self.daemon = Daemon(cfg)
        ready = asyncio.Event()
        dt = self.task(self.daemon.run(self.daemon_stop, started=lambda _: ready.set()), "production-daemon")
        while not ready.is_set():
            if dt.done():
                raise RuntimeError(f"daemon failed to start: {dt.result()}")
            await asyncio.sleep(.005)
        self.ports["daemon_udp"] = self.daemon.udp.getsockname()[1]
        self.relay = Relay(self.ledger, self.manifest, ("127.0.0.1", self.ports["daemon_udp"]))
        self.relay_transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            lambda: self.relay, local_addr=("127.0.0.1", 0))
        self.ports["relay_udp"] = self.relay_transport.get_extra_info("sockname")[1]
        reader, self.client_writer = await asyncio.open_unix_connection(cfg.socket_path, limit=MAX_LINE)
        for expected in ("hello", "landing_state"):
            rec = json.loads(await reader.readline())
            if rec.get("v") != RECORD_V or rec.get("type") != expected:
                raise RuntimeError("invalid record-v1 bootstrap")
        self.record_run = rec["run"]
        self.rec_seq = rec["rec_seq"]
        self.task(self.read_records(reader), "record-v1-listener")
        self.control = str(self.root / "station.sock")
        self.station = Station(sk, [StreamConfig("chatter")], epoch=1,
                               now_ms=runner.now_ms(), grant=grant)
        st = self.task(runner.run_station(self.station,
            [("127.0.0.1", self.ports["relay_udp"])], self.control, self.station_stop), "production-station")
        while not Path(self.control).exists():
            if st.done():
                st.result()
                raise RuntimeError("station stopped at startup")
            await asyncio.sleep(.005)
        self.server = await asyncio.start_server(self.http, "127.0.0.1", 0, limit=4096, backlog=4)
        self.ports["http_tcp"] = self.server.sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{self.ports['http_tcp']}"

    async def read_records(self, reader):
        try:
            while line := await reader.readline():
                complete_ns = time.monotonic_ns()  # newline complete, before JSON parsing
                if len(line) > MAX_LINE or not line.endswith(b"\n"):
                    raise ValueError("invalid record framing")
                rec = json.loads(line)
                if (rec.get("v") != RECORD_V or rec.get("run") != self.record_run
                        or rec["rec_seq"] <= self.rec_seq):
                    raise ValueError("invalid record sequence/version/run")
                self.rec_seq = rec["rec_seq"]
                if rec["type"] == "fatal":
                    raise RuntimeError("daemon fatal record")
                if rec["type"] != "frame" or rec["frame"]["kind"] != "item":
                    continue
                key = identity(rec["frame"])
                if rec["disposition"] == "surface" and rec["admission"] == "verified":
                    if len(self.ledger.records) >= self.bounds.items and key not in self.ledger.records:
                        raise ValueError("record budget exceeded")
                    self.ledger.records.setdefault(key, (complete_ns, rec["frame"]["sha256"]))
                    self.ledger.record_counts[key] = self.ledger.record_counts.get(key, 0) + 1
                self.changed.set()
            if not self.stopping:
                self.ledger.errors.append("record client EOF before cleanup")
        except (ValueError, KeyError, RuntimeError, OSError) as exc:
            self.ledger.errors.append("record client: " + str(exc)[:160])
            self.changed.set()

    async def offer(self, item_id):
        row = self.ledger.offer(item_id, time.monotonic_ns())
        try:
            async with self.submit_lock:
                async with asyncio.timeout(.5):
                    reader, writer = await asyncio.open_unix_connection(self.control, limit=4096)
                    try:
                        writer.write(json.dumps(dict(op="sing", stream="chatter",
                            text=f"synthetic k6 item {item_id}", ttl=10, scope="lan")).encode() + b"\n")
                        await writer.drain()
                        response = json.loads(await reader.readline())
                        if not response.get("ok"):
                            raise ValueError("station refused submission")
                        row["identity"] = (self.station.key_id.hex(),
                            response["epoch"], self.station.streams["chatter"].sid, response["seq"])
                    finally:
                        writer.close()
                        await writer.wait_closed()
        except (TimeoutError, ValueError, OSError) as exc:
            row["submit_error"] = type(exc).__name__
        while True:
            now = time.monotonic_ns()
            result = self.ledger.result(row, now)
            if result["settled"]:
                return result
            self.changed.clear()
            try:
                await asyncio.wait_for(self.changed.wait(), (row["deadline_ns"]-now)/1e9)
            except TimeoutError:
                pass

    def report(self):
        report = self.ledger.report(time.monotonic_ns())
        report["run_id"] = self.run_id
        report["expected_ids"] = self.expected_ids
        report["production_tasks_alive"] = all(not t.done() for t in self.tasks)
        return report

    async def http(self, reader, writer):
        task = asyncio.current_task()
        if self.stopping or len(self.handlers) >= self.bounds.vus + 2:
            writer.close()
            return
        self.handlers.add(task)
        self.writers.add(writer)
        status, result = 400, {"error": "invalid bounded request"}
        try:
            async with asyncio.timeout(4):
                raw = await reader.readuntil(b"\r\n\r\n")
                if len(raw) > 2048:
                    raise ValueError("header too large")
                lines = raw.decode("ascii").split("\r\n")
                method, path, version = lines[0].split(" ")
                headers = {}
                for line in lines[1:]:
                    if line:
                        k, v = line.split(":", 1)
                        k = k.lower()
                        if k in headers:
                            raise ValueError("duplicate header")
                        headers[k] = v.strip()
                if version != "HTTP/1.1" or "transfer-encoding" in headers:
                    raise ValueError("only bounded HTTP/1.1 content-length supported")
                if not hmac.compare_digest(headers.get("authorization", ""), "Bearer " + self.token):
                    status, result = 403, {"error": "fixture token required"}
                elif method == "GET" and path == "/stats":
                    status, result = 200, self.report()
                elif method == "POST" and path == "/offer":
                    length = int(headers.get("content-length", "0"))
                    bounded_int(length, 1, 128, "content-length")
                    body = json.loads(await reader.readexactly(length))
                    if not isinstance(body, dict) or set(body) != {"id"}:
                        raise ValueError("body must be exactly {id: integer}")
                    status, result = 200, await self.offer(body["id"])
                else:
                    status, result = 404, {"error": "unknown fixture endpoint"}
        except (ValueError, TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            pass
        except Exception as exc:
            self.ledger.errors.append("fixture HTTP: " + type(exc).__name__)
            status, result = 500, {"error": "fixture failure"}
        try:
            data = json.dumps(result, allow_nan=False).encode()
            writer.write(f"HTTP/1.1 {status} Fixture\r\nContent-Type: application/json\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n".encode() + data)
            await asyncio.wait_for(writer.drain(), .5)
        except (OSError, TimeoutError):
            pass
        finally:
            writer.close()
            self.writers.discard(writer)
            self.handlers.discard(task)

    async def close(self):
        if self.cleanup is not None:
            return self.cleanup
        self.stopping = True
        errors = []

        async def stage(name, operation, timeout=1):
            try:
                await asyncio.wait_for(operation(), timeout)
            except (Exception, asyncio.CancelledError) as exc:
                errors.append(name + ": " + type(exc).__name__)

        if self.server:
            self.server.close()
            await stage("HTTP close", self.server.wait_closed)
        handlers = list(self.handlers)
        for t in handlers:
            t.cancel()
        await stage("HTTP handlers", lambda: asyncio.gather(*handlers, return_exceptions=True))
        for w in list(self.writers):
            try:
                w.close()
            except OSError as exc:
                errors.append("HTTP writer: " + type(exc).__name__)
        # Stop producer before daemon; later stages run after earlier faults.
        for name, event in (("production-station", self.station_stop), ("production-daemon", self.daemon_stop)):
            event.set()
            for t in self.tasks:
                if t.get_name() == name:
                    await stage(name, lambda t=t: asyncio.shield(t), 3)
                    if t.done() and not t.cancelled() and t.exception() is None:
                        if name == "production-daemon" and t.result() != 0:
                            errors.append("daemon exit nonzero")
                    else:
                        t.cancel()
        if self.client_writer:
            async def close_client():
                self.client_writer.close()
                await self.client_writer.wait_closed()
            await stage("record client close", close_client)
        if self.relay_transport:
            async def close_relay():
                self.relay_transport.close()
                await self.relay.closed.wait()
            await stage("relay close", close_relay)
            # asyncio closes the UDP socket in its scheduled connection_lost
            # callback even when the optional close-wait observer fails.
            await asyncio.sleep(0)
        for t in self.tasks:
            if not t.done():
                t.cancel()
        await stage("task join", lambda: asyncio.gather(*self.tasks, return_exceptions=True))
        try:
            if self.temp:
                self.temp.cleanup()
        except OSError as exc:
            errors.append("temporary state: " + type(exc).__name__)
        unix_absent = not self.root or not any(self.root.rglob("*.sock"))
        if self.relay and self.relay.sender_port is not None:
            self.ports["station_udp"] = self.relay.sender_port
        reusable = {}
        for name, port in self.ports.items():
            kind = socket.SOCK_STREAM if name == "http_tcp" else socket.SOCK_DGRAM
            with socket.socket(socket.AF_INET, kind) as probe:
                if kind == socket.SOCK_STREAM:
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(("127.0.0.1", port))
                    reusable[name] = True
                except OSError:
                    reusable[name] = False
        self.cleanup = dict(tasks_done=all(t.done() for t in self.tasks) and all(t.done() for t in handlers),
                            unix_sockets_removed=unix_absent,
                            temporary_state_removed=not self.root or not self.root.exists(),
                            ports_rebindable=reusable, errors=errors)
        self.cleanup["ok"] = (self.cleanup["tasks_done"] and unix_absent
                              and self.cleanup["temporary_state_removed"]
                              and all(reusable.values()) and not errors)
        return self.cleanup
