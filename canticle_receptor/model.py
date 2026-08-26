from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, TypeAlias


class NoticeKind(StrEnum):
    AVAILABLE = "available"
    TOMBSTONE = "tombstone"


@dataclass(frozen=True, slots=True)
class Notice:
    kind: NoticeKind
    subject: str
    notice_id: str
    issued_at: int
    expires_at: int


@dataclass(frozen=True, slots=True)
class VerifiedNotice:
    issuer: str
    key_id: str
    notice: Notice


class RejectReason(StrEnum):
    PACKET_TOO_LARGE = "packet_too_large"
    MALFORMED_PACKET = "malformed_packet"
    NON_CANONICAL_PACKET = "non_canonical_packet"
    INVALID_SIGNATURE = "invalid_signature"
    INVALID_TIMESTAMP = "invalid_timestamp"
    TTL_EXCEEDED = "ttl_exceeded"
    NOT_YET_VALID = "not_yet_valid"
    EXPIRED = "expired"
    REPLAY = "replay"
    SUBJECT_TOMBSTONED = "subject_tombstoned"


class QuarantineReason(StrEnum):
    ISSUER_NOT_ALLOWED = "issuer_not_allowed"
    ISSUER_QUARANTINED = "issuer_quarantined"
    KEY_NOT_ALLOWED = "key_not_allowed"
    REPLAY_CACHE_FULL = "replay_cache_full"
    TOMBSTONE_CACHE_FULL = "tombstone_cache_full"
    PUBLISHER_UNAVAILABLE = "publisher_unavailable"


@dataclass(frozen=True, slots=True)
class AcceptReceipt:
    decision: Literal["accept"] = field(default="accept", init=False)
    reason: Literal["accepted"] = field(default="accepted", init=False)


@dataclass(frozen=True, slots=True)
class RejectReceipt:
    reason: RejectReason
    decision: Literal["reject"] = field(default="reject", init=False)


@dataclass(frozen=True, slots=True)
class QuarantineReceipt:
    reason: QuarantineReason
    decision: Literal["quarantine"] = field(default="quarantine", init=False)


Receipt: TypeAlias = AcceptReceipt | RejectReceipt | QuarantineReceipt
