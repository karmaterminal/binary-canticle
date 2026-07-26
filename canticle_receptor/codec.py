from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .model import Notice, NoticeKind, RejectReason

MAX_PACKET_SIZE = 1200
MAX_NOTICE_SIZE = 512
PROTOCOL_VERSION = 1

_IDENTIFIER = re.compile(r"[a-z][a-z0-9.-]{0,62}\Z")
_NOTICE_ID = re.compile(r"[0-9a-f]{32}\Z")
_SUBJECT = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TOP_LEVEL_FIELDS = frozenset({"version", "issuer", "key_id", "notice", "signature"})
_NOTICE_FIELDS = frozenset({"kind", "subject", "notice_id", "issued_at", "expires_at"})


class EnvelopeError(ValueError):
    def __init__(self, reason: RejectReason):
        super().__init__(reason.value)
        self.reason = reason


class _DuplicateField(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParsedEnvelope:
    issuer: str
    key_id: str
    notice: Notice
    signature: bytes
    signed_bytes: bytes


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateField
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]{86}", value):
        raise EnvelopeError(RejectReason.MALFORMED_PACKET)
    try:
        decoded = base64.b64decode(value + "==", altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as error:
        raise EnvelopeError(RejectReason.MALFORMED_PACKET) from error
    if len(decoded) != 64 or _b64url_encode(decoded) != value:
        raise EnvelopeError(RejectReason.MALFORMED_PACKET)
    return decoded


def _notice_dict(notice: Notice) -> dict[str, object]:
    return {
        "expires_at": notice.expires_at,
        "issued_at": notice.issued_at,
        "kind": notice.kind.value,
        "notice_id": notice.notice_id,
        "subject": notice.subject,
    }


def _unsigned_dict(issuer: str, key_id: str, notice: Notice) -> dict[str, object]:
    return {
        "issuer": issuer,
        "key_id": key_id,
        "notice": _notice_dict(notice),
        "version": PROTOCOL_VERSION,
    }


def encode_signed_notice(
    private_key: Ed25519PrivateKey,
    *,
    issuer: str,
    key_id: str,
    notice: Notice,
) -> bytes:
    unsigned = _unsigned_dict(issuer, key_id, notice)
    signed_bytes = canonical_json(unsigned)
    envelope = dict(unsigned)
    envelope["signature"] = _b64url_encode(private_key.sign(signed_bytes))
    packet = canonical_json(envelope)
    if len(canonical_json(_notice_dict(notice))) > MAX_NOTICE_SIZE:
        raise ValueError("notice_too_large")
    if len(packet) > MAX_PACKET_SIZE:
        raise ValueError("packet_too_large")
    return packet


def parse_packet(packet: bytes) -> ParsedEnvelope:
    if len(packet) > MAX_PACKET_SIZE:
        raise EnvelopeError(RejectReason.PACKET_TOO_LARGE)

    try:
        text = packet.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateField, ValueError) as error:
        raise EnvelopeError(RejectReason.MALFORMED_PACKET) from error

    if not isinstance(value, dict) or canonical_json(value) != packet:
        raise EnvelopeError(RejectReason.NON_CANONICAL_PACKET)
    if set(value) != _TOP_LEVEL_FIELDS:
        raise EnvelopeError(RejectReason.MALFORMED_PACKET)
    if type(value["version"]) is not int or value["version"] != PROTOCOL_VERSION:
        raise EnvelopeError(RejectReason.MALFORMED_PACKET)

    issuer = value["issuer"]
    key_id = value["key_id"]
    raw_notice = value["notice"]
    signature_text = value["signature"]
    if (
        not isinstance(issuer, str)
        or _IDENTIFIER.fullmatch(issuer) is None
        or not isinstance(key_id, str)
        or _IDENTIFIER.fullmatch(key_id) is None
        or not isinstance(raw_notice, dict)
        or not isinstance(signature_text, str)
    ):
        raise EnvelopeError(RejectReason.MALFORMED_PACKET)
    if set(raw_notice) != _NOTICE_FIELDS:
        raise EnvelopeError(RejectReason.MALFORMED_PACKET)
    if len(canonical_json(raw_notice)) > MAX_NOTICE_SIZE:
        raise EnvelopeError(RejectReason.PACKET_TOO_LARGE)

    kind = raw_notice["kind"]
    subject = raw_notice["subject"]
    notice_id = raw_notice["notice_id"]
    issued_at = raw_notice["issued_at"]
    expires_at = raw_notice["expires_at"]
    if (
        not isinstance(kind, str)
        or kind not in {member.value for member in NoticeKind}
        or not isinstance(subject, str)
        or _SUBJECT.fullmatch(subject) is None
        or not isinstance(notice_id, str)
        or _NOTICE_ID.fullmatch(notice_id) is None
        or type(issued_at) is not int
        or type(expires_at) is not int
        or issued_at < 0
        or expires_at < 0
        or issued_at > 2**63 - 1
        or expires_at > 2**63 - 1
    ):
        raise EnvelopeError(RejectReason.MALFORMED_PACKET)

    notice = Notice(
        kind=NoticeKind(kind),
        subject=subject,
        notice_id=notice_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    unsigned = _unsigned_dict(issuer, key_id, notice)
    return ParsedEnvelope(
        issuer=issuer,
        key_id=key_id,
        notice=notice,
        signature=_b64url_decode(signature_text),
        signed_bytes=canonical_json(unsigned),
    )
