from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle_receptor import (
    MAX_PACKET_SIZE,
    AcceptReceipt,
    IssuerPolicy,
    Notice,
    NoticeKind,
    NoticeReceptor,
    QuarantineReceipt,
    ReceptorState,
    RejectReceipt,
    encode_signed_notice,
)
from canticle_receptor._publisher import PublisherUnavailable
from canticle_receptor.model import (
    QuarantineReason,
    RejectReason,
    VerifiedNotice,
)

NOW = 2_000_000_000
SUBJECT = "sha256:" + ("a" * 64)


class RecordingPublisher:
    def __init__(self) -> None:
        self.notices: list[VerifiedNotice] = []

    def publish(self, notice: VerifiedNotice) -> None:
        self.notices.append(notice)


class UnavailablePublisher:
    def publish(self, notice: VerifiedNotice) -> None:
        del notice
        raise PublisherUnavailable


class ReceptorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.state_path = Path(self.temporary_directory.name) / "state.sqlite3"
        self.private_key = Ed25519PrivateKey.generate()
        self.publisher = RecordingPublisher()
        self.state = ReceptorState(self.state_path)
        self.addCleanup(self.state.close)
        self.receptor = self._receptor()

    def _receptor(
        self,
        *,
        quarantined: bool = False,
        publisher: RecordingPublisher | UnavailablePublisher | None = None,
        state: ReceptorState | None = None,
    ) -> NoticeReceptor:
        return NoticeReceptor(
            issuers={
                "issuer-a": IssuerPolicy(
                    keys={"key-a": self.private_key.public_key()},
                    quarantined=quarantined,
                )
            },
            state=state or self.state,
            publisher=publisher or self.publisher,
            clock=lambda: NOW,
        )

    def _packet(
        self,
        *,
        notice_id: str = "1" * 32,
        kind: NoticeKind = NoticeKind.AVAILABLE,
        subject: str = SUBJECT,
        issued_at: int = NOW,
        expires_at: int = NOW + 30,
        private_key: Ed25519PrivateKey | None = None,
        issuer: str = "issuer-a",
        key_id: str = "key-a",
    ) -> bytes:
        return encode_signed_notice(
            private_key or self.private_key,
            issuer=issuer,
            key_id=key_id,
            notice=Notice(
                kind=kind,
                subject=subject,
                notice_id=notice_id,
                issued_at=issued_at,
                expires_at=expires_at,
            ),
        )

    def test_accepts_valid_notice_and_hands_verified_type_to_publisher(self) -> None:
        receipt = self.receptor.process(self._packet())

        self.assertIsInstance(receipt, AcceptReceipt)
        self.assertEqual(len(self.publisher.notices), 1)
        self.assertIsInstance(self.publisher.notices[0], VerifiedNotice)
        self.assertEqual(self.publisher.notices[0].notice.kind, NoticeKind.AVAILABLE)

    def test_encoding_is_deterministic(self) -> None:
        first = self._packet(notice_id="c" * 32)
        second = self._packet(notice_id="c" * 32)

        self.assertEqual(first, second)

    def test_rejects_invalid_signature_without_publishing(self) -> None:
        receipt = self.receptor.process(
            self._packet(private_key=Ed25519PrivateKey.generate())
        )

        self.assertEqual(receipt, RejectReceipt(RejectReason.INVALID_SIGNATURE))
        self.assertEqual(self.publisher.notices, [])

    def test_rejects_expired_and_excessive_ttl_notices(self) -> None:
        expired = self.receptor.process(
            self._packet(notice_id="2" * 32, issued_at=NOW - 30, expires_at=NOW)
        )
        excessive = self.receptor.process(
            self._packet(notice_id="3" * 32, expires_at=NOW + 61)
        )

        self.assertEqual(expired, RejectReceipt(RejectReason.EXPIRED))
        self.assertEqual(excessive, RejectReceipt(RejectReason.TTL_EXCEEDED))
        self.assertEqual(self.publisher.notices, [])

    def test_rejects_invalid_and_future_timestamp_windows(self) -> None:
        invalid = self.receptor.process(
            self._packet(
                notice_id="d" * 32,
                issued_at=NOW,
                expires_at=NOW,
            )
        )
        future = self.receptor.process(
            self._packet(
                notice_id="e" * 32,
                issued_at=NOW + 6,
                expires_at=NOW + 30,
            )
        )

        self.assertEqual(invalid, RejectReceipt(RejectReason.INVALID_TIMESTAMP))
        self.assertEqual(future, RejectReceipt(RejectReason.NOT_YET_VALID))
        self.assertEqual(self.publisher.notices, [])

    def test_rejects_replay(self) -> None:
        packet = self._packet()

        first = self.receptor.process(packet)
        second = self.receptor.process(packet)

        self.assertIsInstance(first, AcceptReceipt)
        self.assertEqual(second, RejectReceipt(RejectReason.REPLAY))
        self.assertEqual(len(self.publisher.notices), 1)

    def test_tombstone_blocks_later_notice_for_subject(self) -> None:
        tombstone = self.receptor.process(
            self._packet(kind=NoticeKind.TOMBSTONE, notice_id="4" * 32)
        )
        later = self.receptor.process(self._packet(notice_id="5" * 32))

        self.assertIsInstance(tombstone, AcceptReceipt)
        self.assertEqual(later, RejectReceipt(RejectReason.SUBJECT_TOMBSTONED))
        self.assertEqual(len(self.publisher.notices), 1)

    def test_rejects_oversized_malformed_and_noncanonical_packets(self) -> None:
        oversized = self.receptor.process(b"x" * (MAX_PACKET_SIZE + 1))
        malformed = self.receptor.process(b"{")
        canonical_packet = self._packet(notice_id="6" * 32)
        noncanonical_value = json.loads(canonical_packet)
        noncanonical = json.dumps(noncanonical_value, indent=1).encode()
        noncanonical_receipt = self.receptor.process(noncanonical)

        self.assertEqual(oversized, RejectReceipt(RejectReason.PACKET_TOO_LARGE))
        self.assertEqual(malformed, RejectReceipt(RejectReason.MALFORMED_PACKET))
        self.assertEqual(
            noncanonical_receipt,
            RejectReceipt(RejectReason.NON_CANONICAL_PACKET),
        )
        self.assertEqual(self.publisher.notices, [])

    def test_closed_schema_rejects_payload_fields_without_echoing_them(self) -> None:
        value = json.loads(self._packet(notice_id="7" * 32))
        value["notice"]["payload"] = "forbidden-value"
        packet = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()

        receipt = self.receptor.process(packet)

        self.assertIsInstance(receipt, RejectReceipt)
        self.assertNotIn("forbidden", repr(receipt))
        self.assertEqual(self.publisher.notices, [])

    def test_quarantines_policy_blocked_unknown_issuer_and_unknown_key(self) -> None:
        quarantined = self._receptor(quarantined=True).process(
            self._packet(
                notice_id="8" * 32,
                private_key=Ed25519PrivateKey.generate(),
            )
        )
        unknown = self.receptor.process(
            self._packet(notice_id="9" * 32, issuer="issuer-b")
        )
        unknown_key = self.receptor.process(
            self._packet(notice_id="f" * 32, key_id="key-b")
        )

        self.assertEqual(
            quarantined,
            QuarantineReceipt(QuarantineReason.ISSUER_QUARANTINED),
        )
        self.assertEqual(
            unknown,
            QuarantineReceipt(QuarantineReason.ISSUER_NOT_ALLOWED),
        )
        self.assertEqual(
            unknown_key,
            QuarantineReceipt(QuarantineReason.KEY_NOT_ALLOWED),
        )
        self.assertEqual(self.publisher.notices, [])

    def test_quarantines_when_bounded_state_caches_are_full(self) -> None:
        bounded_replay = ReceptorState(
            Path(self.temporary_directory.name) / "bounded-replay.sqlite3",
            max_replay_entries=1,
        )
        self.addCleanup(bounded_replay.close)
        replay_receptor = self._receptor(state=bounded_replay)
        replay_receptor.process(self._packet(notice_id="0" * 32))

        replay_full = replay_receptor.process(
            self._packet(
                notice_id="1" * 31 + "0",
                subject="sha256:" + ("b" * 64),
            )
        )

        bounded_tombstones = ReceptorState(
            Path(self.temporary_directory.name) / "bounded-tombstones.sqlite3",
            max_tombstones=1,
        )
        self.addCleanup(bounded_tombstones.close)
        tombstone_receptor = self._receptor(state=bounded_tombstones)
        tombstone_receptor.process(
            self._packet(
                notice_id="2" * 31 + "0",
                kind=NoticeKind.TOMBSTONE,
            )
        )
        tombstone_full = tombstone_receptor.process(
            self._packet(
                notice_id="3" * 31 + "0",
                kind=NoticeKind.TOMBSTONE,
                subject="sha256:" + ("b" * 64),
            )
        )

        self.assertEqual(
            replay_full,
            QuarantineReceipt(QuarantineReason.REPLAY_CACHE_FULL),
        )
        self.assertEqual(
            tombstone_full,
            QuarantineReceipt(QuarantineReason.TOMBSTONE_CACHE_FULL),
        )

    def test_quarantines_publisher_failure_without_retrying_claim(self) -> None:
        packet = self._packet(notice_id="a" * 32)
        unavailable = self._receptor(publisher=UnavailablePublisher())

        first = unavailable.process(packet)
        second = unavailable.process(packet)

        self.assertEqual(
            first,
            QuarantineReceipt(QuarantineReason.PUBLISHER_UNAVAILABLE),
        )
        self.assertEqual(second, RejectReceipt(RejectReason.REPLAY))

    def test_replay_dedup_survives_receptor_restart(self) -> None:
        packet = self._packet(notice_id="b" * 32)
        first = self.receptor.process(packet)
        self.state.close()

        restarted_state = ReceptorState(self.state_path)
        self.addCleanup(restarted_state.close)
        restarted = self._receptor(state=restarted_state)
        second = restarted.process(packet)

        self.assertIsInstance(first, AcceptReceipt)
        self.assertEqual(second, RejectReceipt(RejectReason.REPLAY))


if __name__ == "__main__":
    unittest.main()
