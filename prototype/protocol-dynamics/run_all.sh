#!/usr/bin/env bash
# Run every experiment and write results/*.json. Needs root (network namespaces,
# nftables, taskset, one global sysctl in E2). About 50 minutes in total.
#
#   sudo PYTHON=/path/to/venv/bin/python ./run_all.sh          # everything
#   sudo ./run_all.sh e2                                       # one experiment: e1 e2 e3 e4 e5
#
# Environment: PYTHON (needs cryptography>=45 and numpy), E1_DURATION (900 s),
# E2_REPEATS (3), GO (go).
set -euo pipefail
cd "$(dirname "$0")"

PYTHON=${PYTHON:-python3}
GO=${GO:-go}
export PYTHONPATH="$(cd ../canticle-station && pwd)${PYTHONPATH:+:$PYTHONPATH}"

cleanup() {
  for ns in $(ip netns list | awk '{print $1}' | grep '^pd-' || true); do ip netns del "$ns" || true; done
}
trap cleanup EXIT
cleanup

ARGS=("$@")
want() { [[ ${#ARGS[@]} -eq 0 || " ${ARGS[*]} " == *" $1 "* ]]; }

# Phase 1: light, latency-bound experiments, in parallel namespaces (~17 min).
pids=()
if want e1; then "$PYTHON" e1_freshness.py all --duration "${E1_DURATION:-900}" & pids+=($!); fi
if want e3; then
  taskset -c 1 "$PYTHON" e3_consumers.py slow & pids+=($!)
  "$PYTHON" e3_consumers.py dead & pids+=($!)
fi
if want e4; then "$PYTHON" e4_late_joiner.py all & pids+=($!); fi
for p in "${pids[@]}"; do wait "$p"; done

# Phase 2: CPU accounting wants a quiet machine (~20 min).
if want e2; then
  (cd fanout && "$GO" build -o fanout .)
  "$PYTHON" e2_fanout.py --repeats "${E2_REPEATS:-3}"
fi

# Phase 3: the reconnect storm (~4 min).
if want e5; then "$PYTHON" e5_reconnect_storm.py all; fi
