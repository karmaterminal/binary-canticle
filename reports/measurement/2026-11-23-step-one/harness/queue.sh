#!/usr/bin/env bash
# The run order used: one suite at a time (two at once would share CPU and disk).
# Started under `nice -n 19 ionice -c3`; everything below inherits it.
set -u
cd "$(dirname "$0")"
PY=~/.venvs/canticle-measure-2/bin/python
export PYTHONDONTWRITEBYTECODE=1
run() { $PY run_cells.py "../results/$1" "@../results/$1/$2" > "../results/$1/run-$2.log" 2> "../results/$1/run-$2.err"; }
run flood cells-rest.json
run flood2 cells.json
run ingest cells.json
run admission cells.json
$PY scenario_reconnect.py ../results/reconnect > ../results/reconnect/run.log 2> ../results/reconnect/run.err
echo done > ../results/queue.done
