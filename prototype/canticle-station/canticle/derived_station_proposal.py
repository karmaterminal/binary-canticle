"""Default-closed, unregistered #146 host-to-station candidate.

This library proves the actual Station signing/carousel boundary under synthetic host authority.
It is not a CLI/control operation or a complete OpenClaw/frond-ear bridge. The authority database
must remain host-owned. The actual host exposure ledger, capability provisioning and egress policy
still require the owners' adopted contract. See the proposal note before using this review code.
"""

from __future__ import annotations

import hashlib
import json

from . import wire
from .derived_reply_proposal import Admission, Refused, ReplyProposal, _json, _require, proposed_item
from .station import Station


class DerivedStationProposal:
    """Single station owner; its normal loop serializes all Station mutations and polling.

    The adapter's lock also serializes competing candidate calls on this Station. SQLite serializes
    generation, history, policy and claim changes across adapters/processes. A committed claim is
    never retried, even if no station effect can later be proved. Recovery is query-only.
    """

    def __init__(self, proposal: ReplyProposal, station: Station, name: str, *, enabled: bool = False):
        self.proposal, self.station, self.name, self.enabled = proposal, station, name, enabled is True

    def publish(self, capsule: bytes, payload: bytes) -> dict:
        _require(self.enabled and self.station._derived_proposals, "disabled")
        with self.station._derived_proposal_lock:
            # Durable admission/claim BEFORE an effect. This verifies the capsule, exact current
            # ledger, generations, authority, payload and actual full signer public key. A crash
            # after here is unknown; neither another process nor a restarted owner may re-enqueue.
            admission = self.proposal.station_admit(
                capsule, payload, station=self.name, key_id=self.station.key_id.hex(),
                public_key=wire.public_key_bytes(self.station.sk).hex())
            return self._apply_claim(admission, payload)

    def _apply_claim(self, admission: Admission, payload: bytes) -> dict:
        # No await/network between the final checks and mutation. The same writer lock prevents
        # a new exposure, withdrawal, generation or policy change from passing those checks.
        with self.proposal._tx() as db:
            row = db.execute("SELECT * FROM elections WHERE id=?", (admission.election_id,)).fetchone()
            effect = db.execute("SELECT state FROM station_effects WHERE election_id=?",
                                (admission.election_id,)).fetchone()
            _require(row is not None and row["state"] == "admitted_unknown" and effect is not None
                     and effect["state"] == "claimed_unknown" and row["envelope"] == admission.envelope.decode(),
                     "claim_consumed")
            reader, intent, snapshot, grant = self.proposal._check_election(db, row, payload, self.proposal._now())
            _require(intent["station"] == self.name, "wrong_station")
            now = self.proposal._now()
            self.proposal._redemption_budget(db, row, grant, now)
            item = proposed_item(admission, payload, epoch=self.station.epoch,
                                 seq=self.station._stream(intent["stream"]).head_seq + 1, now=now)
            result = self.station._accept_derived_proposal(
                now, intent["stream"], item, expected_public_key=bytes.fromhex(intent["public_key"]))
            # Acceptance is only signing + admission to this carousel. No network or recipient
            # claim is made. This immutable receipt is durable before it can be returned.
            frame = self.station._stream(intent["stream"]).ring[result.seq].frame
            receipt = {
                "v": "canticle-derived-station-acceptance/1", "election_id": admission.election_id,
                "reader_generation": reader.generation, "history_digest": snapshot["digest"],
                "history_count": snapshot["count"], "exposure_receipt": row["citation"],
                "payload_sha256": row["payload_sha256"], "station": self.name,
                "public_key": intent["public_key"], "key_id": intent["key_id"],
                "frame_sha256": hashlib.sha256(frame).hexdigest(),
                "epoch": str(result.epoch), "stream": intent["stream"], "seq": str(result.seq),
                "accepted_at": now, "item_expires_at": result.expires_at,
                "hop": item.hop, "wake_derived": bool(item.flags & wire.Item.WAKE_DERIVED),
            }
            encoded = _json(receipt).decode()
            db.execute("UPDATE station_effects SET state='accepted',receipt=? WHERE election_id=?",
                       (encoded, admission.election_id))
            db.execute("INSERT INTO outcomes VALUES (?, 'station_acceptance', ?)",
                       (admission.election_id, "station-acceptance:" + hashlib.sha256(encoded.encode()).hexdigest()))
        return receipt

    def query(self, election_id: str) -> dict:
        """No send, refresh or retry. Absence/ambiguity never proves an item was not emitted."""
        _require(self.enabled, "disabled")
        db = self.proposal._db()
        try:
            row = db.execute("SELECT state,receipt FROM station_effects WHERE election_id=?",
                             (election_id,)).fetchone()
            if row is None:
                raise Refused("station_claim_missing")
            return {"election_id": election_id, "state": row["state"],
                    "acceptance": json.loads(row["receipt"]) if row["receipt"] is not None else None}
        finally:
            db.close()
