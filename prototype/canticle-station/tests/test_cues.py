"""Station-owned cue claims, time bounds and the actual control/carousel seam (#147)."""

import asyncio
from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import random
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import cues, runner, vectors, wire
from canticle.__main__ import main
from canticle.ids import CLASS_BY_NAME, SCOPES
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig

T0 = 1_790_000_000_000
SK = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(vectors.TEST1))
PK = SK.public_key()
GRANT = StationEntry(name="fixture", public_key=wire.public_key_bytes(SK),
                     classes=frozenset(CLASS_BY_NAME[c].code for c in ("ambient", "chatter")),
                     scopes=frozenset({SCOPES["lan"]}), streams=("weather", "chatter"))
ALLOWED = frozenset({"ambient", "chatter"})


def station(*, epoch=7, now=T0):
    return Station(SK, [StreamConfig("weather", cls="ambient", default_ttl_s=600, max_ttl_s=600),
                        StreamConfig("chatter", default_ttl_s=300, max_ttl_s=300)],
                   epoch=epoch, rng=random.Random(3), now_ms=now, grant=GRANT)


def request(cue_id="rain", **kw):
    return {"op": "cue_add", "id": cue_id, "stream": "weather", "text": "Rain on the workshop roof.",
            "in": 120, "for": 600, "loop": "normal", **kw}


class CueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "cues.sqlite"
        self.st = station()
        self.grant = GRANT
        self.store = cues.CueStore(self.path, self.st, now_ms=T0)
        self.addCleanup(lambda: self.store.close())

    def load(self):
        return self.grant

    def add(self, now=T0, **kw):
        return self.store.add(request(**kw), now, ALLOWED, self.load)

    def tick(self, now):
        self.store.tick(now, ALLOWED, self.load)

    def restart(self, now, epoch=8):
        self.store.close()
        self.st = station(epoch=epoch, now=now)
        self.store = cues.CueStore(self.path, self.st, now_ms=now)

    def test_future_start_survives_client_and_station_restart(self):
        added = self.add()
        self.assertEqual(added["state"], "pending")
        self.tick(T0 + 119_000)
        self.assertEqual(self.st.streams["weather"].head_seq, 0)
        self.restart(T0 + 119_500)
        self.tick(T0 + 120_000)
        receipt = self.store.show("rain")
        self.assertEqual(receipt["state"], "accepted")
        self.assertEqual(receipt["acceptance"]["expires_at"], T0 + 720_000)
        self.assertEqual(receipt["acceptance"]["epoch"], 8)
        self.assertEqual(receipt["remote_receipt"], "not_proved")

    def test_same_id_retry_keeps_original_window_and_different_request_refuses(self):
        first = self.add()
        self.assertEqual(self.add(now=T0 + 90_000), first)
        with self.assertRaisesRegex(ValueError, "different request"):
            self.add(text="A different elected sentence.")
        self.store.cancel("rain", T0 + 1)
        self.assertEqual(self.add(now=T0 + 2)["state"], "cancelled")

    def test_cancel_before_start_emits_no_cue_item_but_station_beacons_continue(self):
        self.add()
        result = self.store.cancel("rain", T0 + 10)
        self.assertEqual(result["cancellation"], "never_submitted")
        self.restart(T0 + 20)
        frames = []
        for now in range(T0 + 20, T0 + 800_000, 1000):
            self.tick(now)
            frames.extend(self.st.poll(now))
        self.assertTrue(any(f[3] == wire.KIND_BEACON for f in frames))
        self.assertFalse(any(f[3] == wire.KIND_ITEM for f in frames))
        self.assertEqual(self.st.streams["weather"].head_seq, 0)

    def test_restart_after_end_never_plays_late(self):
        self.add()
        self.restart(T0 + 800_000)
        self.tick(T0 + 800_000)
        self.assertEqual(self.store.show("rain")["state"], "missed")
        self.assertFalse(any(f[3] == wire.KIND_ITEM for f in self.st.poll(T0 + 800_000)))

    def test_valid_late_start_shortens_to_exact_original_end(self):
        self.add()
        self.tick(T0 + 125_001)
        result = self.store.show("rain")
        self.assertEqual(result["late_start_ms"], 5001)
        self.assertEqual(result["acceptance"]["expires_at"], result["ends_at"])
        self.assertEqual(result["acceptance"]["ttl_s"], 594.999)

    def test_duration_is_not_silently_clamped(self):
        with self.assertRaisesRegex(ValueError, "effective stream default TTL"):
            self.add(stream="chatter", **{"for": 600})
        with self.assertRaisesRegex(ValueError, "effective stream default TTL"):
            self.add(**{"for": 601})
        self.add()
        self.st.streams["weather"].cfg.default_ttl_s = 60
        self.tick(T0 + 650_000)  # remaining 70 s, original 600 s contract still binds
        self.assertEqual(self.store.show("rain")["state"], "refused")
        self.assertEqual(self.st.streams["weather"].head_seq, 0)

    def test_current_manifest_is_rechecked_before_dispatch(self):
        changes = [replace(GRANT, revoked=True), replace(GRANT, classes=frozenset()),
                   replace(GRANT, streams=("chatter",)), replace(GRANT, scopes=frozenset()), None]
        for i, changed in enumerate(changes):
            self.grant = GRANT
            created = T0 + i * 200_000
            self.add(now=created, cue_id=f"case{i}")
            self.grant = changed
            self.tick(created + 120_000)
            self.assertEqual(self.store.show(f"case{i}")["state"], "refused")
        self.assertEqual(self.st.streams["weather"].head_seq, 0)

    def test_actual_manifest_file_replacement_is_read_at_dispatch(self):
        manifest = Path(self.tmp.name) / "fixture.json"
        manifest.write_text(json.dumps(Manifest([GRANT]).to_json()))
        load = lambda: Manifest.load(manifest).entry(self.st.key_id)
        self.store.add(request(), T0, ALLOWED, load)
        replacement = manifest.with_name("replacement.json")
        replacement.write_text(json.dumps(Manifest([replace(GRANT, revoked=True)]).to_json()))
        replacement.replace(manifest)
        self.store.tick(T0 + 120_000, ALLOWED, load)
        self.assertEqual(self.store.show("rain")["state"], "refused")
        self.assertEqual(self.st.streams["weather"].head_seq, 0)

    def test_missing_manifest_and_socket_ceiling_fail_closed(self):
        self.add()
        def unavailable():
            raise OSError("fixture unreadable")
        self.store.tick(T0 + 120_000, ALLOWED, unavailable)
        self.assertEqual(self.store.show("rain")["state"], "refused")
        with self.assertRaisesRegex(ValueError, "control socket"):
            self.store.add(request("other"), T0 + 121_000, frozenset({"chatter"}), self.load)

    def test_revocation_stops_an_already_accepted_cue(self):
        self.add(**{"in": 0})
        self.tick(T0)
        self.st.poll(T0)
        self.grant = replace(GRANT, revoked=True)
        self.tick(T0 + 1000)
        result = self.store.show("rain")
        self.assertEqual(result["state"], "interrupted")
        self.assertIn("local_stopped", result["cancellation"])
        self.assertFalse(any(f[3] == wire.KIND_ITEM for f in self.st.poll(T0 + 1000)))

    def test_one_item_identity_repeats_until_absolute_end(self):
        self.add(**{"in": 0, "for": 60})
        frames = []
        for now in range(T0, T0 + 70_000, 500):
            self.tick(now)
            frames.extend(f for f in self.st.poll(now) if f[3] == wire.KIND_ITEM)
        self.assertGreater(len(frames), 4)
        self.assertEqual(len(set(frames)), 1)
        item = wire.parse(frames[0], lambda _: PK).body
        self.assertEqual((item.epoch, item.seq, item.expires_at), (7, 1, T0 + 60_000))
        self.assertEqual(self.store.show("rain")["state"], "ended")
        self.assertEqual(self.st.streams["weather"].head_seq, 1)

    def test_active_cancellation_stops_item_and_accepts_best_effort_pluck(self):
        self.add(**{"in": 0})
        self.tick(T0)
        self.st.poll(T0)
        receipt = self.store.cancel("rain", T0 + 1000)
        self.assertEqual(receipt["state"], "cancelled")
        self.assertIn("remote_delivery_not_proved", receipt["cancellation"])
        self.assertEqual(receipt["hush"]["expires_at"], T0 + 600_000)
        frames = self.st.poll(T0 + 1000)
        self.assertFalse(any(f[3] == wire.KIND_ITEM for f in frames))
        self.assertTrue(any(f[3] == wire.KIND_PLUCK for f in frames))
        seq = self.st.streams["weather"].head_seq
        self.store.cancel("rain", T0 + 2000)
        self.assertEqual(self.st.streams["weather"].head_seq, seq)

    def test_hush_failure_still_stops_owned_local_item_without_remote_erase_claim(self):
        self.add(**{"in": 0})
        self.tick(T0)
        with patch.object(self.st, "hush", side_effect=ValueError("capacity full")):
            receipt = self.store.cancel("rain", T0 + 1000)
        self.assertIn("local_stopped; pluck_outcome_unproved", receipt["cancellation"])
        self.assertIsNone(receipt["hush"])
        self.assertFalse(any(f[3] == wire.KIND_ITEM for f in self.st.poll(T0 + 2000)))

    def test_restart_does_not_replay_acceptance_or_cancel_new_epochs_matching_seq(self):
        self.add(**{"in": 0})
        self.tick(T0)
        self.restart(T0 + 1000)
        other = self.st.sing(T0 + 1000, "weather", text="Unrelated operator item.")
        self.assertEqual(other.seq, 1)
        self.store.cancel("rain", T0 + 2000)
        self.tick(T0 + 2000)
        self.assertEqual(self.store.show("rain")["state"], "interrupted")
        self.assertEqual(self.st.streams["weather"].head_seq, 1)
        self.assertTrue(any(f[3] == wire.KIND_ITEM for f in self.st.poll(T0 + 2000)))

    def test_claim_is_durable_before_real_sing_and_lost_result_never_retries(self):
        self.add(**{"in": 0})
        real_sing = self.st.sing
        def sing_then_lose_result(*a, **kw):
            with sqlite3.connect(self.path) as reader:
                self.assertEqual(reader.execute("SELECT state FROM cues WHERE id='rain'").fetchone()[0], "claimed")
            real_sing(*a, **kw)
            raise RuntimeError("lost acceptance result")
        with patch.object(self.st, "sing", side_effect=sing_then_lose_result) as send:
            self.tick(T0)
            self.tick(T0 + 10_000)
            self.assertEqual(send.call_count, 1)
        self.assertEqual(self.store.show("rain")["state"], "unknown")
        self.restart(T0 + 20_000)
        self.tick(T0 + 30_000)
        self.assertEqual(self.st.streams["weather"].head_seq, 0)
        self.assertEqual(self.store.show("rain")["state"], "unknown")

    def test_result_persistence_failure_leaves_claim_unknown_after_restart(self):
        self.add(**{"in": 0})
        update = self.store._update
        def fail_result(*a, **kw):
            if kw.get("state") == "accepted":
                raise sqlite3.OperationalError("fixture disk full")
            return update(*a, **kw)
        with patch.object(self.store, "_update", side_effect=fail_result):
            with self.assertRaises(sqlite3.OperationalError):
                self.tick(T0)
        self.assertEqual(self.store.show("rain")["state"], "claimed")
        self.restart(T0 + 1000)
        self.tick(T0 + 1000)
        self.assertEqual(self.store.show("rain")["state"], "unknown")
        self.assertEqual(self.st.streams["weather"].head_seq, 0)

    def test_backward_clock_stops_active_and_holds_pending_until_watermark(self):
        self.add(cue_id="active", **{"in": 0})
        self.add(cue_id="future", **{"in": 10})
        self.tick(T0)
        self.tick(T0 + 5000)
        self.tick(T0 + 1000)
        self.assertEqual(self.store.show("active")["state"], "interrupted")
        self.assertFalse(any(f[3] == wire.KIND_ITEM for f in self.st.poll(T0 + 1000)))
        with self.assertRaisesRegex(ValueError, "backwards"):
            self.add(cue_id="blocked", now=T0 + 1001)
        self.restart(T0 + 2000)
        self.tick(T0 + 4000)
        self.assertEqual(self.store.show("future")["state"], "pending")
        self.tick(T0 + 10_000)
        self.assertEqual(self.store.show("future")["state"], "accepted")

    def test_dispatch_is_capped_and_other_independent_cues_keep_their_windows(self):
        for cue_id in ("a", "b", "c"):
            self.add(cue_id=cue_id, **{"in": 0})
        self.tick(T0)
        self.tick(T0 + 999)
        self.assertEqual(self.st.streams["weather"].head_seq, 1)
        self.tick(T0 + 1000)
        self.tick(T0 + 2000)
        self.assertEqual(self.st.streams["weather"].head_seq, 3)
        for cue_id in ("a", "b", "c"):
            self.assertEqual(self.store.show(cue_id)["acceptance"]["expires_at"], T0 + 600_000)

    def test_inspection_redacts_payload_and_has_bounded_pagination(self):
        for cue_id in ("a", "b", "c"):
            self.add(cue_id=cue_id)
        page = self.store.listing(2)
        self.assertEqual([r["id"] for r in page["cues"]], ["a", "b"])
        self.assertEqual(page["next_after"], "b")
        self.assertEqual([r["id"] for r in self.store.listing(2, "b")["cues"]], ["c"])
        self.assertNotIn("Rain on the workshop", json.dumps(page))
        with self.assertRaises(ValueError):
            self.store.listing(cues.MAX_LIST + 1)

    def test_bounds_and_unsupported_authority_fields_refuse(self):
        invalid = [{"in": -1}, {"in": True}, {"in": cues.MAX_DELAY_S + 1}, {"for": 0},
                   {"for": 3601}, {"text": "x" * 801}, {"loop": "forever"}, {"id": "../bad"}]
        for kw in invalid:
            with self.assertRaises(ValueError):
                self.store.dispatch(request(**kw), T0, ALLOWED, self.load)
        for field in ("class", "scope", "keep_on_air", "body_ref"):
            with self.assertRaisesRegex(ValueError, "unsupported"):
                self.store.dispatch(request(**{field: "ungranted"}), T0, ALLOWED, self.load)
        with patch.object(cues, "MAX_ROWS", 1):
            self.add()
            with self.assertRaisesRegex(ValueError, "table full"):
                self.add(cue_id="another")

    def test_exclusive_database_lease_and_owner_only_permissions(self):
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(BlockingIOError):
            cues.CueStore(self.path, self.st, now_ms=T0)
        self.store.close()
        self.path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "0600"):
            cues.CueStore(self.path, self.st, now_ms=T0)
        self.path.chmod(0o600)
        symlink = self.path.with_name("alias.sqlite")
        symlink.symlink_to(self.path)
        with self.assertRaises(OSError):
            cues.CueStore(symlink, self.st, now_ms=T0)

    def test_database_cannot_be_reused_by_another_station_key(self):
        self.store.close()
        other_key = Ed25519PrivateKey.generate()
        other = Station(other_key, [StreamConfig("weather", cls="ambient")], epoch=7, now_ms=T0)
        with self.assertRaisesRegex(ValueError, "different station key"):
            cues.CueStore(self.path, other, now_ms=T0)

    def test_default_disabled_and_cli_command_shapes(self):
        self.assertFalse(runner._dispatch(self.st, request(), ALLOWED)["ok"])
        with patch.object(runner, "control_request", return_value={"ok": True}) as control, redirect_stdout(io.StringIO()):
            self.assertEqual(main(["cue", "add", "--control", "fixture.sock", "--id", "rain", "--stream", "weather",
                                   "--text", "Fixture weather", "--in", "120", "--for", "600"]), 0)
            self.assertEqual(control.call_args.args[1], request(text="Fixture weather"))
            self.assertEqual(main(["cue", "cancel", "--control", "fixture.sock", "--id", "rain"]), 0)
            self.assertEqual(control.call_args.args[1], {"op": "cue_cancel", "id": "rain"})


class ControlIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_station_unix_control_and_udp_cancel_then_accept(self):
        try:
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        except PermissionError:
            if os.environ.get("CI"):
                raise  # CI must exercise the actual control socket, never silently skip it.
            self.skipTest("workspace denies AF_UNIX; real control-socket proof must run in CI")
        else:
            probe.close()
        with tempfile.TemporaryDirectory() as tmp:
            now = runner.now_ms()
            st = station(now=now)
            db = cues.CueStore(Path(tmp) / "cues.sqlite", st, now_ms=now)
            control = str(Path(tmp) / "control.sock")
            stop = asyncio.Event()
            received = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            received.bind(("127.0.0.1", 0))
            received.setblocking(False)
            task = asyncio.create_task(runner.run_station(st, [received.getsockname()], control, stop,
                                       cue_store=db, grant_loader=lambda: GRANT))
            try:
                for _ in range(100):
                    if Path(control).exists():
                        break
                    await asyncio.sleep(0.01)
                self.assertTrue(Path(control).exists())
                send = lambda req: asyncio.to_thread(runner.control_request, control, req)
                added = await send(request("cancelled", **{"in": 1, "for": 5}))
                self.assertTrue(added["ok"])
                cancelled = await send({"op": "cue_cancel", "id": "cancelled"})
                self.assertEqual(cancelled["cue"]["cancellation"], "never_submitted")
                listed = await send({"op": "cue_list"})
                self.assertNotIn("Rain on the workshop", json.dumps(listed))
                # The submitting connection is already gone; station owns the wait.
                await send(request("accepted", text="Actual scheduled fixture", **{"in": 1, "for": 5}))
                deadline = asyncio.get_running_loop().time() + 3
                frames = []
                while asyncio.get_running_loop().time() < deadline:
                    try:
                        frame = await asyncio.wait_for(asyncio.get_running_loop().sock_recv(received, 1200), 0.3)
                        frames.append(frame)
                    except asyncio.TimeoutError:
                        pass
                    if any(f[3] == wire.KIND_ITEM for f in frames):
                        break
                items = [wire.parse(f, lambda _: PK).body for f in frames if f[3] == wire.KIND_ITEM]
                self.assertTrue(items)
                self.assertTrue(all(item.body == b"Actual scheduled fixture" for item in items))
                receipt = await send({"op": "cue_show", "id": "accepted"})
                self.assertEqual(receipt["cue"]["state"], "accepted")
                self.assertEqual(items[0].expires_at, receipt["cue"]["ends_at"])
                await send({"op": "cue_cancel", "id": "accepted"})
                self.assertFalse(any(o.kind == wire.KIND_ITEM for o in st.streams["weather"].ring.values()))
            finally:
                stop.set()
                try:
                    await task
                finally:
                    received.close()
                    db.close()


if __name__ == "__main__":
    unittest.main()
