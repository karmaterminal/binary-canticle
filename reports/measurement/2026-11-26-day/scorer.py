"""Score declared synthetic trace metadata, never infer a prince's encounter.

No network, models, payload text, host adapters or production receptor policy.
The caller must supply matched opportunities and a complete invocation census;
those declarations are validated structurally, not independently attested here.
"""
import argparse
import json
from pathlib import Path
import re
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def score(plan):
    require(isinstance(plan, dict), "trace object required")
    require(plan.get("v") == "canticle-day-trace/0", "unknown trace version")
    require(plan.get("source_kind") == "synthetic", "only synthetic traces admitted")
    budget = plan.get("budget")
    require(type(budget) is int and 1 <= budget <= 100, "bounded integer budget required")
    start, end = plan["window_ms"]
    require(type(start) is int and type(end) is int and 0 <= start < end, "invalid window")
    facts = {}
    for fact in plan["facts"]:
        ident = fact["id"]
        require(isinstance(ident, str) and ident and ident not in facts, "duplicate/empty fact id")
        require(re.fullmatch(r"[0-9a-f]{64}", fact["body_sha256"]) is not None, "invalid body hash")
        issued, expires = fact["issued_ms"], fact["expires_ms"]
        require(type(issued) is int and type(expires) is int and start <= issued < expires <= end,
                "fact lifetime outside fixture window")
        facts[ident] = fact
    require(0 < len(facts) <= 100, "bounded nonempty facts required")
    expected = sorted(plan["facts"], key=lambda f: f["id"])
    require(set(plan["arms"]) == {"discord", "pull", "grant"}, "three named arms required")
    output = {}
    for name, arm in plan["arms"].items():
        require(type(arm["available"]) is bool, "availability must be explicit")
        if not arm["available"]:
            output[name] = {"assessment": "unavailable"}
            continue
        require(sorted(arm["opportunities"], key=lambda f: f["id"]) == expected,
                "unmatched facts/times/hashes: an empty Discord arm is not a baseline")
        require(type(arm["census_complete"]) is bool, "invocation census completeness required")
        turns = {}
        for turn in arm["turns"]:
            ident, when = turn["id"], turn["started_ms"]
            require(isinstance(ident, str) and ident and ident not in turns, "duplicate/empty invocation id")
            require(type(when) is int and start <= when < end, "invocation outside window")
            require(isinstance(turn.get("receipt"), str) and turn["receipt"], "invocation receipt required")
            turns[ident] = turn
        ordered = sorted(turns, key=lambda t: (turns[t]["started_ms"], t))
        credited = set(ordered[:budget])
        delivered = set()
        for row in arm["delivered"]:
            require(row["fact_id"] in facts and bool(row.get("receipt")), "delivery needs known fact and receipt")
            delivered.add(row["fact_id"])
        noticed, first_turn, notice_events, late, beyond, used = {}, {}, {}, set(), set(), set()
        # A notice is an explicit trace annotation citing an output, not a push,
        # an optimistic tool-return stamp, or a token echo equated to full text.
        for row in arm["noticed"]:
            fact_id, turn_id = row["fact_id"], row["turn_id"]
            require(fact_id in facts and turn_id in turns and bool(row.get("receipt")), "invalid notice evidence")
            fact, when = facts[fact_id], row["noticed_ms"]
            require(type(when) is int and turns[turn_id]["started_ms"] <= when < end,
                    "notice time outside invocation/window")
            require(when >= fact["issued_ms"], "notice precedes issue")
            if turn_id not in credited:
                beyond.add(fact_id)
                continue
            if when >= fact["expires_ms"]:
                late.add(fact_id)
                continue
            notice_events.setdefault(fact_id, []).append((when, turn_id))
            if fact_id not in noticed or (when, turn_id) < (noticed[fact_id], first_turn[fact_id]):
                noticed[fact_id] = when
                first_turn[fact_id] = turn_id
        for row in arm["used"]:
            fact_id, turn_id = row["fact_id"], row["turn_id"]
            require(fact_id in facts and turn_id in turns and bool(row.get("receipt")), "invalid use evidence")
            used_ms = row["used_ms"]
            require(type(used_ms) is int and turns[turn_id]["started_ms"] <= used_ms < end,
                    "use time outside invocation/window")
            require(any(when < used_ms or (when == used_ms and source_turn == turn_id)
                        for when, source_turn in notice_events.get(fact_id, [])),
                    "use requires its own prior/this-turn notice")
            if turn_id in credited:
                used.add(fact_id)
        complete = arm["census_complete"]
        count = len(credited)
        output[name] = {
            "assessment": "trace-scored" if complete else "unknown",
            "observed_model_invocations": len(turns), "budgeted_invocations": count,
            "reported_delivered": sorted(delivered), "reported_noticed": sorted(noticed),
            "reported_used": sorted(used), "late_notice_ids": sorted(late),
            "over_budget_notice_ids": sorted(beyond),
            "missing_notice_ids": sorted(set(facts) - noticed.keys()) if complete else None,
            "noticed_per_invocation": len(noticed) / count if complete and count else None,
            "empty_invocations": count - len(set(first_turn.values())) if complete else None,
        }
    b, c = output["pull"], output["grant"]
    comparison = "unknown"
    if b["assessment"] == c["assessment"] == "trace-scored":
        missed_from_pull = set(b["reported_noticed"]) - set(c["reported_noticed"])
        comparison = "fail" if missed_from_pull else "no-additional-trace-miss"
    return {"v": "canticle-day-score/0", "claim": "synthetic declared metadata only; no live encounter or value proof",
            "arms": output, "grant_vs_pull_no_extra_miss": comparison}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    try:
        result = score(json.loads(args.trace.read_text()))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, "invalid trace: " + str(exc) + chr(10))
    print(json.dumps(result, indent=2, allow_nan=False))
    return {"fail": 1, "unknown": 3, "no-additional-trace-miss": 0}[result["grant_vs_pull_no_extra_miss"]]


if __name__ == "__main__":
    sys.exit(main())
