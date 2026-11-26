"""Synthetic controls only. No imported historical or live model trace."""
from copy import deepcopy
import unittest
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from scorer import score


def fixture():
    facts = [dict(id="opening", body_sha256="a"*64, issued_ms=0, expires_ms=900)]
    arm = dict(available=True, opportunities=deepcopy(facts), census_complete=True,
               turns=[dict(id="reader/session/invocation-1", started_ms=100, receipt="synthetic:host-start")],
               delivered=[dict(fact_id="opening", receipt="synthetic:host-returned")],
               noticed=[dict(fact_id="opening", turn_id="reader/session/invocation-1", receipt="synthetic:explicit-output")],
               used=[])
    return dict(v="canticle-day-trace/0", source_kind="synthetic", budget=15,
                window_ms=[0,1000], facts=facts,
                arms={name:deepcopy(arm) for name in ("discord","pull","grant")})


class ScorerTest(unittest.TestCase):
    def test_cli_control_miss_and_unknown_have_distinct_exits(self):
        with tempfile.TemporaryDirectory(prefix="canticle-day-synthetic-") as directory:
            path=Path(directory)/"trace.json"
            for mode,expected in [("control",0),("miss",1),("unknown",3),("invalid",2)]:
                p=fixture()
                if mode=="miss": p["arms"]["grant"]["noticed"]=[]
                if mode=="unknown": p["arms"]["grant"]["census_complete"]=False
                if mode=="invalid": p["source_kind"]="live"
                path.write_text(json.dumps(p))
                result=subprocess.run([sys.executable,str(Path(__file__).with_name("scorer.py")),str(path)],capture_output=True,text=True)
                with self.subTest(mode=mode):
                    self.assertEqual(result.returncode,expected,result.stderr)
                    if mode!="invalid": self.assertIn("synthetic declared metadata",json.loads(result.stdout)["claim"])

    def test_non_object_json_rejected(self):
        for value in [None, [], 1, "trace"]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError,"trace object required"):
                score(value)

    def test_matched_control(self):
        result=score(fixture())
        self.assertEqual(result["grant_vs_pull_no_extra_miss"],"no-additional-trace-miss")
        self.assertEqual(result["arms"]["grant"]["reported_used"],[])

    def test_delivery_is_not_notice_or_use(self):
        p=fixture(); p["arms"]["grant"]["noticed"]=[]
        a=score(p)["arms"]["grant"]
        self.assertEqual(a["reported_delivered"],["opening"])
        self.assertEqual(a["reported_noticed"],[])
        self.assertEqual(a["reported_used"],[])
        self.assertEqual(a["missing_notice_ids"],["opening"])

    def test_planted_miss_fails_comparison(self):
        p=fixture(); p["arms"]["grant"]["noticed"]=[]
        self.assertEqual(score(p)["grant_vs_pull_no_extra_miss"],"fail")

    def test_pushes_never_create_model_invocations(self):
        p=fixture(); a=p["arms"]["grant"]; a["turns"]=[]; a["noticed"]=[]
        a["delivered"]*=5
        result=score(p)["arms"]["grant"]
        self.assertEqual(result["observed_model_invocations"],0)
        self.assertIsNone(result["noticed_per_invocation"])

    def test_many_tool_calls_in_one_invocation_cost_one(self):
        p=fixture(); p["arms"]["pull"]["tool_calls"]=["hear","peek","status"]
        self.assertEqual(score(p)["arms"]["pull"]["observed_model_invocations"],1)

    def test_duplicate_invocation_rejected_not_silently_collapsed(self):
        p=fixture(); p["arms"]["pull"]["turns"]*=2
        with self.assertRaisesRegex(ValueError,"duplicate/empty invocation"):
            score(p)

    def test_same_notice_twice_does_not_gain_a_fact_or_turn(self):
        p=fixture(); p["arms"]["grant"]["noticed"]*=2
        a=score(p)["arms"]["grant"]
        self.assertEqual(a["noticed_per_invocation"],1)
        self.assertEqual(a["empty_invocations"],0)

    def test_repeat_notice_on_later_invocation_is_empty(self):
        p=fixture(); a=p["arms"]["grant"]
        a["turns"].append(dict(id="later",started_ms=200,receipt="synthetic:host-start-2"))
        a["noticed"].insert(0,dict(fact_id="opening",turn_id="later",receipt="synthetic:repeat"))
        self.assertEqual(score(p)["arms"]["grant"]["empty_invocations"],1)

    def test_use_requires_independent_notice(self):
        p=fixture(); a=p["arms"]["grant"]; a["noticed"]=[]
        a["used"]=[dict(fact_id="opening",turn_id=a["turns"][0]["id"],receipt="synthetic:action")]
        with self.assertRaisesRegex(ValueError,"use requires"):
            score(p)

    def test_explicit_use_is_separate(self):
        p=fixture(); a=p["arms"]["grant"]
        a["used"]=[dict(fact_id="opening",turn_id=a["turns"][0]["id"],receipt="synthetic:action")]
        self.assertEqual(score(p)["arms"]["grant"]["reported_used"],["opening"])

    def test_unmatched_discord_arm_rejected(self):
        p=fixture(); p["arms"]["discord"]["opportunities"]=[]
        with self.assertRaisesRegex(ValueError,"unmatched facts"):
            score(p)

    def test_same_ids_with_different_hash_or_lifetime_rejected(self):
        for key,value in [("body_sha256","b"*64),("expires_ms",899)]:
            p=fixture(); p["arms"]["discord"]["opportunities"][0][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,"unmatched facts"):
                score(p)

    def test_unknown_census_never_turns_absence_into_zero_misses(self):
        p=fixture(); a=p["arms"]["grant"]; a["census_complete"]=False; a["noticed"]=[]
        result=score(p)
        self.assertEqual(result["arms"]["grant"]["assessment"],"unknown")
        self.assertIsNone(result["arms"]["grant"]["missing_notice_ids"])
        self.assertEqual(result["grant_vs_pull_no_extra_miss"],"unknown")

    def test_unavailable_openclaw_grant_not_imputed(self):
        p=fixture(); p["arms"]["grant"]={"available":False}
        self.assertEqual(score(p)["arms"]["grant"],{"assessment":"unavailable"})

    def test_over_budget_notice_not_credited(self):
        p=fixture(); p["budget"]=1; a=p["arms"]["grant"]
        a["turns"].insert(0,dict(id="first",started_ms=50,receipt="synthetic:empty-turn"))
        result=score(p)["arms"]["grant"]
        self.assertEqual(result["reported_noticed"],[])
        self.assertEqual(result["over_budget_notice_ids"],["opening"])
        self.assertEqual(result["observed_model_invocations"],2)

    def test_expired_notice_is_late_not_success(self):
        p=fixture(); p["arms"]["grant"]["turns"][0]["started_ms"]=900
        a=score(p)["arms"]["grant"]
        self.assertEqual(a["reported_noticed"],[])
        self.assertEqual(a["late_notice_ids"],["opening"])

    def test_non_synthetic_input_rejected(self):
        p=fixture(); p["source_kind"]="historical"
        with self.assertRaisesRegex(ValueError,"only synthetic"):
            score(p)

    def test_invalid_budget_rejected(self):
        for budget in [True,0,101,1.5]:
            p=fixture(); p["budget"]=budget
            with self.subTest(budget=budget),self.assertRaises(ValueError):
                score(p)


if __name__=="__main__":
    unittest.main()
