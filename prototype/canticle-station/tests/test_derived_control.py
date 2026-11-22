"""Actual control socket -> signed UDP -> Listener; host exposure remains a fixture."""

import asyncio
import base64
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from canticle import runner, wire
from canticle.content_policy import derived_text_allowed, secret_findings
from canticle.derived_control import DerivedControlBridge
from canticle.derived_reply_proposal import Exposure, Grant, HistoryOrigin, Intent, Reader, Refused, ReplyProposal
from canticle.derived_station_proposal import DerivedStationProposal
from canticle.ids import CLASS_BY_NAME, SCOPES
from canticle.listener import Listener
from canticle.manifest import Manifest, StationEntry
from canticle.station import Station, StreamConfig


class Fixture:
    def prepare(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = runner.now_ms()
        self.sk = Ed25519PrivateKey.generate()
        public = wire.public_key_bytes(self.sk)
        self.entry = StationEntry("writer", public, frozenset({CLASS_BY_NAME["chatter"].code}),
                                  ("town.reply",), scopes=frozenset({SCOPES["lan"]}))
        self.reader = Reader("reader", "agent:reader:subagent:lesson", "reader-id", "revision-1")
        self.recipient = Reader("recipient", "agent:recipient:subagent:lesson", "recipient-id", "revision-1")
        self.grant = Grant("writer", "writer", self.entry.key_id.hex(), "town.reply", ("reader",),
                           ("recipient",), public.hex())
        self.proposal = ReplyProposal(self.root / "authority.db", enabled=True,
                                      secret=b"disposable-test-authority-secret-32", issuer="test-host",
                                      grant=self.grant, content_allowed=derived_text_allowed)
        self.proposal.set_current_reader(self.reader)
        self.proposal.set_current_reader(self.recipient)
        self.proposal.attest_history(self.reader, HistoryOrigin(
            "fixture-origin", "observed_session_birth", 0, hashlib.sha256(b"[]").hexdigest()))
        source = Exposure("source-receipt", "fixture-binding", "fixture-decision", ("01" * 8, 1, 1, 1),
                          None, 0, self.now, self.now + 120_000)
        # Synthetic host origin and custody are explicit; this suite proves transport, not a prince.
        fence = self.proposal.begin_exposure(self.reader, source)
        self.proposal.confirm_exposure(self.reader, fence)
        self.station = Station(self.sk, [StreamConfig("town.reply")], epoch=7, now_ms=self.now,
                               grant=self.entry, derived_proposals=True)
        self.adapter = DerivedStationProposal(self.proposal, self.station, "writer", enabled=True)
        self.bridge = DerivedControlBridge(self.adapter)
        self.allowed = runner.socket_grant(self.station)
        self.intent = Intent("writer", "writer", self.entry.key_id.hex(), "town.reply", (self.recipient,), public.hex())
        self.body = "The baker is selling slices of the moon; the receipt says bread."

    def elect(self, body=None):
        text = self.body if body is None else body
        eid = self.proposal.elect(self.reader, author="reader", turn_id="turn-1", choice_id="choice-1",
                                  exposure_receipt="source-receipt", payload=text.encode(), intent=self.intent)
        capsule = self.proposal.claim(eid, text.encode())
        return eid, {"op": "derived_publish", "capsule_b64": base64.b64encode(capsule).decode(), "text": text}

    def dispatch(self, request, uid=None):
        return runner._dispatch(self.station, request, self.allowed,
                                derived_bridge=self.bridge, peer_uid=os.getuid() if uid is None else uid)


class DerivedControlTest(Fixture, unittest.TestCase):
    def setUp(self):
        self.prepare()

    def test_default_control_remains_closed(self):
        _, req = self.elect()
        self.assertFalse(runner._dispatch(self.station, req, self.allowed)["ok"])
        self.assertEqual(self.station.streams["town.reply"].head_seq, 0)

    def test_peer_identity_is_required_and_never_taken_from_json(self):
        _, req = self.elect()
        for uid in (None, os.getuid() + 1):
            with self.subTest(uid=uid), self.assertRaisesRegex(Refused, "peer_identity"):
                runner._dispatch(self.station, req, self.allowed, derived_bridge=self.bridge, peer_uid=uid)
        with self.assertRaisesRegex(Refused, "request_shape"):
            self.dispatch({**req, "peer_uid": os.getuid()})
        self.assertEqual(self.station.streams["town.reply"].head_seq, 0)

    def test_lineage_and_target_are_not_request_parameters(self):
        _, req = self.elect()
        for field in ("hop", "root", "station", "stream", "authority_db", "scope"):
            with self.subTest(field=field), self.assertRaisesRegex(Refused, "request_shape"):
                self.dispatch({**req, field: "attacker-choice"})
        self.assertEqual(self.station.streams["town.reply"].head_seq, 0)

    def test_bad_capsule_and_changed_elected_bytes_have_no_effect(self):
        _, req = self.elect()
        with self.assertRaises(Refused):
            self.dispatch({**req, "capsule_b64": base64.b64encode(b"{}").decode()})
        with self.assertRaises(Refused):
            self.dispatch({**req, "text": self.body + " changed"})
        self.assertEqual(self.station.streams["town.reply"].head_seq, 0)
        self.assertTrue(self.dispatch(req)["ok"])

    def test_socket_class_narrowing_and_station_identity_still_apply(self):
        _, req = self.elect()
        self.assertFalse(runner._dispatch(self.station, req, frozenset(), derived_bridge=self.bridge,
                                          peer_uid=os.getuid())["ok"])
        other = Station(self.sk, [StreamConfig("town.reply")], epoch=8, now_ms=self.now,
                        grant=self.entry, derived_proposals=True)
        with self.assertRaisesRegex(Refused, "station_instance"):
            runner._dispatch(other, req, self.allowed, derived_bridge=self.bridge, peer_uid=os.getuid())

    def test_content_scan_cannot_be_disabled_by_a_permissive_producer(self):
        # Only the deliberately bad fixture producer is permissive. The production bridge scans again.
        with patch.object(self.proposal, "content_allowed", return_value=True):
            token = "ghp_" + "A" * 36
            _, req = self.elect("Please publish " + token)
        with self.assertRaises(Refused) as caught:
            self.dispatch(req)
        self.assertIn("content_policy:github_token", str(caught.exception))
        self.assertNotIn(token, str(caught.exception))
        self.assertEqual(self.station.streams["town.reply"].head_seq, 0)

    def test_scanner_matches_existing_types_and_preserves_plain_text(self):
        cases = (("ghp_" + "A" * 36, "github_token"), ("sk-" + "B" * 24, "api_key"),
                 ("AKIA" + "C" * 16, "aws_key"), ("-----BEGIN RSA PRIVATE KEY-----", "private_key"),
                 ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", "high_entropy"))
        for text, kind in cases:
            with self.subTest(kind=kind):
                self.assertIn(kind, secret_findings(text))
                self.assertFalse(derived_text_allowed(text.encode()))
        self.assertTrue(derived_text_allowed(self.body.encode()))
        self.assertEqual(secret_findings("source sha256 " + "a4" * 32), [])
        self.assertFalse(derived_text_allowed(b"\xff"))


class DerivedControlSocketTest(Fixture, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.prepare()

    @asynccontextmanager
    async def running(self, *, bridge=True):
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.setblocking(False)
        control = str(self.root / "control.sock")
        stop = asyncio.Event()
        task = asyncio.create_task(runner.run_station(self.station, [receiver.getsockname()], control,
                                                      stop=stop, derived_bridge=self.bridge if bridge else None))
        try:
            for _ in range(200):
                if task.done():
                    await task
                if Path(control).exists():
                    break
                await asyncio.sleep(0.005)
            else:
                self.fail("station control socket did not open")
            self.control = control
            yield receiver
        finally:
            stop.set()
            try:
                await asyncio.wait_for(task, 2)
            finally:
                receiver.close()

    async def ask(self, req):
        return await asyncio.to_thread(runner.control_request, self.control, req)

    async def received_item(self, receiver):
        listener = Listener(Manifest([self.entry]), warmup=False, ephemeral=True)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 3
        while loop.time() < deadline:
            datagram, _ = await asyncio.wait_for(loop.sock_recvfrom(receiver, 2048), deadline - loop.time())
            events = listener.hear(datagram, runner.now_ms())
            for event in events:
                if event.kind == "item":
                    return event, wire.parse(datagram, Manifest([self.entry]).resolve, runner.now_ms()).body
        self.fail("no verified item arrived")

    async def test_real_socket_signs_then_real_listener_receives_and_query_never_resends(self):
        eid, req = self.elect()
        with patch.object(self.station, "sing", side_effect=AssertionError("ordinary-sing laundering")):
            async with self.running() as receiver:
                reply = await self.ask(req)
                self.assertTrue(reply["ok"], reply)
                event, item = await self.received_item(receiver)
                self.assertEqual(event.data["text"], self.body)
                self.assertEqual(item.hop, 1)
                self.assertEqual(item.derived_from, ((bytes.fromhex("01" * 8), 1, 1, 1),))
                query = await self.ask({"op": "derived_query", "election_id": eid})
                self.assertEqual(query["acceptance"], reply["acceptance"])
                self.assertFalse((await self.ask(req))["ok"])
                self.assertEqual(self.station.streams["town.reply"].head_seq, 1)

    async def test_lost_control_reply_is_recovered_by_query_only(self):
        eid, req = self.elect()
        async with self.running() as receiver:
            _, writer = await asyncio.open_unix_connection(self.control)
            writer.write((json.dumps(req) + "\n").encode())
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            await self.received_item(receiver)
            reply = await self.ask({"op": "derived_query", "election_id": eid})
            self.assertEqual(reply["state"], "accepted")
            self.assertEqual(reply["acceptance"]["election_id"], eid)
            self.assertFalse((await self.ask(req))["ok"])
            self.assertEqual(self.station.streams["town.reply"].head_seq, 1)

    async def test_quiet_and_unconfigured_real_socket_do_not_create_effect(self):
        async with self.running(bridge=False):
            status = await self.ask({"op": "status"})
            self.assertTrue(status["ok"])
            self.assertEqual(self.station.streams["town.reply"].head_seq, 0)
            _, req = self.elect()
            self.assertFalse((await self.ask(req))["ok"])
            self.assertEqual(self.station.streams["town.reply"].head_seq, 0)


if __name__ == "__main__":
    unittest.main()
