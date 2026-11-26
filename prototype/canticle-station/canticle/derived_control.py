"""Authenticated, owner-configured control transport for the #146 candidate.

Only an already issued host capsule and its exact elected bytes cross this port.
The host owns exposure, election and capability provisioning. No model-callable
lineage, identity, policy, database-path or capability-creation inputs are added.
"""

import base64
import binascii
import os
import re

from .content_policy import secret_findings
from .derived_reply_proposal import MAX_CAPSULE_BYTES, Refused, _require
from .derived_station_proposal import DerivedStationProposal
from .station import Station

OPERATIONS = frozenset({"derived_publish", "derived_query"})
MAX_PAYLOAD_BYTES = 800


class DerivedControlBridge:
    def __init__(self, adapter: DerivedStationProposal):
        self.adapter = adapter

    def check_station(self, station: Station) -> None:
        _require(self.adapter.station is station, "station_instance")
        _require(self.adapter.enabled and self.adapter.proposal.enabled and station._derived_proposals, "disabled")

    def dispatch(self, station: Station, request: dict, peer_uid: int | None) -> dict:
        self.check_station(station)
        # The peer identity is supplied by the Unix server, never by request JSON.
        _require(type(peer_uid) is int and peer_uid == os.getuid(), "peer_identity")
        op = request.get("op")
        if op == "derived_publish":
            _require(set(request) == {"op", "capsule_b64", "text"}, "request_shape")
            encoded, text = request["capsule_b64"], request["text"]
            _require(isinstance(encoded, str) and 0 < len(encoded) <= 4 * ((MAX_CAPSULE_BYTES + 2) // 3)
                     and isinstance(text, str), "request_bounds")
            try:
                capsule = base64.b64decode(encoded, validate=True)
                payload = text.encode("utf-8")
            except (binascii.Error, ValueError, UnicodeError):
                raise Refused("request_encoding") from None
            _require(0 < len(capsule) <= MAX_CAPSULE_BYTES and 0 < len(payload) <= MAX_PAYLOAD_BYTES,
                     "request_bounds")
            findings = secret_findings(text)
            _require(not findings, "content_policy:" + ",".join(findings))
            # HMAC, immutable bytes/history/generations, full signer, policy and
            # durable one-use claim are rechecked by the existing effect adapter.
            acceptance = self.adapter.publish(capsule, payload)
            return {"ok": True, "acceptance": acceptance}
        if op == "derived_query":
            _require(set(request) == {"op", "election_id"}, "request_shape")
            election_id = request["election_id"]
            _require(isinstance(election_id, str) and re.fullmatch(r"[0-9a-f]{32}", election_id) is not None,
                     "election_identity")
            return {"ok": True, **self.adapter.query(election_id)}
        raise Refused("unknown_derived_operation")
