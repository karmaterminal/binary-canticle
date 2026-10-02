from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ._publisher import DataLinkPublisher, PublisherUnavailable
from .codec import EnvelopeError, parse_packet
from .model import (
    AcceptReceipt,
    QuarantineReason,
    QuarantineReceipt,
    Receipt,
    RejectReason,
    RejectReceipt,
    VerifiedNotice,
)
from .state import ClaimOutcome, ReceptorState

MAX_TTL_SECONDS = 60
MAX_FUTURE_SKEW_SECONDS = 5


@dataclass(frozen=True, slots=True)
class IssuerPolicy:
    keys: Mapping[str, Ed25519PublicKey]
    quarantined: bool = False


class NoticeReceptor:
    def __init__(
        self,
        *,
        issuers: Mapping[str, IssuerPolicy],
        state: ReceptorState,
        publisher: DataLinkPublisher,
        clock: Callable[[], float] = time.time,
    ):
        self._issuers = dict(issuers)
        self._state = state
        self._publisher = publisher
        self._clock = clock

    def process(self, packet: bytes) -> Receipt:
        try:
            envelope = parse_packet(packet)
        except EnvelopeError as error:
            return RejectReceipt(error.reason)

        issuer_policy = self._issuers.get(envelope.issuer)
        if issuer_policy is None:
            return QuarantineReceipt(QuarantineReason.ISSUER_NOT_ALLOWED)
        if issuer_policy.quarantined:
            return QuarantineReceipt(QuarantineReason.ISSUER_QUARANTINED)
        public_key = issuer_policy.keys.get(envelope.key_id)
        if public_key is None:
            return QuarantineReceipt(QuarantineReason.KEY_NOT_ALLOWED)
        try:
            public_key.verify(envelope.signature, envelope.signed_bytes)
        except InvalidSignature:
            return RejectReceipt(RejectReason.INVALID_SIGNATURE)

        now = int(self._clock())
        notice = envelope.notice
        if notice.expires_at <= notice.issued_at:
            return RejectReceipt(RejectReason.INVALID_TIMESTAMP)
        if notice.expires_at - notice.issued_at > MAX_TTL_SECONDS:
            return RejectReceipt(RejectReason.TTL_EXCEEDED)
        if notice.issued_at > now + MAX_FUTURE_SKEW_SECONDS:
            return RejectReceipt(RejectReason.NOT_YET_VALID)
        if notice.expires_at <= now:
            return RejectReceipt(RejectReason.EXPIRED)

        claim = self._state.claim(notice, now)
        if claim is ClaimOutcome.REPLAY:
            return RejectReceipt(RejectReason.REPLAY)
        if claim is ClaimOutcome.SUBJECT_TOMBSTONED:
            return RejectReceipt(RejectReason.SUBJECT_TOMBSTONED)
        if claim is ClaimOutcome.REPLAY_CACHE_FULL:
            return QuarantineReceipt(QuarantineReason.REPLAY_CACHE_FULL)
        if claim is ClaimOutcome.TOMBSTONE_CACHE_FULL:
            return QuarantineReceipt(QuarantineReason.TOMBSTONE_CACHE_FULL)

        verified = VerifiedNotice(
            issuer=envelope.issuer,
            key_id=envelope.key_id,
            notice=notice,
        )
        try:
            self._publisher.publish(verified)
        except PublisherUnavailable:
            return QuarantineReceipt(QuarantineReason.PUBLISHER_UNAVAILABLE)
        return AcceptReceipt()
