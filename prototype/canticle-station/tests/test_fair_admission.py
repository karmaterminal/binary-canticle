"""Fair admission before verify and durable write in the host daemon (binary-canticle#171).

The rows of #171's rerun table, each against a throwaway ``canticle daemon`` process over loopback UDP: a quiet
station sings 57 items while a flood runs, and every one of them must be admitted within the station's own burst
(first copy, then +1, +2 and +4 s; §7.6). What must hold under every flood is asserted from the daemon's own
records and from the kernel's drop counter for its socket (``/proc/net/udp``), never from the daemon's internals.

The floods are several times what the daemon's event loop can parse or save (about 15 000 parses/s and 40 durable
saves/s on ronan, #171), and several times less than its reader can read, so a row passes by the order of service.
The flat-out floods are #171's harness, not this module.
"""

import json
import os
import random
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import runner, wire
from canticle.ids import stream_id
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig
from flood import item

ROOT = Path(__file__).resolve().parents[1]
FLOOD = Path(__file__).resolve().parent / "flood.py"
QUIET_ITEMS = 57                # #171: "57/57"
QUIET_INTERVAL_S = 0.15
TAIL_S = 5.0                    # the flood outlasts the last quiet item's burst, so nothing is admitted after it
LATENCY_MAX_S = 4.5             # the last copy of the station's burst, and half a second
LATENCY_P50_S = 0.25
FLOOD_RATE = 100_000            # datagrams/s
BURST = 40_000                  # datagrams sent at a stopped daemon: more than any socket buffer it can ask for
RELAY_LEAD_S = 0.01             # how much earlier than the station a relay on a faster path is heard


OUTSIDE = "FAIL, outside the supported guarantee (not asserted)"


def kernel_drops(port: int) -> int:
    """The kernel's own drop counter for the socket bound to 127.0.0.1:port."""
    want = "0100007F:%04X" % port
    with open("/proc/net/udp") as fh:
        for row in fh.read().splitlines()[1:]:
            cols = row.split()
            if cols[1] == want:
                return int(cols[-1])
    raise AssertionError(f"no UDP socket on 127.0.0.1:{port}")


def percentile(xs: list, p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


class Tap(threading.Thread):
    """A record v1 binding on the daemon's socket that notes when each record arrived."""

    def __init__(self, path: str):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(path)
        self.recs: list = []          # (monotonic arrival, record)
        self.first: dict = {}         # idem -> arrival of its first verified frame record
        self.start()

    def run(self):
        buf = b""
        try:
            while chunk := self.sock.recv(1 << 20):
                now = time.monotonic()
                *lines, buf = (buf + chunk).split(b"\n")
                for line in lines:
                    rec = json.loads(line)
                    self.recs.append((now, rec))
                    if rec["type"] == "frame" and rec["admission"] == "verified":
                        self.first.setdefault(rec["idem"], now)
        except OSError:
            pass

    def frames(self) -> list:
        return [r for _, r in list(self.recs) if r["type"] == "frame"]

    def healths(self) -> list:
        return [r for _, r in list(self.recs) if r["type"] == "health"]

    def next_health(self, timeout=5.0) -> dict:
        n, deadline = len(self.healths()), time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(self.healths()) > n:
                return self.healths()[-1]
            time.sleep(0.01)
        raise AssertionError("no health record in time")


class Quiet(threading.Thread):
    """The quiet station: a real carousel, one item every QUIET_INTERVAL_S, from one socket. With ``relayed``, a relay
    without a key is heard RELAY_LEAD_S before it with a copy of each of its beacons, from a new port each."""

    def __init__(self, sk, port: int, capture=None, items=QUIET_ITEMS, bseq=0, beacon_ms=1_000, relayed=False):
        super().__init__(daemon=True)
        self.items = items
        self.st = Station(sk, [StreamConfig("quiet")], epoch=7, rng=random.Random(3), now_ms=runner.now_ms(),
                          beacon_period_ms=beacon_ms)
        self.st.bseq = bseq
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.dest, self.capture = ("127.0.0.1", port), capture
        self.sung: dict = {}          # idem -> when its first copy went out
        self.distinct: set = set()
        self.singing, self.stop = threading.Event(), threading.Event()
        self.warm: list = []          # items to sing before the row starts
        self.first_sent = None        # when its first frame went out
        self.relayed, self.relays = relayed, []    # the relay's sockets: kept open, so each copy has a port of its own

    def poll(self):
        for frame in self.st.poll(runner.now_ms()):
            self.distinct.add(frame)
            if self.relayed and frame[3] == wire.KIND_BEACON:
                self.relays.append(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
                self.relays[-1].sendto(frame, self.dest)
                time.sleep(RELAY_LEAD_S)
            self.first_sent = self.first_sent or time.monotonic()
            self.sock.sendto(frame, self.dest)
            if self.capture is not None and not self.singing.is_set():
                for dest in self.capture:
                    self.sock.sendto(frame, dest)

    def run(self):
        start = None
        while not self.stop.is_set():
            while self.warm:
                self.st.sing(runner.now_ms(), "quiet", text=self.warm.pop())
            if self.singing.is_set():
                start = start or time.monotonic()
                n = len(self.sung)
                if n < self.items and time.monotonic() >= start + n * QUIET_INTERVAL_S:
                    r = self.st.sing(runner.now_ms(), "quiet", text=f"quiet {n}")
                    self.sung[f"canticle:{self.st.key_id.hex()}:7:{stream_id('quiet'):08x}:{r.seq}"] = time.monotonic()
            self.poll()
            self.stop.wait(0.01)
        for s in (self.sock, *self.relays):
            s.close()


class FairAdmissionCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.keys = {}
        entries = []
        for name, streams in (("quiet", ("quiet", "flood")), ("other", ("flood", "quiet"))):
            sk = Ed25519PrivateKey.generate()
            self.keys[name] = sk
            path = os.path.join(self.dir, f"{name}.key")
            Path(path).write_text(sk.private_bytes_raw().hex())
            os.chmod(path, 0o600)
            entries.append(StationEntry(name, wire.public_key_bytes(sk), frozenset({1, 3}), streams))
        self.manifest = os.path.join(self.dir, "fleet.json")
        Path(self.manifest).write_text(json.dumps(Manifest(entries).to_json()))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]

    def kid(self, name: str) -> str:
        return wire.key_id(wire.public_key_bytes(self.keys[name])).hex()

    def env(self) -> dict:
        return {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1",
                "XDG_RUNTIME_DIR": self.dir, "XDG_STATE_HOME": self.dir}

    def daemon(self) -> subprocess.Popen:
        path = os.path.join(self.dir, "run", "daemon.sock")
        proc = subprocess.Popen(
            [sys.executable, "-m", "canticle", "daemon", "--manifest", self.manifest, "--bind",
             f"127.0.0.1:{self.port}", "--no-multicast", "--socket", path, "--state-dir",
             os.path.join(self.dir, "state"), "--health-interval", "0.5"],
            env=self.env(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.addCleanup(self._reap, proc)
        deadline = time.monotonic() + 15
        while not os.path.exists(path):
            if proc.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("the daemon did not start: " + proc.stderr.read().decode())
            time.sleep(0.02)
        time.sleep(0.1)
        self.tap = Tap(path)
        self.addCleanup(self.tap.sock.close)
        return proc

    def _reap(self, proc):
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        for f in (proc.stdout, proc.stderr):
            if f is not None:
                f.close()

    def flood(self, mode: str, duration: float, *args, fds=()) -> subprocess.Popen:
        proc = subprocess.Popen([sys.executable, str(FLOOD), mode, "--port", str(self.port), "--duration",
                                 str(duration), *map(str, args)], env=self.env(), stdout=subprocess.PIPE, pass_fds=fds)
        self.addCleanup(self._reap, proc)
        self.assertTrue(json.loads(proc.stdout.readline())["ready"])
        return proc

    @staticmethod
    def totals(proc) -> tuple:
        """(the JSON lines a flood printed, its totals)."""
        lines = [json.loads(x) for x in proc.stdout.read().splitlines()]    # not communicate(): it skips what is buffered
        proc.wait(60)
        return lines[:-1], lines[-1]

    def quiet(self, name="quiet", **kw) -> Quiet:
        q = Quiet(self.keys[name], self.port, **kw)
        q.start()
        self.addCleanup(q.join)
        self.addCleanup(q.stop.set)
        return q

    def first_frame(self, q: Quiet) -> float:
        """Seconds from the station's first frame, beacon or item, to the first record of its key: before it, the
        daemon had verified nothing of it."""
        return next(at for at, r in list(self.tap.recs)
                    if r["type"] == "presence" or (r["type"] == "frame" and r["admission"] == "verified")) - q.first_sent

    def settle(self, q: Quiet):
        """The daemon has heard the quiet station before the flood starts, as on a live seat."""
        deadline = time.monotonic() + 10
        while not any(r["type"] == "presence" for _, r in list(self.tap.recs)):
            self.assertLess(time.monotonic(), deadline, "the daemon never heard the quiet station")
            time.sleep(0.02)

    def measure(self, name: str, sung: dict, floods: list, note="") -> tuple:
        """Print one row: what arrived and when, what was offered, and what was lost, by reason. Returns (the latencies,
        the last health, the kernel's drops)."""
        offered = sum(t["sent"] / t["elapsed"] for t in floods)
        time.sleep(0.3)
        health = self.tap.next_health()
        lost = kernel_drops(self.port)
        lat = [self.tap.first[i] - t for i, t in sung.items() if i in self.tap.first]
        dist = " ".join(f"{k} {percentile(lat, p) * 1000:.0f}" for k, p in
                        (("p50", 50), ("p90", 90), ("p99", 99), ("max", 100))) if lat else "-"
        sys.stderr.write(f"\n{name}: quiet {len(lat)}/{len(sung)}; latency ms {dist}; offered {offered:,.0f}/s; "
                         f"socket drops {lost} (reported {health['records'].get('socket_dropped')}); "
                         f"receive {json.dumps(health.get('receive'))}; {note}\n")
        return lat, health, lost

    def row(self, name: str, sung: dict, floods: list, items=QUIET_ITEMS, note="") -> dict:
        """Check one row: every quiet item admitted, in time, with every loss counted. Returns the last health."""
        lat, health, lost = self.measure(name, sung, floods, note)
        self.assertEqual(len(sung), items)
        self.assertEqual(len(lat), items, f"{name}: {items - len(lat)} quiet items were never admitted")
        self.assertLessEqual(percentile(lat, 50), LATENCY_P50_S, name)
        self.assertLessEqual(max(lat), LATENCY_MAX_S, name)
        self.assertEqual(health["records"].get("socket_dropped"), lost, f"{name}: the kernel's drops are not reported")
        return health


class FloodRowsTest(FairAdmissionCase):
    DURATION = QUIET_ITEMS * QUIET_INTERVAL_S + TAIL_S

    def test_r1_valid_other_key_flood(self):
        """(R1) New valid items from another licensed key, as fast as two processes can sign them."""
        self.daemon()
        q = self.quiet()
        self.settle(q)
        floods = [self.flood("valid", self.DURATION, "--key", os.path.join(self.dir, "other.key"), "--epoch", 7 + i)
                  for i in range(2)]
        q.singing.set()
        health = self.row("R1 valid other-key flood", q.sung, [self.totals(f)[1] for f in floods])
        self.assertGreater(sum(health["receive"]["refused"].values()), 0)
        self.assertIn("datagrams_refused", {r for h in self.tap.healths() for r in h["reasons"]})

    def test_r2_same_station_flood(self):
        """(R2) The quiet stream inside the flooding station: one key, one socket, the flood on another stream."""
        self.daemon()
        f = self.flood("station", self.DURATION, "--key", os.path.join(self.dir, "quiet.key"), "--quiet-items",
                       QUIET_ITEMS, "--quiet-interval", QUIET_INTERVAL_S)
        lines, total = self.totals(f)
        sung = {f"canticle:{self.kid('quiet')}:7:{stream_id('quiet'):08x}:{x['seq']}": x["t"] for x in lines}
        health = self.row("R2 same-station flood", sung, [total])
        self.assertGreater(sum(health["receive"]["refused"].values()), 0)

    def test_r3_forged_flood_claiming_the_quiet_key(self):
        """(R3) Distinct invalid signatures naming the quiet key and stream, beside its own valid items: the flood
        may spend its own share of the verify work, never the honest station's."""
        self.daemon()
        q = self.quiet()
        self.settle(q)
        f = self.flood("forged", self.DURATION, "--kid", self.kid("quiet"), "--stream", "quiet", "--rate", FLOOD_RATE)
        q.singing.set()
        health = self.row("R3 forged flood claiming the quiet key", q.sung, [self.totals(f)[1]])
        self.assertGreater(health["counters"]["unverified"]["bad_signature"], 0)     # some were verified, and failed
        self.assertLess(health["counters"]["unverified"]["bad_signature"], 20_000)   # and only a bounded number were
        self.assertGreater(sum(health["receive"]["refused"].values()), 100_000)

    def test_r4_replays_of_the_quiet_keys_own_frames(self):
        """(R4) The quiet station's own frames, beacons included, captured before the flood and resent unchanged while
        they are still valid: from a sender of its own, and at the same time from the station's very socket (a
        perfect source spoof). No copy is verified again or costs the station anything, and every one is counted.
        (Replays of the newest item only would deliver it: the copies must be of earlier frames to do harm.)"""
        self.daemon()
        caps = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(2)]
        for c in caps:
            c.bind(("127.0.0.1", 0))
            self.addCleanup(c.close)
        q = self.quiet(capture=[c.getsockname() for c in caps])
        self.settle(q)
        for n in range(4):
            q.warm.append(f"warm {n}")
        time.sleep(4.5)                         # the warm items' bursts, and as many beacons, are captured
        floods = [self.flood("replay", self.DURATION, "--rate", FLOOD_RATE / 2, "--capture", c.fileno(), *extra,
                             fds=(c.fileno(), *fds))
                  for c, extra, fds in ((caps[0], (), ()),
                                        (caps[1], ("--fd", q.sock.fileno()), (q.sock.fileno(),)))]
        q.singing.set()
        health = self.row("R4 replays of the quiet key's own frames", q.sung, [self.totals(f)[1] for f in floods])
        self.assertGreater(health["receive"]["repeats"], 100_000)
        # One verify per distinct frame, give or take the copies already queued when the first one was verified.
        self.assertLessEqual(health["receive"]["verified"], len(q.distinct) + 50)


class LowRateTest(FairAdmissionCase):
    """Floods that base, with a whole core to spend on them, would have survived. Twenty items each."""

    ITEMS = 20
    DURATION = ITEMS * QUIET_INTERVAL_S + TAIL_S

    def test_old_beacons_replayed_cost_the_station_nothing(self):
        """A beacon has no expiry: one the digests no longer hold, or of an earlier epoch, verifies each time it is
        replayed. It must spend neither the station's beacons' turns nor its bucket, nor push its clock offset up
        until its items read `not_yet_valid`."""
        self.daemon()
        cap = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(cap.close)
        cap.bind(("127.0.0.1", 0))
        old = [wire.encode_beacon(self.keys["quiet"], wire.Beacon(
            epoch=epoch, bseq=bseq, wallclock=runner.now_ms() - 60_000, next_beacon_ms=1000,
            profile="canticle-regulation/1", streams=(), b_station=16_000)) for epoch in (6, 7) for bseq in range(1, 51)]
        for b in old:
            cap.sendto(b, cap.getsockname())
        q = self.quiet(items=self.ITEMS, bseq=1_000, beacon_ms=250)
        self.settle(q)
        f = self.flood("replay", self.DURATION, "--rate", 500, "--ports", 10, "--capture", cap.fileno(), fds=(cap.fileno(),))
        time.sleep(2)
        q.singing.set()
        totals = self.totals(f)[1]
        beacons = sum(frame[3] == wire.KIND_BEACON for frame in q.distinct)
        health = self.row("replayed old beacons, 10 ports", q.sung, [totals], items=self.ITEMS)
        self.assertEqual(health["counters"]["unverified"]["not_yet_valid"], 0)
        self.assertGreaterEqual(health["counters"]["beacon"]["verified"], beacons)     # every one of its own was heard

    def test_a_station_that_starts_inside_a_forged_flood_from_its_own_host(self):
        """Nothing of the key has verified yet, and its station shares its address with the forger's twelve ports."""
        self.daemon()
        f = self.flood("forged", self.DURATION + 2, "--kid", self.kid("quiet"), "--stream", "quiet", "--rate", 20_000,
                       "--ports", 12, "--beacons")
        time.sleep(1)
        q = self.quiet(items=self.ITEMS)
        q.singing.set()
        totals = self.totals(f)[1]
        self.row("cold start inside a forged flood, 12 ports", q.sung, [totals], items=self.ITEMS,
                 note=f"its first valid frame was admitted {1000 * self.first_frame(q):.0f} ms after it went out")

    def test_a_forger_at_the_stations_own_address_costs_only_that_station(self):
        """FAIL, outside the supported guarantee, for the spoofed station: forgeries from its very socket share its
        queue, and nothing before the signature can tell them apart. Scheduling by source narrows the threat model, it
        does not give that station R3's guarantee. Up to what the daemon spends on failed checks for one source, they
        cost nothing; here they are far more. The station's row is measured and printed, not asserted. Asserted is what
        is supported: other stations lose nothing, the verify work stays bounded, and the loss is reported."""
        self.daemon()
        q, other = self.quiet(items=self.ITEMS), self.quiet("other", items=self.ITEMS)
        self.settle(q)
        f = self.flood("forged", self.DURATION, "--kid", self.kid("quiet"), "--stream", "quiet", "--rate", FLOOD_RATE,
                       "--fd", q.sock.fileno(), fds=(q.sock.fileno(),))
        q.singing.set()
        other.singing.set()
        total = self.totals(f)[1]
        self.measure("R3 from the station's own socket: that station", q.sung, [total], note=OUTSIDE)
        health = self.row("R3 from the station's own socket: another station", other.sung, [total], items=self.ITEMS)
        self.assertLess(health["counters"]["unverified"]["bad_signature"], 20_000)
        self.assertIn("datagrams_refused", {r for h in self.tap.healths() for r in h["reasons"]})

    def test_a_slow_forger_at_the_stations_own_address_costs_nothing(self):
        self.daemon()
        q = self.quiet(items=self.ITEMS)
        self.settle(q)
        f = self.flood("forged", self.DURATION, "--kid", self.kid("quiet"), "--stream", "quiet", "--rate", 500,
                       "--fd", q.sock.fileno(), fds=(q.sock.fileno(),))
        q.singing.set()
        self.row("slow R3 from the station's own socket", q.sung, [self.totals(f)[1]], items=self.ITEMS)


class SourceChurnTest(FairAdmissionCase):
    """A source is an IPv4 address and a UDP port, so a sender can have as many as it likes (🌫's condition on #173)."""

    def test_forged_flood_from_a_new_socket_per_datagram(self):
        """R3 with the sources churned: a newly opened socket for every forgery, every second one on the station's own
        host and the others on 60 000 addresses. The station is established, and keeps its share."""
        self.daemon()
        q = self.quiet()
        self.settle(q)
        f = self.flood("forged", QUIET_ITEMS * QUIET_INTERVAL_S + TAIL_S, "--kid", self.kid("quiet"), "--stream", "quiet",
                       "--rate", FLOOD_RATE / 2, "--churn", 1)
        g = self.flood("forged", QUIET_ITEMS * QUIET_INTERVAL_S + TAIL_S, "--kid", self.kid("quiet"), "--stream", "quiet",
                       "--rate", FLOOD_RATE / 2, "--churn", 1, "--hosts", 60_000)
        q.singing.set()
        totals = [self.totals(x)[1] for x in (f, g)]
        sources = sum(t["sources"] for t in totals)
        health = self.row("R3 from a new socket per datagram", q.sung, totals,
                          note=f"{sum(t['opened'] for t in totals):,} sockets, {sources:,} sources")
        self.assertGreater(sources, 100_000)
        self.assertLess(health["counters"]["unverified"]["bad_signature"], 20_000)
        self.assertEqual((health["receive"].get("known"), health["receive"].get("displaced")), (1, 0))

    def test_a_relay_that_is_heard_first_takes_the_stations_share_and_it_is_counted(self):
        """FAIL, outside the supported guarantee, for the relayed station: a relay without a key, on a faster path,
        is heard first with the station's own beacons, from a new port each, so its ports are the known sources and
        the station is a stranger when the forged flood comes, from new sockets too. Nothing before the signature can tell
        a relay from the station. Its row is measured and printed, not asserted. Asserted is that the churn shows
        in the counts, and that another station loses nothing."""
        self.daemon()
        q, other = self.quiet(items=self.ITEMS, beacon_ms=250, relayed=True), self.quiet("other", items=self.ITEMS)
        self.settle(q)
        time.sleep(3)                           # a dozen beacons, each heard from the relay first
        before = self.tap.next_health()["receive"]
        f = self.flood("forged", self.DURATION + 1, "--kid", self.kid("quiet"), "--stream", "quiet", "--rate", FLOOD_RATE,
                       "--churn", 1)
        time.sleep(1)                           # no item of the station's slips in before the flood is at its rate
        q.singing.set()
        other.singing.set()
        total = self.totals(f)[1]
        self.measure("a relay heard first, then R3 from new sockets: that station", q.sung, [total], note=OUTSIDE)
        health = self.row("a relay heard first, then R3 from new sockets: another station", other.sung, [total],
                          items=self.ITEMS)
        self.assertGreater(before.get("displaced") or 0, 0, "the station's share went to the relay, and no count says so")
        self.assertGreaterEqual(health["receive"]["displaced"], before["displaced"])
        self.assertIn("datagrams_refused", {r for h in self.tap.healths() for r in h["reasons"]})

    ITEMS, DURATION = LowRateTest.ITEMS, LowRateTest.DURATION


class LossVisibilityTest(FairAdmissionCase):
    def test_r5_socket_drops_are_counted_and_degrade_health(self):
        """(R5) What the kernel drops at the daemon's socket is counted exactly, degrades health, and is told apart
        from what the daemon refused and from records dropped for a slow connection."""
        proc = self.daemon()
        self.assertEqual((self.tap.next_health()["state"], kernel_drops(self.port)), ("ok", 0))
        frame = item(self.keys["other"], "flood", 1, 7)
        os.kill(proc.pid, signal.SIGSTOP)       # the daemon stands still, so the socket must overflow
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            for _ in range(BURST):
                s.sendto(frame, ("127.0.0.1", self.port))
        os.kill(proc.pid, signal.SIGCONT)
        time.sleep(1.5)
        health, lost = self.tap.next_health(), kernel_drops(self.port)
        self.assertGreater(lost, 0)
        self.assertEqual(health["records"].get("socket_dropped"), lost,
                         f"the kernel dropped {lost} datagrams and health reported "
                         f"{health['records'].get('socket_dropped')}")
        degraded = [h for h in self.tap.healths() if "socket_drops" in h["reasons"]]
        self.assertTrue(degraded and all(h["state"] == "degraded" for h in degraded))
        self.assertEqual(health["records"]["dropped"], 0)          # records for a connection: none were
        self.assertNotIn("records_lost", {r for h in self.tap.healths() for r in h["reasons"]})
        self.assertEqual(self.tap.next_health()["reasons"], [])    # reported once per loss, not forever


if __name__ == "__main__":
    unittest.main()
