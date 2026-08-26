from __future__ import annotations

import socket
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle_receptor import (
    AcceptReceipt,
    IssuerPolicy,
    Notice,
    NoticeKind,
    NoticeReceptor,
    ReceptorState,
    UdpCueListener,
    encode_signed_notice,
)
from canticle_receptor.model import VerifiedNotice

NOW = 2_000_000_000


class RecordingPublisher:
    def __init__(self) -> None:
        self.notices: list[VerifiedNotice] = []

    def publish(self, notice: VerifiedNotice) -> None:
        self.notices.append(notice)


class UdpListenerTest(unittest.TestCase):
    def test_localhost_datagram_reaches_private_publisher_seam(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            key = Ed25519PrivateKey.generate()
            publisher = RecordingPublisher()
            state = ReceptorState(Path(directory) / "state.sqlite3")
            self.addCleanup(state.close)
            receptor = NoticeReceptor(
                issuers={
                    "issuer-a": IssuerPolicy(keys={"key-a": key.public_key()}),
                },
                state=state,
                publisher=publisher,
                clock=lambda: NOW,
            )
            packet = encode_signed_notice(
                key,
                issuer="issuer-a",
                key_id="key-a",
                notice=Notice(
                    kind=NoticeKind.AVAILABLE,
                    subject="sha256:" + ("c" * 64),
                    notice_id="c" * 32,
                    issued_at=NOW,
                    expires_at=NOW + 30,
                ),
            )

            with UdpCueListener(receptor, port=0) as listener:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    sender.sendto(packet, listener.address)
                receipt = listener.receive_once(timeout=1)

            self.assertIsInstance(receipt, AcceptReceipt)
            self.assertEqual(len(publisher.notices), 1)

    def test_listener_refuses_non_loopback_bind(self) -> None:
        with self.assertRaisesRegex(ValueError, "listener_must_be_ipv4_loopback"):
            UdpCueListener(object(), host="0.0.0.0")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
