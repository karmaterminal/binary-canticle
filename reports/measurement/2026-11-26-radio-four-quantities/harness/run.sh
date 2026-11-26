#!/usr/bin/env bash
# The four-quantities window (METHOD.md): read-only instruments on this host, for <seconds>, into <results-dir>.
#   harness/run.sh <results-dir> [seconds]   (default 2700: 45 minutes)
# Nothing here sings, hushes, tunes, grants, restarts or reconfigures anything. Every instrument runs niced.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
out=${1:?usage: run.sh <results-dir> [seconds]}
dur=${2:-2700}
venv_py="$HOME/.venvs/canticle/bin/python"
mkdir -p "$out"

t0=$(date +%s%3N)
printf '{"t0": %s, "duration_s": %s, "host": "%s"}\n' "$t0" "$dur" "$(hostname)" > "$out/window.json"
nice -n 10 python3 -B -I "$here/catalog.py" --out "$out/catalog.json"
nice -n 10 "$venv_py" -B -I "$here/beacon_sizes.py" --out "$out/beacon-sizes.json"
nice -n 10 python3 -B -I "$here/daemon_records.py" --out "$out/daemon-records.jsonl" --duration "$dur" &
rec=$!
nice -n 10 python3 -B -I "$here/host_sampler.py" --out "$out/host-samples.jsonl" --duration "$dur" --t0 "$t0" &
smp=$!
wait "$rec" "$smp"
t1=$(date +%s%3N)
nice -n 10 python3 -B -I "$here/window_close.py" --t0 "$t0" --t1 "$t1" --out "$out/window-close.json"
printf '{"t0": %s, "t1": %s, "duration_s": %s, "host": "%s"}\n' "$t0" "$t1" "$dur" "$(hostname)" > "$out/window.json"
echo "window closed: t0=$t0 t1=$t1"
