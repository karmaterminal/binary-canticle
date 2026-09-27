#!/usr/bin/env bash
# Run every experiment and write results/*.json. Needs root (network namespaces,
# nftables, taskset, one global sysctl in E2). About 50 minutes in total.
#
#   sudo PYTHON=/path/to/venv/bin/python ./run_all.sh          # everything
#   sudo ./run_all.sh e2                                       # one experiment: e1 e2 e3 e4 e5
#
# Environment: PYTHON (needs cryptography>=45 and numpy), E1_DURATION (900 s),
# E2_REPEATS (3), GO (go), PD_NS_PREFIX (namespace name prefix, default pd<pid>-).
#
# Namespaces: every one this run creates is named "$PD_NS_PREFIX..." and is
# recorded in a private list as it is created (harness/netns.py). On exit, this
# script deletes exactly the listed namespaces that still exist, and nothing
# else, so a concurrent run or an unrelated namespace is never touched.
#
# Exit status: nonzero if any experiment fails. E1 and E4 then publish nothing
# (their raw files and aggregate stay as they were); see harness/runs.py.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON=${PYTHON:-python3}
GO=${GO:-go}
export PYTHONPATH="$(cd ../canticle-station && pwd)${PYTHONPATH:+:$PYTHONPATH}"
export PD_NS_PREFIX=${PD_NS_PREFIX:-pd$$-}
PD_NS_TRACK=$(mktemp "${TMPDIR:-/tmp}/pd-netns.XXXXXX")
export PD_NS_TRACK

cleanup() {
  local have ns
  have=$(ip netns list | awk '{print $1}')
  sort -u "$PD_NS_TRACK" | while read -r ns; do
    [[ -n $ns && $ns == "$PD_NS_PREFIX"* ]] || continue
    if grep -qxF -- "$ns" <<<"$have"; then ip netns del "$ns" || true; fi
  done
  rm -f "$PD_NS_TRACK"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

ARGS=("$@")
want() { [[ ${#ARGS[@]} -eq 0 || " ${ARGS[*]} " == *" $1 "* ]]; }

# Phase 1: light, latency-bound experiments, in parallel namespaces (~17 min).
pids=()
names=()
if want e1; then "$PYTHON" e1_freshness.py all --duration "${E1_DURATION:-900}" & pids+=($!); names+=(e1); fi
if want e3; then
  taskset -c 1 "$PYTHON" e3_consumers.py slow & pids+=($!); names+=(e3-slow)
  "$PYTHON" e3_consumers.py dead & pids+=($!); names+=(e3-dead)
fi
if want e4; then "$PYTHON" e4_late_joiner.py all & pids+=($!); names+=(e4); fi
failed=()
for i in "${!pids[@]}"; do
  wait "${pids[$i]}" || failed+=("${names[$i]}")
done
if [[ ${#failed[@]} -gt 0 ]]; then
  echo "run_all.sh: failed: ${failed[*]}" >&2
  exit 1
fi

# Phase 2: CPU accounting wants a quiet machine (~20 min).
if want e2; then
  (cd fanout && "$GO" build -o fanout .)
  "$PYTHON" e2_fanout.py --repeats "${E2_REPEATS:-3}"
fi

# Phase 3: the reconnect storm (~4 min).
if want e5; then "$PYTHON" e5_reconnect_storm.py all; fi
