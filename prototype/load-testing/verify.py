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
