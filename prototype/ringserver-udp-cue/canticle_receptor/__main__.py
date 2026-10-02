from __future__ import annotations

import argparse
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .model import VerifiedNotice
from .receptor import IssuerPolicy, NoticeReceptor
from .state import ReceptorState
from .udp import UdpCueListener


class _ReceiptOnlyPublisher:
    def publish(self, notice: VerifiedNotice) -> None:
        del notice


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the localhost Binary Canticle UDP-cue receptor prototype."
    )
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--public-key-hex", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9999)
    parser.add_argument("--once", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        public_key = Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(args.public_key_hex)
        )
    except ValueError:
        print("invalid public key", file=sys.stderr)
        return 2

    state = ReceptorState(args.state)
    receptor = NoticeReceptor(
        issuers={
            args.issuer: IssuerPolicy(keys={args.key_id: public_key}),
        },
        state=state,
        publisher=_ReceiptOnlyPublisher(),
    )
    try:
        with UdpCueListener(receptor, host=args.host, port=args.port) as listener:
            if args.once:
                receipt = listener.receive_once()
                print(receipt.decision, receipt.reason)
            else:
                listener.serve_forever(
                    on_receipt=lambda receipt: print(
                        receipt.decision,
                        receipt.reason,
                        flush=True,
                    )
                )
    except KeyboardInterrupt:
        return 0
    finally:
        state.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
