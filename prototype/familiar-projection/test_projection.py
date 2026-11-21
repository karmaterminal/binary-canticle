"""Tests for the familiar projection checker (#148). Standard library only. From the repository root:

    PYTHONPATH=prototype/canticle-station python -m unittest discover -s prototype/familiar-projection -v

PYTHONPATH is optional: with it, two tests also check the checker against the station's own codec.
"""

import contextlib
import hashlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import projection as P  # noqa: E402

FIXTURES = {p.stem: p for p in sorted((HERE / "fixtures").glob("*.json"))}
CASES = {"AC1", "AC2", "AC3", "AC4", "AC5", "AC6", "AC7", "notice vs record", "descriptor"}


def run(name: str) -> list:
    return P.run_fixture(FIXTURES[name])


class FixturesTest(unittest.TestCase):
    def test_every_fixture_passes(self):
        for name in FIXTURES:
            with self.subTest(name):
                self.assertEqual(run(name), [])

    def test_fixtures_cover_every_acceptance_case(self):
        self.assertEqual({P.load(p)["case"] for p in FIXTURES.values()}, CASES)

    def test_fixtures_are_synthetic(self):
        for name, path in FIXTURES.items():
            with self.subTest(name):
                fx = P.load(path)
                self.assertIs(fx["synthetic"], True)
                text = path.read_text(encoding="utf-8")
                # Placeholder station keys only, and nothing shaped like a Discord snowflake.
                self.assertEqual(set(re.findall(r"\b[0-9a-f]{16}\b", text)) - {"f00d000000000001", "f00d000000000002"}, set())
                self.assertIsNone(re.search(r"\b\d{17,20}\b", text))

    def test_order_does_not_matter(self):
        """Each fixture starts from nothing: running them backwards gives the same results."""
        forward = {name: run(name) for name in FIXTURES}
        backward = {name: run(name) for name in reversed(list(FIXTURES))}
        self.assertEqual(forward, backward)

    def test_command_line(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(P.main([]), 0)
        self.assertEqual(len(out.getvalue().splitlines()), len(FIXTURES))
        fx = P.load(FIXTURES["a1-one-window-two-receivers"])
        fx["name"] = "broken"
        fx["expect_end"]["producers"]["f00d000000000001"]["synthesis"] = 2
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text(json.dumps(fx), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(P.main([str(path)]), 1)
        self.assertIn("producer f00d000000000001 synthesis: expected 2, got 1", out.getvalue())


class FixtureFormatTest(unittest.TestCase):
    def fixture(self, **over) -> dict:
        fx = P.load(FIXTURES["a7-receiver-gap"])
        fx.update(over)
        return fx

    def test_strict(self):
        cases = {
            "not synthetic": self.fixture(synthetic=False),
            "unknown key": self.fixture(extra=1),
            "unknown op": self.fixture(steps=[{"t": 0, "op": "wake", "at": "r1"}]),
            "unknown step key": self.fixture(steps=[{"t": 0, "op": "health", "at": "r1", "records_lost": 1, "x": 1}]),
            "time goes back": self.fixture(steps=[{"t": 5, "op": "health", "at": "r1", "no_datagrams": True},
                                                  {"t": 4, "op": "health", "at": "r2", "no_datagrams": True}]),
            "unknown expectation": self.fixture(steps=[{"t": 0, "op": "read", "at": "r1", "expect": {"mood": 1}}]),
        }
        for what, fx in cases.items():
            with self.subTest(what), self.assertRaises(P.FixtureError):
                P.Run(fx, "a7-receiver-gap").run()

    def test_duplicate_json_keys_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dupe.json"
            path.write_text('{"v": 1, "v": 2}', encoding="utf-8")
            with self.assertRaises(P.FixtureError):
                P.load(path)


class DescriptorBytesTest(unittest.TestCase):
    """On the wire a body is its canonical bytes, so equal projections have equal record v1 sha256."""

    def setUp(self):
        self.body = P.load(FIXTURES["d1-descriptor-rules"])["bodies"]["ok"]

    def test_canonical_bytes_are_read(self):
        raw = P.canonical(self.body)
        self.assertEqual(P.read_descriptor_bytes(raw, "lan").digest, hashlib.sha256(raw).hexdigest())

    def test_other_bytes_are_refused(self):
        raw = P.canonical(self.body).decode()
        cases = [
            ("spaces after separators", json.dumps(self.body).encode(), "not-canonical"),
            ("a duplicate key", raw.replace('"v":', '"v":"x","v":', 1).encode(), "not-json"),
            ("NaN", raw.replace('"rev":1', '"rev":NaN').encode(), "not-json"),
            ("not UTF-8", b"\xff" + raw.encode(), "not-json"),
        ]
        for what, data, code in cases:
            with self.subTest(what), self.assertRaises(P.Refused) as cm:
                P.read_descriptor_bytes(data, "lan")
            self.assertEqual(cm.exception.code, code)


class StationAgreementTest(unittest.TestCase):
    """The checker reuses the station's identifiers and fits its frame (skipped without canticle)."""

    def test_idem_and_stream_id_match_the_station(self):
        try:
            from canticle import ids, records
        except ImportError:
            self.skipTest("canticle-station is not on PYTHONPATH")
        for name in ("wake", "familiar", "x-test.doctor"):
            self.assertEqual(P.stream_id(name), ids.stream_id(name))
        kid = bytes.fromhex("f00d000000000001")
        self.assertEqual(P.idem("f00d000000000001", 3, "wake", 9), records.idem((kid, 3, ids.stream_id("wake"), 9)))

    def test_largest_body_fits_a_keyed_item(self):
        try:  # canticle first: without it on PYTHONPATH, a system cryptography is never touched
            from canticle import ids, wire
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        except ImportError:
            self.skipTest("canticle-station or cryptography is not installed")
        item = wire.Item(epoch=2**32 - 1, stream=ids.stream_id("wake"), seq=2**32 - 1, issued_at=1_795_000_000_000,
                         expires_at=1_795_000_300_000, cls=1, ctype=3, body=b"x" * P.MAX_BODY, state_key="k" * 48,
                         scope=1, flags=wire.Item.REFRESH)
        self.assertLessEqual(len(wire.encode_item(Ed25519PrivateKey.from_private_bytes(bytes(32)), item)),
                             wire.MAX_FRAME)


class RevertChecksTest(unittest.TestCase):
    """Each rule, put back to the naive behaviour it replaces, makes the fixture that guards it fail."""

    def assertCaught(self, fixture: str, expected: str, *patches):
        with contextlib.ExitStack() as stack:
            for target, attr, new in patches:
                stack.enter_context(mock.patch.object(target, attr, new))
            failures = run(fixture)
        self.assertTrue(any(expected in f for f in failures),
                        f"{fixture} did not catch the revert; failures: {failures}")

    def test_ac1_a_receiver_that_synthesizes_on_read(self):
        view = P.Receiver.view

        def summarizing_view(self, *a, **kw):
            self.model_calls += 1  # "summarize what's current for me"
            return view(self, *a, **kw)

        self.assertCaught("a1-one-window-two-receivers", "model_calls", (P.Receiver, "view", summarizing_view))

    def test_ac1_a_re_stamp_counted_as_a_synthesis(self):
        resolved = P.resolved
        self.assertCaught("a1-one-window-two-receivers", "mechanical",
                          (P, "resolved", lambda proj, c: resolved(proj, c) + (proj.generated_at,)))

    def test_ac2_ac3_withdrawal_only_inside_the_projection_that_states_it(self):
        state = P.evidence_state
        for fixture, expected in (("a2-expiry-withdrawal-supersession", "team1#c1"),
                                  ("a3-partial-invalidation", "p3#c1"), ("a4-elected-history", "p1#c1")):
            with self.subTest(fixture):
                self.assertCaught(fixture, expected, (P, "evidence_state", lambda rx, h, c, t: (
                    None if state(rx, h, c, t) == "withdrawn" else state(rx, h, c, t))))

    def test_ac2_source_lapse_ignored_until_the_projection_lapses(self):
        state = P.evidence_state
        naive = (P, "evidence_state", lambda rx, h, c, t: None if state(rx, h, c, t) == "source-lapsed" else state(rx, h, c, t))
        self.assertCaught("a2-expiry-withdrawal-supersession", "team1#c3", naive)
        self.assertCaught("n1-notice-versus-record", "w1#c1", naive)

    def test_ac2_newer_source_revision_ignored(self):
        state = P.evidence_state
        self.assertCaught("a2-expiry-withdrawal-supersession", "team2#c2", (P, "evidence_state", lambda rx, h, c, t: (
            None if state(rx, h, c, t) == "source-superseded" else state(rx, h, c, t))))

    def test_ac3_restated_validity_extends_the_source(self):
        self.assertCaught("a3-partial-invalidation", "p4#c2",
                          (P, "stated_until", lambda earlier, stated: stated if earlier is None else max(earlier, stated)))

    def test_ac3_a_fresh_body_forgets_an_earlier_withdrawal(self):
        mark = P.Receiver._mark

        def forgetful(self, key_id, proj, t):
            for s in proj.sources.values():
                if m := self.marks.get((key_id, s.actor, s.ref)):
                    m.withdrawn.pop(s.rev, None)
            mark(self, key_id, proj, t)

        self.assertCaught("a3-partial-invalidation", "p3#c1", (P.Receiver, "_mark", forgetful))

    def test_ac4_history_standing_read_as_current(self):
        status = P.claim_status
        self.assertCaught("a4-elected-history", "merge", (P, "claim_status", lambda rx, h, c, t: (
            "current" if status(rx, h, c, t) == "history" else status(rx, h, c, t))))

    def test_ac4_a_session_keeps_heard_content(self):
        retain = P.Receiver.retain
        self.assertCaught("a4-elected-history", "retain p1#c1",
                          (P.Receiver, "retain", lambda self, t, ref, by: retain(self, t, ref, "principal")))

    def test_ac5_presentation_without_a_currency_recheck(self):
        def resolve_any(self, pkey, t):
            hits = [(h, c) for h, c in self.claims() if h.pkeys[c.id] == pkey]
            return hits[-1] if hits else None

        self.assertCaught("a5-restart-after-validity", "presented", (P.Receiver, "_resolve", resolve_any))

    def test_ac6_presentation_without_evidence_dedupe(self):
        label = P.label_of
        self.assertCaught("a6-rephrase-no-weight", "presented", (P, "presentation_key", lambda proj, c: (
            label(proj, c), proj.digest + c.id)))

    def test_ac6_support_counted_in_claims(self):
        def claim_count(self, topic, t):
            return sum(1 for h, c in self.claims() if topic in c.topics and P.claim_status(self, h, c, t) == "current")

        self.assertCaught("a6-rephrase-no-weight", "topic_support build", (P.Receiver, "topic_support", claim_count))

    def test_ac7_a_gap_read_as_current(self):
        status = P.claim_status
        self.assertCaught("a7-receiver-gap", "carried", (P, "claim_status", lambda rx, h, c, t: (
            "current" if status(rx, h, c, t) == "carried" else status(rx, h, c, t))))

    def test_ac7_an_unread_actor_left_out(self):
        self.assertCaught("a7-receiver-gap", "unknown", (P.Receiver, "unknown", lambda self, t: []))

    def test_ac7_a_gap_rendered_as_quiet(self):
        render = P.Receiver.render

        def quiet(self, t, name, refs):
            return [x.replace("coverage unknown", "all quiet") for x in render(self, t, name, refs)]

        self.assertCaught("a7-receiver-gap", "§6.3 rule 5", (P.Receiver, "render", quiet))

    def test_notice_expiry_ends_the_whole_projection(self):
        status = P.claim_status

        def whole(rx, held, claim, t):
            if any(t >= s.valid_until for s in held.proj.sources.values()):
                return "lapsed"
            return status(rx, held, claim, t)

        self.assertCaught("n1-notice-versus-record", "w1#c2", (P, "claim_status", whole))


if __name__ == "__main__":
    unittest.main()
