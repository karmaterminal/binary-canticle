"""Real Station/Listener effect proof, with synthetic host authority and no host/plugin bridge."""

import hashlib
import os
import socket
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import vectors, wire
from canticle.derived_reply_proposal import Exposure, Grant, HistoryOrigin, Intent, Reader, Refused, ReplyProposal
from canticle.derived_station_proposal import DerivedStationProposal
from canticle.ids import CLASS_BY_NAME, SCOPES
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.station import NotGranted, Station, StreamConfig


class StationProposalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "authority.db"
        self.now = 1_790_000_000_000
        self.sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(vectors.TEST1))
        self.pub = wire.public_key_bytes(self.sk)
        self.entry = StationEntry("rune", self.pub, frozenset({CLASS_BY_NAME["chatter"].code}),
                                  streams=("town.reply",), scopes=frozenset({SCOPES["lan"]}))
        self.reader = Reader("rune", "agent:rune:subagent:reader", "reader-id", "revision-1")
        self.recipient = Reader("silas", "agent:silas:subagent:reader", "recipient-id", "revision-1")
        self.grant = Grant("rune", "rune", self.entry.key_id.hex(), "town.reply", ("rune",), ("silas",),
                           self.pub.hex())
        self.intent = Intent("rune", "rune", self.entry.key_id.hex(), "town.reply", (self.recipient,),
                             self.pub.hex())
        self.body = b"The parcel arrived, but now it hums."
        self.proposal = self.reopen()
        self.proposal.set_current_reader(self.reader)
        self.proposal.set_current_reader(self.recipient)
        self.proposal.attest_history(self.reader, HistoryOrigin(
            "host-observed-birth", "observed_session_birth", 0, hashlib.sha256(b"[]").hexdigest()))
        self.station = self.new_station()
        self.adapter = DerivedStationProposal(self.proposal, self.station, "rune", enabled=True)
        self.listener = Listener(Manifest([self.entry]), state_path=Path(self.tmp.name) / "listener.json")

    def reopen(self):
        return ReplyProposal(self.path, enabled=True, secret=b"synthetic-host-capability-secret-32",
                             grant=self.grant, content_allowed=lambda _: True, clock=lambda: self.now)

    def new_station(self, **kw):
        return Station(self.sk, [StreamConfig("town.reply")],
                       **{**dict(epoch=7, now_ms=self.now, grant=self.entry, derived_proposals=True), **kw})

    def expose(self, n=1, **kw):
        source = Exposure(**{**dict(receipt_id=f"exposure-{n}", binding="rune-reader",
                                  reader_decision=f"allowed-read-{n}", item=(f"{n:016x}", 7, 5, n),
                                  root=None, hop=0, drained_at=self.now, expires_at=self.now + 240_000),
                             **kw})
        self.proposal.record_exposure(self.reader, source)
        return source

    def elect(self):
        eid = self.proposal.elect(self.reader, author="rune", turn_id="turn-1", choice_id="choice-1",
                                  exposure_receipt="exposure-1", payload=self.body, intent=self.intent)
        return eid, self.proposal.claim(eid, self.body)

    def prepared(self):
        self.expose()
        return self.elect()

    def refused(self, reason, fn):
        with self.assertRaises(Refused) as cm:
            fn()
        self.assertEqual(cm.exception.reason, reason)

    def items(self):
        return [frame for frame in self.station.poll(self.now) if frame[3] == wire.KIND_ITEM]

    def test_default_gates_create_no_effect_and_do_not_consume_a_claim(self):
        eid, capsule = self.prepared()
        self.refused("disabled", lambda: DerivedStationProposal(self.proposal, self.station, "rune").publish(capsule, self.body))
        closed = Station(self.sk, [StreamConfig("town.reply")], epoch=7, now_ms=self.now, grant=self.entry)
        self.refused("disabled", lambda: DerivedStationProposal(self.proposal, closed, "rune", enabled=True).publish(capsule, self.body))
        self.assertEqual(self.proposal.inspect(eid)["state"], "claimed_unknown")
        self.assertEqual(self.items(), [])

    def test_read_then_quiet_is_no_station_operation(self):
        self.expose()
        self.now += 20_000
        self.assertEqual(self.items(), [])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM station_effects").fetchone()[0], 0)

    def test_real_station_signs_lineage_and_real_listener_verifies_exact_bytes(self):
        # The chosen display parent is exposure-1. Maximum hop must also include a non-chosen
        # earlier source, and parents/root must follow the final four of the complete history.
        first = self.expose(1, hop=1)
        for n in range(2, 7):
            self.expose(n, wake_derived=None if n == 3 else False)
        eid, capsule = self.elect()
        with patch.object(self.station, "sing", side_effect=AssertionError("ordinary sing laundering")):
            receipt = self.adapter.publish(capsule, self.body)
        frames = self.station.poll(self.now)
        events = [event for frame in frames for event in self.listener.hear(frame, self.now)]
        items = [frame for frame in frames if frame[3] == wire.KIND_ITEM]
        self.assertEqual(len(items), 1)
        parsed = wire.parse(items[0], Manifest([self.entry]).resolve, self.now).body
        self.assertEqual(parsed.body, self.body)
        self.assertEqual(parsed.hop, 2)
        self.assertEqual([x[3] for x in parsed.derived_from], [3, 4, 5, 6])
        self.assertEqual(parsed.root, (bytes.fromhex(f"{3:016x}"), 7, 5, 3))
        self.assertEqual(parsed.flags, wire.Item.WAKE_DERIVED)
        self.assertNotIn(first.item[3], [x[3] for x in parsed.derived_from])
        surfaced = [event for event in events if event.kind == "item"]
        self.assertEqual(len(surfaced), 1)
        self.assertEqual(surfaced[0].data["text"].encode(), self.body)
        self.assertEqual(receipt["frame_sha256"], hashlib.sha256(items[0]).hexdigest())
        self.assertEqual(receipt["reader_generation"], self.reader.generation)
        self.assertEqual(receipt["history_count"], 6)
        self.assertEqual(receipt["exposure_receipt"], "exposure-1")
        self.assertEqual(receipt["public_key"], self.pub.hex())
        self.assertEqual(self.adapter.query(eid)["acceptance"], receipt)
        self.assertEqual([r["kind"] for r in self.proposal.inspect(eid)["outcomes"]], ["station_acceptance"])
        # A listener encounter is not fabricated into an actual host/session exposure receipt.

    def test_loopback_udp_reaches_signature_verifying_listener(self):
        eid, capsule = self.prepared()
        receipt = self.adapter.publish(capsule, self.body)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rx, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as tx:
            try:
                rx.bind(("127.0.0.1", 0))
            except PermissionError:
                if os.environ.get("CI"):
                    raise  # CI must prove transport, never silently skip it
                self.skipTest("sandbox forbids loopback UDP; CI requires the real transport proof")
            rx.settimeout(2)
            frames = self.station.poll(self.now)
            for frame in frames:
                tx.sendto(frame, rx.getsockname())
            events = []
            for _ in frames:
                datagram, _ = rx.recvfrom(2048)
                events.extend(self.listener.hear(datagram, self.now))
        surfaced = [event for event in events if event.kind == "item"]
        self.assertEqual(len(surfaced), 1)
        self.assertEqual(surfaced[0].data["text"].encode(), self.body)
        self.assertEqual(self.adapter.query(eid)["acceptance"], receipt)

    def test_competing_redemptions_commit_once(self):
        eid, capsule = self.prepared()
        def attempt(_):
            adapter = DerivedStationProposal(self.reopen(), self.station, "rune", enabled=True)
            try:
                return adapter.publish(capsule, self.body)
            except Refused as e:
                return e.reason
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(8)))
        self.assertEqual(sum(isinstance(x, dict) for x in results), 1)
        self.assertEqual(results.count("claim_consumed"), 7)
        self.assertEqual(len(self.items()), 1)
        self.assertEqual(self.adapter.query(eid)["state"], "accepted")

    def test_restart_after_claim_before_effect_stays_unknown_without_resend(self):
        eid, capsule = self.prepared()
        with patch.object(self.adapter, "_apply_claim", side_effect=RuntimeError("crash before effect")):
            with self.assertRaisesRegex(RuntimeError, "crash before"):
                self.adapter.publish(capsule, self.body)
        recovered = DerivedStationProposal(self.reopen(), self.new_station(), "rune", enabled=True)
        self.assertEqual(recovered.query(eid), {"election_id": eid, "state": "claimed_unknown", "acceptance": None})
        self.refused("claim_consumed", lambda: recovered.publish(capsule, self.body))
        self.assertEqual(self.items(), [])

    def test_lost_result_after_effect_recovers_immutable_acceptance_without_resend(self):
        eid, capsule = self.prepared()
        receipt = self.adapter.publish(capsule, self.body)  # discard the transport result
        recovered = DerivedStationProposal(self.reopen(), self.new_station(), "rune", enabled=True)
        self.assertEqual(recovered.query(eid)["acceptance"], receipt)
        self.refused("claim_consumed", lambda: recovered.publish(capsule, self.body))
        self.assertEqual(len(self.items()), 1)
        self.assertEqual([f for f in recovered.station.poll(self.now) if f[3] == wire.KIND_ITEM], [])

    def test_receipt_write_failure_after_actual_effect_remains_unknown_and_never_retries(self):
        eid, capsule = self.prepared()
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TRIGGER fail_acceptance BEFORE UPDATE ON station_effects "
                       "BEGIN SELECT RAISE(ABORT, 'receipt failure'); END")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "receipt failure"):
            self.adapter.publish(capsule, self.body)
        self.assertEqual(len(self.items()), 1)
        recovered = DerivedStationProposal(self.reopen(), self.new_station(), "rune", enabled=True)
        self.assertEqual(recovered.query(eid)["state"], "claimed_unknown")
        self.assertIsNone(recovered.query(eid)["acceptance"])
        self.refused("claim_consumed", lambda: recovered.publish(capsule, self.body))
        self.assertEqual(self.proposal.inspect(eid)["outcomes"], [])

    def test_replaced_signer_with_same_key_id_is_refused_at_actual_mutation(self):
        eid, capsule = self.prepared()
        apply = self.adapter._apply_claim
        def replace_signer(admission, body):
            self.station.sk = Ed25519PrivateKey.generate()
            # Deliberately leave the station's 64-bit ID unchanged: a key-id-only guard would pass.
            return apply(admission, body)
        with patch.object(self.adapter, "_apply_claim", side_effect=replace_signer):
            with self.assertRaisesRegex(NotGranted, "signer changed"):
                self.adapter.publish(capsule, self.body)
        self.assertEqual(self.station.streams["town.reply"].head_seq, 0)
        self.assertEqual(self.adapter.query(eid)["state"], "claimed_unknown")

    def test_manifest_revocation_between_claim_and_effect_refuses(self):
        _, capsule = self.prepared()
        apply = self.adapter._apply_claim
        def revoke(admission, body):
            self.station.grant = replace(self.entry, revoked=True)
            return apply(admission, body)
        with patch.object(self.adapter, "_apply_claim", side_effect=revoke):
            with self.assertRaises(NotGranted):
                self.adapter.publish(capsule, self.body)
        self.assertEqual(self.items(), [])

    def test_withdrawal_and_generation_change_after_claim_are_rechecked_before_effect(self):
        for change, reason in ((lambda: self.proposal.withdraw_or_mute(self.reader, "exposure-1"), "source_unavailable"),
                               (lambda: self.proposal.set_current_reader(replace(self.recipient, session_id="replaced")), "reader_generation")):
            with self.subTest(reason=reason):
                self.setUp()
                _, capsule = self.prepared()
                apply = self.adapter._apply_claim
                def invalidate(admission, body):
                    change()
                    return apply(admission, body)
                with patch.object(self.adapter, "_apply_claim", side_effect=invalidate):
                    self.refused(reason, lambda: self.adapter.publish(capsule, self.body))
                self.assertEqual(self.items(), [])

    def test_new_exposure_after_claim_closes_mutation(self):
        _, capsule = self.prepared()
        apply = self.adapter._apply_claim
        def hear_another(admission, body):
            self.expose(2, hop=1)
            return apply(admission, body)
        with patch.object(self.adapter, "_apply_claim", side_effect=hear_another):
            self.refused("ledger_changed", lambda: self.adapter.publish(capsule, self.body))
        self.assertEqual(self.items(), [])

    def test_tightened_turn_and_hour_budgets_are_rechecked_at_effect(self):
        for limits in ({"per_turn": 1}, {"per_hour": 1}):
            with self.subTest(limits=limits):
                self.setUp()
                eid, capsule = self.prepared()
                other_body = b"Another deliberately elected note."
                other = self.proposal.elect(self.reader, author="rune", turn_id="turn-1", choice_id="choice-2",
                                           exposure_receipt="exposure-1", payload=other_body, intent=self.intent)
                self.proposal.claim(other, other_body)
                apply = self.adapter._apply_claim
                def tighten(admission, body):
                    self.proposal.replace_grant(replace(self.grant, **limits))
                    return apply(admission, body)
                with patch.object(self.adapter, "_apply_claim", side_effect=tighten):
                    self.refused("budget", lambda: self.adapter.publish(capsule, self.body))
                self.assertEqual(self.items(), [])
                self.assertEqual(self.adapter.query(eid)["state"], "claimed_unknown")
                self.refused("claim_consumed", lambda: self.adapter.publish(capsule, self.body))

    def test_deadline_after_claim_does_not_allocate_a_sequence(self):
        eid, capsule = self.prepared()
        apply = self.adapter._apply_claim
        def delay(admission, body):
            self.now += 30_000
            return apply(admission, body)
        with patch.object(self.adapter, "_apply_claim", side_effect=delay):
            self.refused("expired", lambda: self.adapter.publish(capsule, self.body))
        self.assertEqual(self.station.streams["town.reply"].head_seq, 0)
        self.assertIsNone(self.adapter.query(eid)["acceptance"])

    def test_station_ttl_cap_only_shortens_the_original_absolute_expiry(self):
        eid, capsule = self.prepared()
        self.station.streams["town.reply"].cfg.default_ttl_s = 10
        receipt = self.adapter.publish(capsule, self.body)
        self.assertEqual(receipt["item_expires_at"], self.now + 10_000)
        frame = self.items()[0]
        self.assertEqual(wire.parse(frame, Manifest([self.entry]).resolve, self.now).body.expires_at, self.now + 10_000)
        self.now += 20_000
        self.assertEqual(self.items(), [])
        self.assertEqual(self.adapter.query(eid)["acceptance"], receipt)

    def test_capability_full_key_and_payload_tampering_fail_before_effect(self):
        _, capsule = self.prepared()
        self.refused("payload_changed", lambda: self.adapter.publish(capsule, b"Different words"))
        self.refused("capability_auth", lambda: self.adapter.publish(
            capsule.replace(self.pub.hex().encode(), b"0" * 64), self.body))
        self.assertEqual(self.items(), [])

