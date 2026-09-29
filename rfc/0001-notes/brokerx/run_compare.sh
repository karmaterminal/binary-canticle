#!/usr/bin/env bash
# Control experiment: same carousel semantics over (A) raw UDP + minimal relay, (B) NATS core via nats-server.
#
# Every path is quoted, the script stops on the first error, and each server is proven to be the
# process this script started (alive and owning its ports) before any client runs, so it can never
# benchmark, or write into, a server it did not start.
set -euo pipefail
D=$(cd "$(dirname "$0")" && pwd); cd "$D"; PY="$D/venv/bin/python"; OUT="$D/results"; mkdir -p "$OUT"
N=${N:-50}; ITEMS=${ITEMS:-20}; LOOP=${LOOP:-1000}
rss() { awk '/VmRSS/{print $2}' "/proc/$1/status" 2>/dev/null || true; }
free() { ! ss -H -ltun "sport = :$1" | grep -q .; }                    # nothing bound on the port
owns() { ss -H -ltunp "sport = :$2" 2>/dev/null | grep -q "pid=$1,"; }  # $1 (pid) owns port $2
started() {  # started PID PORT...: wait until PID is alive and owns every PORT, else fail
  local pid=$1; shift
  for _ in $(seq 50); do
    kill -0 "$pid" 2>/dev/null || { echo "pid $pid exited before listening" >&2; return 1; }
    local ok=1; for p in "$@"; do owns "$pid" "$p" || ok=0; done
    [[ $ok == 1 ]] && return 0
    sleep 0.1
  done
  echo "pid $pid does not own ports $*" >&2; return 1
}
for p in 47110 47111 4333 8333; do free "$p" || { echo "port $p is already in use; refusing to run" >&2; exit 1; }; done
pids=()
trap 'for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done' EXIT

echo "== A: raw UDP station -> relay -> $N leased listeners (loss 0 and 0.3)"
"$PY" relay_udp.py --run 42 > "$OUT/a_relay.txt" & RELAY=$!; pids+=("$RELAY")
started "$RELAY" 47110 47111
"$PY" station.py udp 127.0.0.1:47110 --items "$ITEMS" --loop-ms "$LOOP" --run 40 > "$OUT/a_station.txt" & ST=$!
"$PY" listener.py udp 127.0.0.1:47111 --n "$N" --loss 0.0 --join 5 --listen 15 > "$OUT/a_listen_loss0.txt" & L1=$!
"$PY" listener.py udp 127.0.0.1:47111 --n "$N" --loss 0.3 --join 22 --listen 15 > "$OUT/a_listen_loss30.txt" & L2=$!
sleep 14; echo "rss_kB relay=$(rss "$RELAY") station=$(rss "$ST") listeners($N)=$(rss "$L1")" | tee "$OUT/a_rss.txt"
wait "$L1" "$L2" "$ST" "$RELAY"
cat "$OUT"/a_*.txt

echo "== B: NATS core station -> nats-server -> $N subscribers"
rm -rf -- "$D/jsdata"
./bin/nats-server -p 4333 -m 8333 -js -sd "$D/jsdata" > "$OUT/b_server.log" 2>&1 & NS=$!; pids+=("$NS")
started "$NS" 4333 8333
echo "rss_kB nats-server idle=$(rss "$NS")" | tee "$OUT/b_rss.txt"
"$PY" station.py nats nats://127.0.0.1:4333 --items "$ITEMS" --loop-ms "$LOOP" --run 25 > "$OUT/b_station.txt" & ST=$!
"$PY" listener.py nats nats://127.0.0.1:4333 --n "$N" --join 5 --listen 15 > "$OUT/b_listen.txt" & L1=$!
sleep 14; echo "rss_kB nats-server=$(rss "$NS") station=$(rss "$ST") listeners($N)=$(rss "$L1")" | tee -a "$OUT/b_rss.txt"
wait "$L1" "$ST"
curl -s localhost:8333/varz | "$PY" -c 'import json,sys; v=json.load(sys.stdin); print({k:v[k] for k in ["version","in_msgs","out_msgs","in_bytes","out_bytes","mem","connections"]})' | tee "$OUT/b_varz.txt"
kill "$NS"; wait "$NS" 2>/dev/null || true
cat "$OUT/b_station.txt" "$OUT/b_listen.txt"
