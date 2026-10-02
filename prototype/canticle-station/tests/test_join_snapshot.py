"""The join snapshot (RFC-0001 §14.18.3 *Join snapshot*, amendment BC-1b, D36): proof case (5)(a)-(h), daemon side.

Everything runs in one event loop on loopback: UDP on an ephemeral 127.0.0.1 port, the unix socket in a
temporary directory. Receptor steps are driven either by real datagrams or through ``Daemon._call`` (the same
synchronous path a datagram takes), so that a race at the cut can be placed inside one event-loop step.
"""

import asyncio
import json
import os
import random
import socket
import time
import unittest
from pathlib import Path
from unittest import mock

from canticle import runner, wire
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig

from test_daemon import SK, DaemonCase, until

REQ = b'{"op":"join_snapshot","v":"canticle-receptor-record/1"}\n'
SNAP = ("snapshot", "snapshot_end")


def strip(rec):
    return {k: v for k, v in rec.items() if k not in ("v", "type", "rec_seq", "run")}


def parse(lines, asked=True):
    """The binding's validation of one connection (§14.18.3 *Joining a run*, *Join snapshot*). Returns the parts;
    raises AssertionError on anything the binding would call malformed_record."""
    recs = [json.loads(x) for x in lines]
    assert recs[0]["type"] == "hello" and recs[1]["type"] == "landing_state", recs[:2]
    assert recs[1]["rec_seq"] > recs[0]["rec_seq"] and recs[1]["run"] == recs[0]["run"]
    baseline = last = recs[1]["rec_seq"]
    i, before = 2, []
    while i < len(recs) and recs[i]["type"] not in SNAP:
        assert recs[i]["rec_seq"] > last, (recs[i]["rec_seq"], last)
        last = recs[i]["rec_seq"]
        before.append(recs[i])
        i += 1
    if not asked:
        assert i == len(recs), "snapshot record on a connection that did not ask"
        return {"baseline": baseline, "before": before, "snaps": [], "end": None, "after": []}
    snaps = []
    while i < len(recs) and recs[i]["type"] == "snapshot":
        snaps.append(recs[i])
        i += 1
    assert i < len(recs) and recs[i]["type"] == "snapshot_end", "no snapshot_end"
    end = recs[i]
    w = end["watermark"]
    assert end["rec_seq"] == w and w >= baseline and w >= last, (w, baseline, last)
    assert [s["snap_seq"] for s in snaps] == list(range(1, len(snaps) + 1))
    assert all(s["rec_seq"] == w and s["run"] == recs[0]["run"] for s in snaps)
    assert end["count"] == len(snaps) and end["truncated"] == (end["omitted"] > 0)
    after = recs[i + 1:]
    prev = w
    for r in after:
        assert r["type"] not in SNAP and r["rec_seq"] > prev, r
        prev = r["rec_seq"]
    return {"baseline": baseline, "before": before, "snaps": snaps, "end": end, "after": after}


class View:
    """A binding's local view of one run: surfaced frames by idem, presence by key id (§14.18.3 *Applying it*)."""

    def __init__(self):
        self.frames, self.presence = {}, {}

    def live(self, r):
        if r["type"] == "frame" and r["admission"] == "verified" and r["disposition"] == "surface":
            self.frames[r["idem"]] = strip(r)
        elif r["type"] == "retract":
            self.frames.pop(r["idem"], None)
        elif r["type"] == "presence":
            self.presence[r["key_id"]] = r["state"]

    def snapshot(self, snaps, end):
        frames = {s["entry"]["frame"]["idem"]: s["entry"]["frame"] for s in snaps if "frame" in s["entry"]}
        presence = {s["entry"]["presence"]["key_id"]: s["entry"]["presence"]["state"]
                    for s in snaps if "presence" in s["entry"]}
        if end["truncated"]:
            self.frames.update(frames)
            self.presence.update(presence)
        else:
            self.frames, self.presence = frames, presence

    @classmethod
    def of(cls, lines, asked=True):
        p = parse(lines, asked)
        v = cls()
        for r in p["before"]:
            v.live(r)
        if asked:
            v.snapshot(p["snaps"], p["end"])
        for r in p["after"]:
            v.live(r)
        return v


class SnapshotCase(DaemonCase):
    def setUp(self):
        super().setUp()
        m = Manifest([StationEntry("cael", wire.public_key_bytes(SK), frozenset({1, 3, 7}),
                                   ("chatter", "lens.threat", "alarms"))])
        Path(self.manifest).write_text(json.dumps(m.to_json()))

    def station(self):
        return Station(SK, [StreamConfig("chatter"), StreamConfig("lens.threat", cls="live-state"),
                            StreamConfig("alarms", cls="alarm")], epoch=1, rng=random.Random(3), now_ms=runner.now_ms())

    @staticmethod
    def feed(d, frames, now=None, kinds=(wire.KIND_ITEM, wire.KIND_PLUCK)):
        for f in frames:
            if f[3] in kinds:
                d._call(d.receptor.hear, f, now if now is not None else runner.now_ms())

    def sing(self, d, st, stream="chatter", now=None, **kw):
        """Sing one item and hear its frames (no beacon): one `frame` record. Returns the SingResult."""
        now = now if now is not None else runner.now_ms()
        kw.setdefault("ttl_s", 30)
        res = st.sing(now, stream, text=kw.pop("text", f"{stream} {now}"), **kw)
        self.feed(d, st.poll(now), now)
        return res

    def pluck(self, d, st, res, stream="chatter", now=None):
        now = now if now is not None else runner.now_ms()
        st.hush(now, stream, res.seq)
        self.feed(d, st.poll(now), now)

    def beacon(self, d, st, now=None):
        now = now if now is not None else runner.now_ms()
        st.next_beacon_at = 0
        self.feed(d, st.poll(now), now, kinds=(wire.KIND_BEACON,))

    def pad(self, d, n):
        assert d.emitter.rec_seq <= n, (d.emitter.rec_seq, n)
        while d.emitter.rec_seq < n:
            d.receptor.health(runner.now_ms())

    async def join(self, d, request=REQ):
        before = set(d.peers)
        c = await self.connect(d)
        if request:
            c.writer.write(request)
            await c.writer.drain()
        await until(lambda: len(d.peers - before) == 1, what="peer attached")
        peer = next(iter(d.peers - before))
        if request:
            await until(lambda: peer.snap_state is not None, what="request read")
        return c, peer

    def stall(self, d):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        s.connect(d.cfg.socket_path)
        s.setblocking(False)
        return s

    async def stalled_peer(self, d, s, queued):
        """Attach a stalled peer (never reads) and fill its queue to exactly ``queued`` records."""
        before = set(d.peers)
        await until(lambda: len(d.peers - before) == 1)
        peer = next(iter(d.peers - before))
        while True:                       # until the kernel buffer is full and the writer is blocked
            mark = len(peer.queue)
            for _ in range(20):
                d.receptor.health(runner.now_ms())
            await asyncio.sleep(0.02)
            if len(peer.queue) == mark + 20 and mark > 0:
                break
        assert len(peer.queue) <= queued, (len(peer.queue), queued)
        while len(peer.queue) < queued:
            d.receptor.health(runner.now_ms())
        return peer

    @staticmethod
    async def drain(s, sink, until_pred=lambda: False):
        loop = asyncio.get_running_loop()
        buf = b""
        try:
            while data := await loop.sock_recv(s, 65536):
                buf += data
                *done, buf = buf.split(b"\n")
                sink.extend(x + b"\n" for x in done)
        except (ConnectionError, OSError, asyncio.CancelledError):
            pass

    def many(self, d, st, n, now0):
        """``n`` chatter items, heard at now0, now0 + 1, ... (so newest-first order is checkable)."""
        for i in range(n):
            self.sing(d, st, now=now0 + i, text=f"item {i}")


class ProofCase5aContentTest(SnapshotCase):
    def test_content_watermark_and_live_tail(self):
        """(a) hello 1, landing_state 50, I1 at 60, S's presence at 70, I2 at 80 plucked at 90, B at 99."""
        async def scenario(d, port):
            st = self.station()
            a, _ = await self.join(d, request=None)
            await until(lambda: len(a.lines) == 2)
            self.pad(d, 49)
            d.receptor.set_landing(breaker="half_open", until=runner.now_ms() + 60_000)
            self.assertEqual(d.emitter.rec_seq, 50)
            self.pad(d, 59)
            i1 = self.sing(d, st)
            self.assertEqual(d.emitter.rec_seq, 60)
            self.pad(d, 69)
            self.beacon(d, st)
            self.assertEqual(d.emitter.rec_seq, 70)
            self.pad(d, 74)
            self.sing(d, st, "lens.threat", state_key="k")   # warm-up hold: ringbuffer_only, not deliverable
            self.pad(d, 79)
            i2 = self.sing(d, st)
            self.assertEqual(d.emitter.rec_seq, 80)
            self.pad(d, 89)
            self.pluck(d, st, i2)
            self.assertEqual(d.emitter.rec_seq, 90)
            self.pad(d, 99)
            b, peer = await self.join(d)
            await until(lambda: any(r["type"] == "snapshot_end" for r in b.recs))
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:   # a live record: over UDP
                st.sing(runner.now_ms(), "chatter", text="after the join", ttl_s=30)
                for f in st.poll(runner.now_ms()):
                    if f[3] == wire.KIND_ITEM:
                        s.sendto(f, ("127.0.0.1", port))
            await until(lambda: d.emitter.rec_seq >= 100)
            self.pad(d, 101)
            await until(lambda: b.seqs()[-1:] == [101] and a.seqs()[-1:] == [101])
            return a, b, i1, dict(d.snapshots)
        (a, b, i1, counts), _ = self.run_with(scenario)
        p = parse(b.lines)
        self.assertTrue(b.recs[0]["join_snapshot"])
        self.assertEqual((p["baseline"], p["before"], p["end"]["watermark"]), (50, [], 99))
        self.assertEqual(b.seqs()[:2], [1, 50])
        entries = [s["entry"] for s in p["snaps"]]
        self.assertEqual([next(iter(e)) for e in entries], ["presence", "frame"])
        by_seq = {r["rec_seq"]: r for r in a.recs}
        self.assertEqual(entries[0]["presence"], strip(by_seq[70]))          # S's current presence
        self.assertEqual(entries[1]["frame"], strip(by_seq[60]))             # I1's record, as emitted
        self.assertEqual(entries[1]["frame"]["frame"]["seq"], i1.seq)
        self.assertEqual(p["end"], {**p["end"], "count": 2, "truncated": False, "omitted": 0})
        self.assertEqual([r["rec_seq"] for r in p["after"]], [100, 101, 102])   # 102: the clean stop's bye
        self.assertEqual(a.lines[-3:], b.lines[-3:])                         # the same live records as A
        self.assertEqual(p["after"][0]["type"], "frame")
        self.assertEqual((counts["requested"], counts["served"], counts["truncated"]), (1, 1, 0))
        # B's view after snapshot_end equals A's view at W.
        va = View()
        for r in a.recs[2:]:
            if r["rec_seq"] <= 99:
                va.live(r)
        vb = View()
        vb.snapshot(p["snaps"], p["end"])
        self.assertEqual((vb.frames, vb.presence), (va.frames, va.presence))


class ProofCase5bCutTest(SnapshotCase):
    REQ_LINE = REQ.rstrip(b"\n")

    def test_retract_and_new_item_right_after_the_cut_queue_behind_snapshot_end(self):
        async def scenario(d, port):
            st = self.station()
            i1 = self.sing(d, st)
            b, peer = await self.join(d, request=None)
            await until(lambda: len(b.lines) == 2)
            # One event-loop step: the cut, then a PLUCK of I1 and a new item.
            self.assertTrue(d.request_snapshot(peer, self.REQ_LINE))
            w = d.emitter.rec_seq
            self.pluck(d, st, i1)
            i3 = self.sing(d, st)
            self.pad(d, d.emitter.rec_seq + 1)
            n = d.emitter.rec_seq
            await until(lambda: b.seqs()[-1:] == [n])
            return b, i1, i3, w
        (b, i1, i3, w), _ = self.run_with(scenario)
        p = parse(b.lines)
        self.assertEqual(p["end"]["watermark"], w)
        self.assertEqual([s["entry"]["frame"]["frame"]["seq"] for s in p["snaps"] if "frame" in s["entry"]], [i1.seq])
        after = [(r["type"], r.get("target", r.get("frame", {})).get("seq")) for r in p["after"]]
        self.assertEqual(after[:2], [("retract", i1.seq), ("frame", i3.seq)])
        self.assertEqual(p["after"][0]["rec_seq"], w + 1)
        idems = [r["idem"] for r in b.recs if r["type"] == "retract"]
        self.assertEqual(len(idems), 1)                                       # received once
        v = View.of(b.lines)
        self.assertEqual([f["frame"]["seq"] for f in v.frames.values()], [i3.seq])

    def test_pluck_and_expiry_in_the_same_turn_as_the_cut(self):
        async def scenario(d, port):
            st = self.station()
            now = runner.now_ms()
            plucked = self.sing(d, st, now=now)
            short = self.sing(d, st, now=now, ttl_s=30)
            long = self.sing(d, st, now=now, ttl_s=200)
            b, peer = await self.join(d, request=None)
            await until(lambda: len(b.lines) == 2)
            later = now + 31_000 + 1_000
            # One step: a PLUCK lands, then the cut at a time past `short`'s local expiry (its tick not yet run),
            # then the tick that retracts it.
            self.pluck(d, st, plucked, now=now)
            with mock.patch.object(runner, "now_ms", return_value=later):
                self.assertTrue(d.request_snapshot(peer, self.REQ_LINE))
            w = d.emitter.rec_seq
            d._call(d.receptor.tick, later)
            n = d.emitter.rec_seq
            await until(lambda: b.seqs()[-1:] == [n])
            return b, plucked, short, long, w
        (b, plucked, short, long, w), _ = self.run_with(scenario)
        p = parse(b.lines)
        self.assertEqual([r["target"]["seq"] for r in p["before"] if r["type"] == "retract"], [plucked.seq])
        snap_seqs = [s["entry"]["frame"]["frame"]["seq"] for s in p["snaps"] if "frame" in s["entry"]]
        self.assertEqual(snap_seqs, [long.seq])                               # neither plucked nor expired
        self.assertIn(("retract", short.seq, "expired"),
                      [(r["type"], r["target"]["seq"], r["reason"]) for r in p["after"] if r["type"] == "retract"])
        # No item is both in the snapshot and missed live: every surfaced item is accounted for exactly once.
        v = View.of(b.lines)
        self.assertEqual([f["frame"]["seq"] for f in v.frames.values()], [long.seq])


class ProofCase5cKeysTest(SnapshotCase):
    def test_entries_reproduce_records_with_dedup_as_emitted(self):
        """(c), daemon side: a frame entry is the record's fields with its idem and dedup unchanged; a tuple
        surfaced before a restart and not heard since is not an entry (this run emitted no record for it); one
        re-heard after the restart is, with dedup "resurfaced"."""
        st = self.station()
        now = runner.now_ms()
        r1 = st.sing(now, "chatter", text="before restart", ttl_s=30)
        r2 = st.sing(now, "chatter", text="also before", ttl_s=30)
        frames = [f for f in st.poll(now) if f[3] == wire.KIND_ITEM]

        async def first(d, port):
            for f in frames:
                d._call(d.receptor.hear, f, now)
            return len(d.receptor.deliverable)
        n, code = self.run_with(first)
        self.assertEqual((n, code), (2, 0))

        async def second(d, port):
            b, peer = await self.join(d, request=None)
            await until(lambda: len(b.lines) == 2)
            restored = set(d.receptor.restored)
            d._call(d.receptor.hear, frames[0], runner.now_ms())   # re-heard: resurfaced
            self.assertTrue(d.request_snapshot(peer, REQ.rstrip(b"\n")))
            await until(lambda: any(r["type"] == "snapshot_end" for r in b.recs))
            return b, restored
        (b, restored), _ = self.run_with(second)
        self.assertEqual(len(restored), 2)
        p = parse(b.lines)
        fr = [s["entry"]["frame"] for s in p["snaps"] if "frame" in s["entry"]]
        self.assertEqual(len(fr), 1)
        live = [r for r in p["before"] if r["type"] == "frame"]
        self.assertEqual(fr[0], strip(live[0]))
        self.assertEqual(fr[0]["dedup"], "resurfaced")
        self.assertEqual(p["end"]["truncated"], False)


class ProofCase5dCapacityTest(SnapshotCase):
    def test_empty_queue_more_than_511_live_carries_511_truncated(self):
        async def scenario(d, port):
            st = self.station()
            self.beacon(d, st)
            now0 = runner.now_ms()
            self.many(d, st, 600, now0)
            al = self.sing(d, st, "alarms", now=now0 - 5, state_key="door")   # oldest, but alarm class
            b, peer = await self.join(d, request=None)
            await until(lambda: len(b.lines) == 2 and not peer.queue)
            self.assertTrue(d.request_snapshot(peer, REQ.rstrip(b"\n")))
            q = len(peer.queue)
            await until(lambda: any(r["type"] == "snapshot_end" for r in b.recs), timeout=10)
            d.receptor.health(runner.now_ms())
            n = d.emitter.rec_seq
            await until(lambda: b.seqs()[-1:] == [n])
            return b, q, al, b.recs[-1]
        (b, q, al, health), _ = self.run_with(scenario)
        p = parse(b.lines)
        self.assertEqual(q, 512)                                       # 511 entries + snapshot_end, nothing else
        self.assertEqual((p["end"]["count"], p["end"]["truncated"], p["end"]["omitted"]), (511, True, 602 - 511))
        kinds = [next(iter(s["entry"])) for s in p["snaps"]]
        self.assertEqual(kinds[0], "presence")
        frames = [s["entry"]["frame"] for s in p["snaps"][1:]]
        self.assertEqual(frames[0]["class"], "alarm")                  # alarm first, whatever its heard_at
        heard = [f["times"]["heard_at"] for f in frames[1:]]
        self.assertEqual(heard, sorted(heard, reverse=True))           # then newest first
        self.assertEqual(frames[1]["body"]["text"], "item 599")
        self.assertEqual(health["snapshots"]["truncated"], 1)
        self.assertEqual(health["snapshots"]["served"], 1)

    def test_byte_cap_truncates(self):
        async def scenario(d, port):
            st = self.station()
            self.many(d, st, 50, runner.now_ms())
            b, peer = await self.join(d)
            await until(lambda: any(r["type"] == "snapshot_end" for r in b.recs))
            return b
        b, _ = self.run_with(scenario, snapshot_bytes_max=8_000)
        p = parse(b.lines)
        size = sum(len(x) for x in b.lines if json.loads(x)["type"] == "snapshot")
        self.assertLessEqual(size, 8_000)
        self.assertTrue(p["end"]["truncated"])
        self.assertEqual(p["end"]["count"] + p["end"]["omitted"], 50)
        self.assertGreater(p["end"]["count"], 0)

    def test_truncated_snapshot_merges_and_keeps_held_items(self):
        """(d) on a rejoin: an item B held that the cap leaves out is still held after snapshot_end."""
        v = View()
        v.frames = {"canticle:held": {"idem": "canticle:held"}}
        v.snapshot([{"entry": {"frame": {"idem": "canticle:new"}}}],
                   {"truncated": True, "omitted": 3, "count": 1})
        self.assertEqual(sorted(v.frames), ["canticle:held", "canticle:new"])


class ProofCase5eStalledTest(SnapshotCase):
    def test_stalled_mid_snapshot_is_closed_and_a_is_unchanged(self):
        async def scenario(d, port):
            emitted = []
            sink = d.emitter.sink
            d.emitter.sink = lambda t, line: (emitted.append(line), sink(t, line))
            st = self.station()
            a, _ = await self.join(d, request=None)
            now0 = runner.now_ms()
            for i in range(520):
                self.sing(d, st, now=now0 + i, text=f"{i} " + "x" * 900)
            s = self.stall(d)
            s.sendall(REQ)
            await until(lambda: any(p.snap_state for p in d.peers), what="request read")
            b = next(p for p in d.peers if p.snap_state)
            queue_peak = len(b.queue)
            t0 = time.monotonic()
            await until(lambda: b.closed, timeout=d.cfg.write_bound_s + 2, what="stalled snapshot closed")
            t_closed = time.monotonic() - t0
            self.sing(d, st, text="after the close")               # the receive path carries on
            n = d.emitter.rec_seq
            await until(lambda: a.seqs()[-1:] == [n])
            s.close()
            return a, emitted, queue_peak, t_closed, dict(d.snapshots), dict(d.counts)
        (a, emitted, peak, t_closed, snaps, counts), _ = self.run_with(scenario)
        self.assertEqual(a.lines[2:2 + len(emitted)], emitted)   # A: every record, nothing extra
        self.assertLessEqual(peak, 1024)
        self.assertLess(t_closed, 2.0 + 1.0)
        self.assertEqual((snaps["served"], snaps["closed"], counts["closed_stalled"]), (1, 1, 1))


class ProofCase5fConvergenceTest(SnapshotCase):
    def test_two_late_joiners_converge(self):
        async def scenario(d, port):
            st = self.station()
            a, _ = await self.join(d, request=None)
            self.beacon(d, st)
            items = [self.sing(d, st) for _ in range(5)]
            b, _ = await self.join(d)
            self.pluck(d, st, items[0])
            items += [self.sing(d, st) for _ in range(3)]
            self.pluck(d, st, items[6])
            c, _ = await self.join(d)
            self.pluck(d, st, items[2])
            self.sing(d, st)
            n = d.emitter.rec_seq
            await until(lambda: all(x.seqs()[-1:] == [n] for x in (a, b, c)))
            return a, b, c
        (a, b, c), _ = self.run_with(scenario)
        va = View.of(a.lines, asked=False)
        vb, vc = View.of(b.lines), View.of(c.lines)
        self.assertEqual(len(va.frames), 6)
        self.assertEqual((vb.frames, vb.presence), (va.frames, va.presence))
        self.assertEqual((vc.frames, vc.presence), (va.frames, va.presence))
        self.assertFalse(parse(b.lines)["end"]["truncated"] or parse(c.lines)["end"]["truncated"])


class ProofCase5gNoRequestTest(SnapshotCase):
    def test_without_a_request_the_stream_is_case_5_and_the_state_is_invisible(self):
        async def scenario(d, port):
            st = self.station()
            self.beacon(d, st)
            self.sing(d, st)
            d.receptor.set_landing(breaker="half_open", until=runner.now_ms() + 60_000)   # moves the baseline
            base = d.emitter.rec_seq
            plain, _ = await self.join(d, request=None)
            asking, _ = await self.join(d)
            self.pad(d, base + 2)
            await until(lambda: plain.seqs()[-1:] == [base + 2] and asking.seqs()[-1:] == [base + 2])
            return plain, asking, base
        (plain, asking, base), _ = self.run_with(scenario)
        p = parse(plain.lines, asked=False)
        self.assertEqual(plain.seqs()[1:4], [base, base + 1, base + 2])        # first live record: baseline + 1
        self.assertFalse(any(r["type"] in SNAP for r in plain.recs))
        v = View.of(plain.lines, asked=False)
        self.assertEqual((v.frames, v.presence), ({}, {}))                     # invisible to it
        q = parse(asking.lines)
        self.assertEqual([next(iter(s["entry"])) for s in q["snaps"]], ["presence", "frame"])
        self.assertEqual(q["end"]["watermark"], base)


class RequestHandlingTest(SnapshotCase):
    def test_one_request_per_connection_first_line_only(self):
        async def scenario(d, port):
            self.sing(d, self.station())
            twice, p1 = await self.join(d, request=REQ + REQ + b'{"op":"sing"}\n')
            junk, p2 = await self.join(d, request=None)
            junk.writer.write(b'{"op":"hello"}\n' + REQ)
            await junk.writer.drain()
            long, p3 = await self.join(d, request=None)
            long.writer.write(b"x" * (70 * 1024) + b"\n" + REQ)
            await long.writer.drain()
            badv, p4 = await self.join(d, request=None)
            badv.writer.write(b'{"op":"join_snapshot","v":"canticle-receptor-record/2"}\n')
            await badv.writer.drain()
            await until(lambda: d.snapshots["ignored"] == 2 + 2 + 2 + 1, what="ignored lines counted")
            await until(lambda: any(r["type"] == "snapshot_end" for r in twice.recs))
            self.pad(d, d.emitter.rec_seq + 1)
            n = d.emitter.rec_seq
            await until(lambda: all(c.seqs()[-1:] == [n] for c in (twice, junk, long, badv)))
            return twice, junk, long, badv, dict(d.snapshots)
        (twice, junk, long, badv, snaps), _ = self.run_with(scenario)
        self.assertEqual(sum(r["type"] == "snapshot_end" for r in twice.recs), 1)
        for c in (junk, long, badv):
            parse(c.lines, asked=False)
        self.assertEqual((snaps["requested"], snaps["served"]), (1, 1))


class CutErrorTest(SnapshotCase):
    def test_an_error_at_the_cut_closes_that_connection_only(self):
        async def scenario(d, port):
            a, _ = await self.join(d, request=None)
            with mock.patch.object(d.receptor, "snapshot_entries", side_effect=RuntimeError("boom")):
                b = await self.connect(d)
                b.writer.write(REQ)
                await b.writer.drain()
                await until(lambda: b.eof)
            self.sing(d, self.station())
            n = d.emitter.rec_seq
            await until(lambda: a.seqs()[-1:] == [n])
            return b, dict(d.snapshots), dict(d.counts)
        (b, snaps, counts), code = self.run_with(scenario)
        self.assertEqual(code, 0)
        self.assertFalse(any(r["type"] in SNAP for r in b.recs))
        self.assertEqual((snaps["closed"], counts["closed_snapshot_error"]), (1, 1))


class ProofCase5hQueuedTest(SnapshotCase):
    """(h) live records already queued at the request; the boundaries 513 free, 512 queued, stalled deferral."""

    def _live(self, d, n=600):
        st = self.station()
        self.many(d, st, n, runner.now_ms())

    def test_queued_live_records_snapshot_truncated_to_fit(self):
        async def scenario(d, port):
            self._live(d)
            s = self.stall(d)
            peer = await self.stalled_peer(d, s, 100)
            self.assertTrue(d.request_snapshot(peer, REQ.rstrip(b"\n")))
            w = d.emitter.rec_seq
            q = len(peer.queue)
            got: list = []
            reader = asyncio.create_task(self.drain(s, got))
            self.pad(d, d.emitter.rec_seq + 1)
            n = d.emitter.rec_seq
            await until(lambda: got and json.loads(got[-1])["rec_seq"] == n, timeout=10)
            reader.cancel()
            s.close()
            return got, w, q
        (got, w, q), _ = self.run_with(scenario)
        p = parse(got)
        self.assertEqual(q, 100 + 411 + 1)                           # min(511, 924 - 513) = 411, then snapshot_end
        self.assertEqual((p["end"]["count"], p["end"]["truncated"], p["end"]["omitted"]), (411, True, 600 - 411))
        self.assertEqual(p["end"]["watermark"], w)
        self.assertGreaterEqual(w, p["before"][-1]["rec_seq"])
        self.assertEqual(p["after"][0]["rec_seq"], w + 1)

    def test_exactly_513_free_slots_sends_only_snapshot_end(self):
        async def scenario(d, port):
            self._live(d, 3)
            s = self.stall(d)
            peer = await self.stalled_peer(d, s, 1024 - 513)
            self.assertTrue(d.request_snapshot(peer, REQ.rstrip(b"\n")))
            tail = [json.loads(line) for _, line, _ in list(peer.queue)[-2:]]
            free = peer.free()
            s.close()
            return tail, free
        (tail, free), _ = self.run_with(scenario)
        self.assertEqual(tail[-1]["type"], "snapshot_end")
        self.assertNotEqual(tail[-2]["type"], "snapshot")
        self.assertEqual((tail[-1]["count"], tail[-1]["truncated"], tail[-1]["omitted"]), (0, True, 3))
        self.assertEqual(free, 512)

    def test_512_queued_defers_the_cut_until_drained(self):
        async def scenario(d, port):
            self._live(d, 3)
            s = self.stall(d)
            peer = await self.stalled_peer(d, s, 512)
            self.assertTrue(d.request_snapshot(peer, REQ.rstrip(b"\n")))
            self.assertEqual(peer.snap_state, "deferred")
            self.pad(d, d.emitter.rec_seq + 5)                       # live records keep flowing meanwhile
            got: list = []
            reader = asyncio.create_task(self.drain(s, got))
            await until(lambda: peer.snap_state == "served", what="deferred cut taken")
            w = d.emitter.rec_seq
            self.pad(d, d.emitter.rec_seq + 1)
            n = d.emitter.rec_seq
            await until(lambda: got and json.loads(got[-1])["rec_seq"] == n, timeout=10)
            reader.cancel()
            s.close()
            return got, w, dict(d.snapshots)
        (got, w, snaps), _ = self.run_with(scenario)
        p = parse(got)
        self.assertEqual(p["end"]["watermark"], w)                  # W taken at the deferred cut
        self.assertGreater(w, p["before"][-1]["rec_seq"] - 1)
        # The cut happens the moment B has drained to 513 free slots (BC-1b), where the cap min(511, free - 513)
        # is 0: only snapshot_end goes out, truncated, and B stays joined_late.
        self.assertEqual((p["end"]["count"], p["end"]["truncated"], p["end"]["omitted"]), (0, True, 3))
        self.assertEqual((snaps["deferred"], snaps["served"], snaps["closed"]), (1, 1, 0))

    def test_deferred_and_stalled_is_closed_after_2_s(self):
        async def scenario(d, port):
            s = self.stall(d)
            peer = await self.stalled_peer(d, s, 600)
            self.assertTrue(d.request_snapshot(peer, REQ.rstrip(b"\n")))
            t0 = time.monotonic()
            await until(lambda: peer.closed, timeout=4, what="deferral closed")
            elapsed = time.monotonic() - t0
            s.close()
            return elapsed, dict(d.snapshots), dict(d.counts)
        (elapsed, snaps, counts), _ = self.run_with(scenario)
        self.assertGreaterEqual(elapsed, 2.0)
        self.assertLess(elapsed, 2.0 + 1.0)
        self.assertEqual((snaps["deferred"], snaps["closed"], snaps["served"], counts["closed_stalled"]), (1, 1, 0, 1))


if __name__ == "__main__":
    unittest.main()
