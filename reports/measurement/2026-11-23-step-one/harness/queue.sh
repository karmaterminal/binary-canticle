#!/usr/bin/env bash
# Runs the remaining suites one after another (never two at once: they would share CPU and disk).
# Started under `nice -n 19 ionice -c3`; everything below inherits it.
set -u
cd "$(dirname "$0")"
PY=~/.venvs/canticle-measure-2/bin/python
export PYTHONDONTWRITEBYTECODE=1
while [ -n "${WAIT_PID:-}" ] && kill -0 "$WAIT_PID" 2>/dev/null; do sleep 15; done
$PY run_cells.py ../results/flood2 @../results/flood2/cells.json > ../results/flood2/run.log 2> ../results/flood2/run.err
$PY run_cells.py ../results/ingest @../results/ingest/cells.json > ../results/ingest/run.log 2> ../results/ingest/run.err
$PY run_cells.py ../results/admission @../results/admission/cells.json > ../results/admission/run.log 2> ../results/admission/run.err
$PY scenario_reconnect.py ../results/reconnect > ../results/reconnect/run.log 2> ../results/reconnect/run.err
echo done > ../results/queue.done
