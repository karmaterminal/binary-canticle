#!/usr/bin/env bash
# Run every experiment and publish results/<unit>/ for each (e1, e2, e3-slow,
# e3-dead, e4, e5). Needs root (network namespaces, nftables, taskset, one
# global sysctl in E2). About 55 minutes in total.
#
#   sudo PYTHON=/path/to/venv/bin/python ./run_all.sh          # everything
#   sudo ./run_all.sh e2                                       # one experiment: e1 e2 e3 e4 e5
#   sudo ./run_all.sh --allow-dirty e4                         # see "Provenance" below
#
# Environment: PYTHON (needs cryptography>=45 and numpy), E1_DURATION (900 s),
# E2_REPEATS (3), GO (go; E2 builds fanout/ itself), PD_NS_PREFIX (namespace
# name prefix, default pd<pid>-).
#
# Provenance: every script refuses to start, and publishes nothing, if any of
# its source files (the script, harness/*.py, ../canticle-station/canticle/*.py,
# and fanout/*.go + go.mod for E2) differs from HEAD. --allow-dirty runs anyway
# and embeds the diff in each manifest. See harness/runs.py.
#
# Namespaces: every one this run creates is named "$PD_NS_PREFIX..." and is
# recorded in a private list as it is created (harness/netns.py). On exit, this
# script deletes exactly the listed namespaces that still exist, and nothing
# else, so a concurrent run or an unrelated namespace is never touched.
#
# Exit status: nonzero if any experiment fails. A failed experiment publishes
# nothing: its results/<unit>/ stays the previous generation (harness/runs.py).
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

ARGS=()
DIRTY=()
for arg in "$@"; do
  case $arg in
    --allow-dirty) DIRTY=(--allow-dirty) ;;
    e1|e2|e3|e4|e5) ARGS+=("$arg") ;;
    *) echo "run_all.sh: unknown argument $arg (want e1 … e5 or --allow-dirty)" >&2; exit 2 ;;
  esac
done
want() { [[ ${#ARGS[@]} -eq 0 || " ${ARGS[*]} " == *" $1 "* ]]; }

# Phase 1: light, latency-bound experiments, in parallel namespaces (~17 min; E3 dead takes that long).
pids=()
names=()
if want e1; then "$PYTHON" e1_freshness.py all --duration "${E1_DURATION:-900}" ${DIRTY[@]+"${DIRTY[@]}"} & pids+=($!); names+=(e1); fi
if want e3; then
  taskset -c 1 "$PYTHON" e3_consumers.py slow ${DIRTY[@]+"${DIRTY[@]}"} & pids+=($!); names+=(e3-slow)
  "$PYTHON" e3_consumers.py dead ${DIRTY[@]+"${DIRTY[@]}"} & pids+=($!); names+=(e3-dead)
fi
if want e4; then "$PYTHON" e4_late_joiner.py all ${DIRTY[@]+"${DIRTY[@]}"} & pids+=($!); names+=(e4); fi
failed=()
for i in "${!pids[@]}"; do
  wait "${pids[$i]}" || failed+=("${names[$i]}")
done
if [[ ${#failed[@]} -gt 0 ]]; then
  echo "run_all.sh: failed: ${failed[*]}" >&2
  exit 1
fi

# Phase 2: CPU accounting wants a quiet machine (~24 min, with the matched idle controls).
if want e2; then GO=$GO "$PYTHON" e2_fanout.py --repeats "${E2_REPEATS:-3}" ${DIRTY[@]+"${DIRTY[@]}"}; fi

# Phase 3: the reconnect storm (~4 min).
if want e5; then "$PYTHON" e5_reconnect_storm.py all ${DIRTY[@]+"${DIRTY[@]}"}; fi
