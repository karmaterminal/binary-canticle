#!/usr/bin/env python3
"""Check real k6/fixture/cleanup receipts; a negative run remains a failed run."""
import argparse
import json
from pathlib import Path


def verify(directory, negative=False):
    if not __debug__:
        raise RuntimeError("receipt verification requires Python assertions (no -O/PYTHONOPTIMIZE)")
    root = Path(directory)
    run = json.loads((root / "run.json").read_text())
    fixture = json.loads((root / "fixture-report.json").read_text())
    summary = json.loads((root / "k6-summary.json").read_text())
    cleanup = json.loads((root / "cleanup.json").read_text())
    process = json.loads((root / "process.json").read_text())
    assert process["child_started"] and process["child_reaped"], process
    assert process["k6_exit_code"] == (99 if negative else 0), process
    assert process["supervisor_exit_code"] == process["k6_exit_code"], process
    n = run["bounds"]["items"]
    counts = fixture["counts"]
    assert fixture["run_id"] and fixture["expected_ids"] == list(range(n)), fixture
    assert sorted(r["id"] for r in fixture["rows"]) == fixture["expected_ids"], fixture
    assert run["bounds"]["drop_first"] is negative, run
    assert fixture["accounting"] and not fixture["errors"], fixture
    assert fixture["production_tasks_alive"], fixture
    assert counts["offered"] == counts["accepted"] == counts["arrived"] == n, counts
    assert counts["pending"] == counts["submit_errors"] == counts["duplicate_surface_records"] == 0, counts
    assert counts["delivered"] == n - int(negative), counts
    assert counts["missed"] == int(negative), counts
    assert cleanup["ok"] and cleanup["k6_child_reaped"], cleanup
    if not run["shared_process"]:
        assert fixture["process_mode"] is True, fixture
        children = fixture["processes"]
        assert set(children) == {"station", "daemon"}, children
        startup_fields = {"pid", "alive", "started", "ready", "started_ns", "child_started_ns", "ready_ns", "exit_code"}
        assert all(startup_fields <= set(r) for r in children.values()), children
        assert len({r["pid"] for r in children.values()}) == 2, children
        assert type(fixture["parent_pid"]) is int and fixture["parent_pid"] > 0, fixture
        assert all(r["pid"] != fixture["parent_pid"] for r in children.values()), children
        assert all(r["alive"] is True and type(r["pid"]) is int and r["pid"] > 0
                   and r["started"] is True and r["ready"] is True
                   and r["exit_code"] is None
                   and all(type(r[k]) is int and r[k] > 0
                           for k in ("started_ns", "child_started_ns", "ready_ns"))
                   and r["started_ns"] <= r["child_started_ns"] <= r["ready_ns"]
                   for r in children.values()), children
        assert cleanup["processes_reaped"], cleanup
        assert set(cleanup["processes"]) == {"station", "daemon"}, cleanup
        cleanup_fields = startup_fields | {"reaped", "reaped_ns", "exit_observed_ns", "handle_closed", "term_sent", "kill_sent"}
        assert all(cleanup_fields <= set(r) for r in cleanup["processes"].values()), cleanup
        assert all(cleanup["processes"][name][key] == receipt[key]
                   for name, receipt in children.items()
                   for key in ("pid", "started", "ready", "started_ns", "child_started_ns", "ready_ns")), cleanup
        assert all(r["reaped"] is True and r["exit_code"] == 0
                   and r["handle_closed"] is True and r["alive"] is False
                   and r["term_sent"] is True and r["kill_sent"] is False
                   and r["ready_ns"] <= r["exit_observed_ns"]
                   and r["ready_ns"] <= r["reaped_ns"]
                   for r in cleanup["processes"].values()), cleanup
        assert cleanup["processes"]["station"]["reaped_ns"] <= cleanup["processes"]["daemon"]["reaped_ns"], cleanup
        assert all(cleanup["processes"][name]["pid"] == receipt["pid"]
                   for name, receipt in children.items()), cleanup
    metrics = summary["metrics"]
    assert metrics["canticle_offered"]["values"]["count"] == n
    assert metrics["canticle_delivered"]["values"]["count"] == n - int(negative)
    rate = metrics["canticle_deadline_miss"]["values"]["rate"]
    assert abs(rate - int(negative)/n) < 1e-9, rate
    assert metrics["canticle_offer_to_record_or_deadline_ms"]["values"]["count"] == n
    assert metrics["canticle_arrival_to_record_or_deadline_ms"]["values"]["count"] == n
    thresholds = metrics["canticle_deadline_miss"]["thresholds"]
    assert thresholds["rate==0"]["ok"] is not negative, thresholds
    if negative:
        assert run["bounds"]["drop_first"]
        assert fixture["packets"]["intentionally_dropped"] > 0
        missed = [r for r in fixture["rows"] if r["missed"]]
        assert len(missed) == 1 and missed[0]["identity"][-1] == 1, missed
        assert missed[0]["arrival_to_record_ms"] is None
    else:
        assert fixture["packets"]["intentionally_dropped"] == 0
    return dict(verified=True, negative_control=negative, offered=n,
                delivered=counts["delivered"], missed=counts["missed"],
                deadline_miss_rate=rate, cleanup_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.directory, args.negative)))
