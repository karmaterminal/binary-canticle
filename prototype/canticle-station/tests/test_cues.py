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

    def test_absolute_expiry_bounds_delayed_first_acceptance(self):
        # No earlier submission reached the station. Starting a fresh relative
        # 60 seconds at T0+50 must not freshen the originator's T0+60 deadline.
        receipt = self.add(now=T0 + 50_000, **{"in": 0, "for": 60, "not_after": T0 + 60_000})
        self.assertEqual(receipt["ends_at"], T0 + 60_000)
        self.tick(T0 + 50_123)
        receipt = self.store.show("rain")
        self.assertEqual(receipt["state"], "accepted")
        self.assertEqual(receipt["not_after"], T0 + 60_000)
        self.assertEqual(receipt["acceptance"]["expires_at"], T0 + 60_000)
        frames = self.st.poll(T0 + 50_123)
        item = next(wire.parse(f, lambda _: PK).body for f in frames if f[3] == wire.KIND_ITEM)
        self.assertEqual(item.expires_at, T0 + 60_000)
        self.assertEqual(item.issued_at, T0 + 50_123)

    def test_absolute_bound_retry_keeps_first_receipt_after_lost_ack_and_restart(self):
        req = request(**{"in": 0, "for": 60, "not_after": T0 + 60_000})
        first = self.store.dispatch(req, T0 + 50_000, ALLOWED, self.load)["cue"]
        # The client discards that response, then retries the identical request.
        self.assertEqual(self.store.dispatch(req, T0 + 55_000, ALLOWED, self.load)["cue"], first)
        self.restart(T0 + 56_000)
        self.tick(T0 + 56_000)
        accepted = self.store.dispatch(req, T0 + 57_000, ALLOWED, self.load)["cue"]
        self.assertEqual(accepted["state"], "accepted")
        self.assertEqual(accepted["ends_at"], T0 + 60_000)
        self.assertEqual(accepted["acceptance"]["expires_at"], T0 + 60_000)
        self.restart(T0 + 58_000, epoch=9)
        self.tick(T0 + 59_000)
        interrupted = self.store.dispatch(req, T0 + 70_000, ALLOWED, self.load)["cue"]
        self.assertEqual(interrupted["state"], "interrupted")
        self.assertEqual(interrupted["acceptance"], accepted["acceptance"])
        self.assertEqual(self.st.streams["weather"].head_seq, 0)

    def test_absolute_bound_is_part_of_idempotent_identity(self):
        req = request(**{"in": 0, "for": 60, "not_after": T0 + 60_000})
        first = self.store.dispatch(req, T0, ALLOWED, self.load)["cue"]
        changes = [{"not_after": T0 + 61_000}, {"not_after": T0 + 59_000}, {"text": "Changed"},
                   {"in": 1}, {"for": 59}, {"loop": "slow"}, {"stream": "chatter"}]
        for change in changes:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "different request"):
                self.store.dispatch({**req, **change}, T0 + 1, ALLOWED, self.load)
        without_bound = dict(req)
        del without_bound["not_after"]
        with self.assertRaisesRegex(ValueError, "different request"):
            self.store.dispatch(without_bound, T0 + 1, ALLOWED, self.load)
        self.assertEqual(self.store.show("rain"), first)

    def test_relative_saved_identity_is_unchanged_and_cannot_gain_a_bound(self):
        first = self.add()
        saved = self.store._row("rain")["request"]
        self.assertEqual(json.loads(saved), ["weather", "Rain on the workshop roof.", 120, 600, "normal"])
        self.assertIsNone(first["not_after"])
        self.restart(T0 + 1)
        self.assertEqual(self.add(now=T0 + 2), first)
        with self.assertRaisesRegex(ValueError, "different request"):
            self.add(now=T0 + 3, not_after=T0 + 720_000)

    def test_first_expired_or_unplayable_absolute_window_is_durably_missed(self):
        cases = [(0, 0), (0, T0 - 1), (0, T0), (0, T0 + 100),
                 (120, T0 + 119_999), (120, T0 + 120_100)]
        for i, (delay, bound) in enumerate(cases):
            req = request(f"missed{i}", **{"in": delay, "for": 60, "not_after": bound})
            first = self.store.dispatch(req, T0, ALLOWED, self.load)["cue"]
            self.assertEqual(first["state"], "missed")
            self.assertIsNone(first["claimed_epoch"])
            self.assertIsNone(first["acceptance"])
            self.assertEqual(first["not_after"], bound)
            self.assertEqual(self.store.dispatch(req, T0 + 1000, ALLOWED, self.load)["cue"], first)
        self.restart(T0 - 1000)
        self.tick(T0 + 100_000)
        self.assertEqual(self.st.streams["weather"].head_seq, 0)
        self.assertFalse(any(f[3] == wire.KIND_ITEM for f in self.st.poll(T0 + 100_000)))

    def test_pending_absolute_window_missed_during_restart_never_sings(self):
        self.add(**{"in": 10, "for": 60, "not_after": T0 + 30_000})
        self.restart(T0 + 31_000)
        self.tick(T0 + 31_000)
        self.assertEqual(self.store.show("rain")["state"], "missed")
        self.assertEqual(self.store.show("rain")["ends_at"], T0 + 30_000)
        self.assertEqual(self.st.streams["weather"].head_seq, 0)

    def test_absolute_bound_only_shortens_and_preserves_exact_milliseconds(self):
        self.add(cue_id="later", **{"in": 0, "for": 60, "not_after": cues.MAX_NOT_AFTER_MS})
        self.tick(T0)
        self.assertEqual(self.store.show("later")["acceptance"]["expires_at"], T0 + 60_000)
        self.add(cue_id="earlier", now=T0 + 1000, **{"in": 0, "for": 60, "not_after": T0 + 60_123})
        self.tick(T0 + 1000)
        self.assertEqual(self.store.show("earlier")["acceptance"]["expires_at"], T0 + 60_123)
        self.assertEqual(self.store.show("earlier")["acceptance"]["ttl_s"], 59.123)

    def test_absolute_bound_cannot_bypass_requested_duration_authority(self):
        with self.assertRaisesRegex(ValueError, "effective stream default TTL"):
            self.add(stream="chatter", **{"in": 0, "for": 600, "not_after": T0 + 10_000})
        self.add(**{"in": 0, "for": 600, "not_after": T0 + 30_000})
        self.st.streams["weather"].cfg.default_ttl_s = 60
        self.tick(T0 + 1000)
        self.assertEqual(self.store.show("rain")["state"], "refused")
        self.assertEqual(self.st.streams["weather"].head_seq, 0)

    def test_absolute_bound_has_strict_json_integer_validation(self):
        for bad in (None, True, False, -1, 1.0, "1790000060000", (1 << 53), [], {}):
            with self.subTest(value=bad), self.assertRaisesRegex(ValueError, "not_after must be an integer"):
                self.store.dispatch(request(not_after=bad), T0, ALLOWED, self.load)
        self.assertEqual(self.store.listing()["cues"], [])

    def test_absolute_bound_clock_regression_holds_without_moving_deadline(self):
        req = request(**{"in": 10, "for": 60, "not_after": T0 + 30_000})
        self.store.dispatch(req, T0, ALLOWED, self.load)
        self.tick(T0 + 5000)
        self.restart(T0 + 2000)
        self.tick(T0 + 4000)
        self.assertEqual(self.store.show("rain")["state"], "pending")
        with self.assertRaisesRegex(ValueError, "backwards"):
            self.store.dispatch({**req, "id": "second"}, T0 + 4000, ALLOWED, self.load)
        self.tick(T0 + 10_000)
        self.assertEqual(self.store.show("rain")["acceptance"]["expires_at"], T0 + 30_000)
        self.tick(T0 + 9000)
        self.assertEqual(self.store.show("rain")["state"], "interrupted")
        self.tick(T0 + 11_000)
        self.assertFalse(any(f[3] == wire.KIND_ITEM for f in self.st.poll(T0 + 11_000)))

    def test_absolute_bound_unknown_sing_and_identical_retry_never_reissue(self):
        req = request(**{"in": 0, "for": 60, "not_after": T0 + 30_000})
        self.store.dispatch(req, T0, ALLOWED, self.load)
        real_sing = self.st.sing
        def lost(*a, **kw):
            real_sing(*a, **kw)
            raise RuntimeError("fixture: acceptance result lost")
        with patch.object(self.st, "sing", side_effect=lost) as send:
            self.tick(T0 + 1000)
            self.store.dispatch(req, T0 + 2000, ALLOWED, self.load)
            self.tick(T0 + 2000)
            self.assertEqual(send.call_count, 1)
        unknown = self.store.show("rain")
        self.assertEqual(unknown["state"], "unknown")
        self.assertEqual(unknown["ends_at"], T0 + 30_000)
        self.restart(T0 + 3000)
        self.tick(T0 + 4000)
        self.assertEqual(self.store.show("rain")["state"], "unknown")
        self.assertEqual(self.st.streams["weather"].head_seq, 0)

    def test_absolute_bound_cancellation_keeps_original_expiry(self):
        self.add(cue_id="cancel-before", **{"in": 10, "for": 60, "not_after": T0 + 30_000})
        self.assertEqual(self.store.cancel("cancel-before", T0)["cancellation"], "never_submitted")
        self.add(cue_id="cancel-after", **{"in": 0, "for": 60, "not_after": T0 + 30_123})
        self.tick(T0)
        result = self.store.cancel("cancel-after", T0 + 1000)
        self.assertEqual(result["state"], "cancelled")
        self.assertEqual(result["hush"]["expires_at"], T0 + 30_123)
        self.assertEqual(result["not_after"], T0 + 30_123)

    def test_capabilities_are_read_only_and_cli_sends_absolute_milliseconds(self):
        watermark = self.store.watermark
        resp = self.store.dispatch({"op": "cue_capabilities"}, T0 + 5000, ALLOWED, self.load)
        self.assertEqual(resp, {"ok": True, "capabilities": {"schema": "canticle-cue-control/1",
                         "absolute_not_after": True, "exact_station_public_key": True,
                         "timestamp_unit": "unix_ms", "max_not_after": (1 << 53) - 1}})
        self.assertEqual(self.store.watermark, watermark)
        self.assertEqual(self.store.listing()["cues"], [])
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.store.dispatch({"op": "cue_capabilities", "text": "no"}, T0, ALLOWED, self.load)
        self.assertFalse(runner._dispatch(self.st, {"op": "cue_capabilities"}, ALLOWED)["ok"])
        with patch.object(runner, "control_request", return_value={"ok": True}) as control, redirect_stdout(io.StringIO()):
            self.assertEqual(main(["cue", "capabilities", "--control", "fixture.sock"]), 0)
            self.assertEqual(control.call_args.args[1], {"op": "cue_capabilities"})
            self.assertEqual(main(["cue", "add", "--control", "fixture.sock", "--id", "rain", "--stream", "weather",
                                   "--text", "Fixture", "--in", "0", "--for", "60", "--not-after-ms", str(T0 + 60_000)]), 0)
            self.assertEqual(control.call_args.args[1], request(text="Fixture", **{"in": 0, "for": 60, "not_after": T0 + 60_000}))

    def test_wrong_expected_public_key_has_no_cue_or_real_station_effect(self):
        before = list(self.store.db.iterdump())
        refused = None
        try:
            # Exercise the real station and cue table, without mocking signing.
            self.add(now=T0 + 5000, expected_public_key="00" * 32, **{"in": 0})
        except ValueError as error:
            refused = str(error)
        after_add = list(self.store.db.iterdump())
        self.tick(T0 + 5000)
        self.assertEqual(self.st.streams["weather"].head_seq, 0,
                         "A request for another full public key reached real signing")
        self.assertFalse(any(f[3] == wire.KIND_ITEM for f in self.st.poll(T0 + 5000)))
        self.assertIsNotNone(refused)
        self.assertIn("expected_public_key does not match", refused)
        self.assertEqual(after_add, before, "A refused identity changed the cue database or watermark")

    def test_expected_public_key_is_checked_before_existing_id_lookup(self):
        first = self.add()
        before = list(self.store.db.iterdump())
        with self.assertRaisesRegex(ValueError, "expected_public_key does not match"):
            self.add(now=T0 + 5000, expected_public_key="00" * 32)
        self.assertEqual(list(self.store.db.iterdump()), before)
        self.assertEqual(self.store.show("rain"), first)

    def test_expected_public_key_strict_shape_rejection_is_state_neutral(self):
        pub = GRANT.public_key.hex()
        for invalid in (None, False, 0, [], {}, "", pub[:-1], pub + "0", "g" * 64,
                        " " + pub, pub + "\n", "0x" + pub, "０" * 64):
            with self.subTest(value=invalid):
                before = list(self.store.db.iterdump())
                with self.assertRaisesRegex(ValueError, "expected_public_key must be 64 ASCII hex characters"):
                    self.store.add(request(expected_public_key=invalid), T0 + 5000, ALLOWED, self.load)
                self.assertEqual(list(self.store.db.iterdump()), before)

    def test_matching_expected_public_key_preserves_legacy_identity_and_restart(self):
        pub = GRANT.public_key.hex()
        req = request(**{"in": 10, "for": 60, "not_after": T0 + 30_000})
        first = self.store.dispatch(req, T0, ALLOWED, self.load)["cue"]
        saved = self.store._row("rain")["request"]
        for expected in (pub, pub.upper()):
            self.assertEqual(self.store.dispatch({**req, "expected_public_key": expected}, T0 + 1,
                                                ALLOWED, self.load)["cue"], first)
            self.assertEqual(self.store._row("rain")["request"], saved)
        self.restart(T0 + 2000)
        self.tick(T0 + 10_000)
        accepted = self.store.dispatch({**req, "expected_public_key": pub}, T0 + 10_001, ALLOWED, self.load)["cue"]
        self.assertEqual(accepted["state"], "accepted")
        self.assertEqual(accepted["acceptance"]["expires_at"], T0 + 30_000)
        self.assertEqual(self.st.streams["weather"].head_seq, 1)

    def test_cli_carries_exact_public_key_expectation(self):
        pub = GRANT.public_key.hex()
        with patch.object(runner, "control_request", return_value={"ok": True}) as control, redirect_stdout(io.StringIO()):
            self.assertEqual(main(["cue", "add", "--control", "fixture.sock", "--id", "rain", "--stream", "weather",
                                   "--text", "Fixture", "--in", "0", "--for", "60", "--expected-public-key", pub]), 0)
            self.assertEqual(control.call_args.args[1], request(text="Fixture", expected_public_key=pub,
                                                               **{"in": 0, "for": 60}))

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
    async def test_replaced_control_socket_refuses_wrong_expected_signer_before_effect(self):
        try:
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        except PermissionError:
            if os.environ.get("CI"):
                raise
            self.skipTest("workspace denies AF_UNIX; exact-signer control proof must run in CI")
        else:
            probe.close()
        with tempfile.TemporaryDirectory() as tmp:
            control = str(Path(tmp) / "control.sock")
            received = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            received.bind(("127.0.0.1", 0))
            received.setblocking(False)
            st = station(now=runner.now_ms())
            db = cues.CueStore(Path(tmp) / "first.sqlite", st, now_ms=runner.now_ms())
            stop = asyncio.Event()
            task = asyncio.create_task(runner.run_station(st, [received.getsockname()], control, stop,
                                       cue_store=db, grant_loader=lambda: GRANT))
            send = lambda req: asyncio.to_thread(runner.control_request, control, req)

            async def ready():
                for _ in range(100):
                    if Path(control).exists():
                        return
                    await asyncio.sleep(0.01)
                self.fail("Real station did not create its control socket")

            try:
                await ready()
                catalog = await send({"op": "public_catalog"})
                elected = catalog["public_key"]
                self.assertEqual(elected, GRANT.public_key.hex())
                # A different real signing station now owns the same pathname.
                stop.set()
                await task
                db.close()
                other_sk = Ed25519PrivateKey.generate()
                other_grant = replace(GRANT, public_key=wire.public_key_bytes(other_sk))
                st = Station(other_sk, [StreamConfig("weather", cls="ambient", default_ttl_s=600, max_ttl_s=600)],
                             epoch=8, now_ms=runner.now_ms(), grant=other_grant)
                db = cues.CueStore(Path(tmp) / "replacement.sqlite", st, now_ms=runner.now_ms())
                stop = asyncio.Event()
                task = asyncio.create_task(runner.run_station(st, [received.getsockname()], control, stop,
                                           cue_store=db, grant_loader=lambda: other_grant))
                await ready()
                capability = await send({"op": "cue_capabilities"})
                self.assertTrue(capability["capabilities"]["exact_station_public_key"])
                refused = await send(request("wrong-station", expected_public_key=elected, **{"in": 0, "for": 5}))
                self.assertFalse(refused["ok"])
                self.assertIn("expected_public_key does not match", refused["error"])
                self.assertEqual((await send({"op": "cue_list"}))["cues"], [])
                self.assertEqual(st.streams["weather"].head_seq, 0)
                self.assertFalse(any(o.kind == wire.KIND_ITEM for o in st.streams["weather"].ring.values()))

                # A correctly pinned request proves that the real replacement
                # socket, signing path and loopback receiver are operational.
                accepted = await send(request("right-station", text="Exact signer fixture",
                                             expected_public_key=other_grant.public_key.hex(), **{"in": 0, "for": 5}))
                self.assertTrue(accepted["ok"])
                deadline = asyncio.get_running_loop().time() + 2
                items = []
                while asyncio.get_running_loop().time() < deadline and not items:
                    try:
                        frame = await asyncio.wait_for(asyncio.get_running_loop().sock_recv(received, 1200), 0.2)
                    except asyncio.TimeoutError:
                        continue
                    if frame[3] == wire.KIND_ITEM:
                        items.append(wire.parse(frame, lambda _: other_sk.public_key()).body)
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0].body, b"Exact signer fixture")
                self.assertEqual(items[0].epoch, 8)
                self.assertEqual(st.streams["weather"].head_seq, 1)
                self.assertEqual([r["id"] for r in (await send({"op": "cue_list"}))["cues"]], ["right-station"])
            finally:
                stop.set()
                try:
                    await task
                finally:
                    received.close()
                    db.close()

    async def test_absolute_expiry_over_real_control_and_udp_with_unread_ack(self):
        try:
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        except PermissionError:
            if os.environ.get("CI"):
                raise
            self.skipTest("workspace denies AF_UNIX; absolute-expiry control proof must run in CI")
        else:
            probe.close()
        # The boundary uses real Unix control connections, a real SQLite table,
        # the station's actual signing/carousel code and loopback UDP. Only the
        # wall-clock observation is controlled, so no minute-long sleep is needed.
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, "now_ms") as read_clock:
            clock = [T0 + 50_000]
            read_clock.side_effect = lambda: clock[0]
            st = station(now=clock[0])
            db = cues.CueStore(Path(tmp) / "cues.sqlite", st, now_ms=clock[0])
            control = str(Path(tmp) / "control.sock")
            stop = asyncio.Event()
            received = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            received.bind(("127.0.0.1", 0))
            received.setblocking(False)
            task = asyncio.create_task(runner.run_station(st, [received.getsockname()], control, stop,
                                       cue_store=db, grant_loader=lambda: GRANT))
            abandoned = None
            try:
                for _ in range(100):
                    if Path(control).exists():
                        break
                    await asyncio.sleep(0.01)
                self.assertTrue(Path(control).exists())
                send = lambda req: asyncio.to_thread(runner.control_request, control, req)
                capability = await send({"op": "cue_capabilities"})
                self.assertTrue(capability["capabilities"]["absolute_not_after"])
                self.assertEqual(capability["capabilities"]["timestamp_unit"], "unix_ms")

                # First submission reaches the station 50 seconds after origin.
                # Keep the connection open but never read its acknowledgement.
                req = request("delayed", text="Delayed originator fixture", **{
                    "in": 0, "for": 60, "not_after": T0 + 60_000})
                _, abandoned = await asyncio.open_unix_connection(control)
                abandoned.write((json.dumps(req) + "\n").encode())
                await abandoned.drain()
                for _ in range(100):
                    receipt = await send({"op": "cue_show", "id": "delayed"})
                    if receipt.get("ok") and receipt["cue"]["state"] == "accepted":
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(receipt["cue"]["state"], "accepted")
                abandoned.close()
                await abandoned.wait_closed()
                abandoned = None

                clock[0] = T0 + 55_000
                recovered = await send(req)
                self.assertEqual(recovered["cue"], receipt["cue"])
                self.assertEqual(recovered["cue"]["ends_at"], T0 + 60_000)
                self.assertEqual(recovered["cue"]["acceptance"]["expires_at"], T0 + 60_000)
                deadline = asyncio.get_running_loop().time() + 2
                items = []
                while asyncio.get_running_loop().time() < deadline and not items:
                    try:
                        frame = await asyncio.wait_for(asyncio.get_running_loop().sock_recv(received, 1200), 0.2)
                    except asyncio.TimeoutError:
                        continue
                    if frame[3] == wire.KIND_ITEM:
                        items.append(wire.parse(frame, lambda _: PK).body)
                self.assertTrue(items)
                self.assertEqual(items[0].body, b"Delayed originator fixture")
                self.assertEqual(items[0].expires_at, T0 + 60_000)
                self.assertEqual(st.streams["weather"].head_seq, 1)

                expired = await send(request("expired-first", **{
                    "in": 0, "for": 60, "not_after": T0 + 49_000}))
                self.assertEqual(expired["cue"]["state"], "missed")
                self.assertIsNone(expired["cue"]["acceptance"])
                self.assertEqual(st.streams["weather"].head_seq, 1)
                clock[0] = T0 + 60_000
                for _ in range(100):
                    ended = await send({"op": "cue_show", "id": "delayed"})
                    if ended["cue"]["state"] == "ended":
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(ended["cue"]["state"], "ended")
                self.assertFalse(any(o.kind == wire.KIND_ITEM for o in st.streams["weather"].ring.values()))
            finally:
                if abandoned is not None:
                    abandoned.close()
                    await abandoned.wait_closed()
                stop.set()
                try:
                    await task
                finally:
                    received.close()
                    db.close()

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
