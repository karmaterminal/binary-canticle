#!/usr/bin/env bash
# Runs after queue.sh: the two cells that bracket the valid-flood threshold.
set -u
cd "$(dirname "$0")"
while [ ! -f ../results/queue.done ]; do sleep 20; done
PYTHONDONTWRITEBYTECODE=1 ~/.venvs/canticle-measure-2/bin/python run_cells.py ../results/flood3 @../results/flood3/cells.json > ../results/flood3/run-cells.log 2> ../results/flood3/run-cells.err
echo done > ../results/queue2.done
