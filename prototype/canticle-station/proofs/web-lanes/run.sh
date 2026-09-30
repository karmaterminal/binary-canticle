#!/usr/bin/env bash
# Bounded proof run for #57 (web tuner) and #58 (ambient emitter). Needs root (network namespaces).
#
# Topology: two network namespaces on ONE kernel, joined by a veth pair. The station and the two
# fixture emitters run in "cant-a"; the listeners, the tuner gateway and the headless browser in
# "cant-b". Frames cross the veth as LAN multicast (239.255.13.13:9999, IP TTL 1). This is SAME-HOST
# evidence: separate network stacks, one machine and one clock. It is not a second host.
#
#   PYTHON=/path/to/python-with-cryptography ./run.sh [results-dir]
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PKG="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-python3}"
OUT="${1:-$HERE/results/$(date -u +%Y%m%dT%H%M%SZ)}"
EMIT_S="${EMIT_S:-300}"          # emitter run length
LATE_S="${LATE_S:-150}"          # a late listener starts here (s after the emitters)
LATE_PAGE_S="${LATE_PAGE_S:-200}" # a late browser page tunes in here
DRAIN_S="${DRAIN_S:-75}"         # wait after the emitters stop, > the 60 s TTL
NA=cant-a NB=cant-b
mkdir -p "$OUT"
# Record exactly which source ran. A dirty tree is recorded, and analyze.py fails the run on it.
git -C "$PKG" rev-parse HEAD > "$OUT/source-commit"
git -C "$PKG" status --porcelain -- . > "$OUT/source-dirty"
WORK="$(mktemp -d)"
export PYTHONPATH="$PKG"
export NODE_PATH="${NODE_PATH:-$(npm root -g)}"
PIDS=()

log() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$OUT/timeline.txt"; }
t_ms() { "$PY" -c 'import time; print(time.time_ns() // 1_000_000)'; }
sleep_until() { local left=$(( $1 - ($(t_ms) - T0) / 1000 )); [ "$left" -gt 0 ] && sleep "$left" || true; }
cleanup() {
  for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done
  sleep 1
  ip netns del "$NA" 2>/dev/null || true
  ip netns del "$NB" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT
[ "$(id -u)" = 0 ] || { echo "run as root (network namespaces)" >&2; exit 1; }
for ns in "$NA" "$NB"; do ip netns del "$ns" 2>/dev/null || true; done

# ---- network: two stacks, one veth, multicast routed onto it, counters on UDP input
ip netns add "$NA"; ip netns add "$NB"
ip link add veth-a netns "$NA" type veth peer name veth-b netns "$NB"
ip -n "$NA" addr add 10.77.0.1/24 dev veth-a; ip -n "$NB" addr add 10.77.0.2/24 dev veth-b
for ns in "$NA" "$NB"; do ip -n "$ns" link set lo up; done
ip -n "$NA" link set veth-a up; ip -n "$NB" link set veth-b up
ip -n "$NA" route add 224.0.0.0/4 dev veth-a; ip -n "$NB" route add 224.0.0.0/4 dev veth-b
# Station side: count every UDP datagram that reaches it. The design says there are none (I-1, I-2).
ip netns exec "$NA" nft -f - <<'EOF'
table inet proof {
  chain input {
    type filter hook input priority 0; policy accept;
    meta l4proto udp counter comment "udp-into-station-host"
  }
}
EOF
ip netns exec "$NB" nft -f - <<'EOF'
table inet proof {
  chain input {
    type filter hook input priority 0; policy accept;
    udp dport 9999 counter comment "canticle-into-listener-host"
  }
}
EOF

# ---- keys and manifest
(cd "$WORK" && "$PY" -m canticle keygen --out room.key --manifest fleet.json --name hymn-room \
  --classes ambient,chatter --streams hymn,lens.weather --scopes lan >/dev/null)
cp "$WORK/fleet.json" "$OUT/fleet.json"
cp "$HERE/hymn.txt" "$HERE/weather.txt" "$OUT/"

# ---- listener host: early recorder and tuner gateway
ip netns exec "$NB" "$PY" -m canticle listen --manifest "$WORK/fleet.json" --multicast \
  --state "$WORK/early.state" --evidence --timestamps > "$OUT/listen-early.jsonl" 2> "$OUT/listen-early.err" &
PIDS+=($!); EARLY=$!
ip netns exec "$NB" "$PY" -m canticle tuner --manifest "$WORK/fleet.json" --multicast \
  --http 127.0.0.1:8765 --state "$WORK/tuner.state" --log "$OUT/tuner-events.jsonl" 2> "$OUT/tuner.err" &
PIDS+=($!); TUNER=$!
sleep 1

# ---- station host: station, then two fixture emitters
ip netns exec "$NA" "$PY" -m canticle station --key "$WORK/room.key" --manifest "$WORK/fleet.json" \
  --stream hymn:ambient --stream lens.weather:ambient --multicast --control "$WORK/room.sock" \
  2> "$OUT/station.err" &
PIDS+=($!); STATION=$!
while [ ! -S "$WORK/room.sock" ]; do sleep 0.1; done
log "station pid $STATION up; tuner pid $TUNER; early listener pid $EARLY"
sleep 3
T0=$(t_ms); echo "$T0" > "$OUT/t0_ms"
ip netns exec "$NA" "$PY" -m canticle ambient --control "$WORK/room.sock" --stream hymn --fixture "$HERE/hymn.txt" \
  --ttl 60 --min-gap 2 --max-gap 10 --breath 0.2 --duration "$EMIT_S" --seed 58 --log "$OUT/emit-hymn.jsonl" &
PIDS+=($!); EH=$!
ip netns exec "$NA" "$PY" -m canticle ambient --control "$WORK/room.sock" --stream lens.weather \
  --fixture "$HERE/weather.txt" --ttl 60 --min-gap 5 --max-gap 15 --breath 0.3 --duration "$EMIT_S" --seed 57 \
  --log "$OUT/emit-weather.jsonl" &
PIDS+=($!); EW=$!
log "emitters started (hymn pid $EH, lens.weather pid $EW) for ${EMIT_S}s"

ip netns exec "$NB" "$PY" "$HERE/snapshots.py" http://127.0.0.1:8765 $((EMIT_S + DRAIN_S + 15)) > "$OUT/ring-snapshots.jsonl" &
PIDS+=($!); SNAP=$!

sleep 20
log "browser 1: tune hymn, leave, retune lens.weather, retune hymn"
ip netns exec "$NB" node "$HERE/browser.cjs" early "$OUT" >> "$OUT/browser.jsonl" 2>> "$OUT/browser.err"

sleep_until "$LATE_S"
log "late listener starts (T+${LATE_S} s)"
ip netns exec "$NB" "$PY" -m canticle listen --manifest "$WORK/fleet.json" --multicast \
  --state "$WORK/late.state" --timestamps > "$OUT/listen-late.jsonl" 2> "$OUT/listen-late.err" &
PIDS+=($!); LATE=$!
echo "$(t_ms)" > "$OUT/late_start_ms"

sleep_until "$LATE_PAGE_S"
log "browser 2: a late page tunes hymn (T+${LATE_PAGE_S} s)"
ip netns exec "$NB" node "$HERE/browser.cjs" late "$OUT" >> "$OUT/browser.jsonl" 2>> "$OUT/browser.err"

wait "$EH" "$EW"
log "emitters stopped; items already on air now expire naturally"
echo "$(t_ms)" > "$OUT/emit_stop_ms"
sleep "$DRAIN_S"
log "browser 3: after natural expiry"
ip netns exec "$NB" node "$HERE/browser.cjs" drain "$OUT" >> "$OUT/browser.jsonl" 2>> "$OUT/browser.err"
wait "$SNAP" || true

# ---- resources and counters, then stop (the station sends its goodbye beacon)
tick=$(getconf CLK_TCK)
{
  for pair in station:$STATION tuner:$TUNER listen-early:$EARLY listen-late:$LATE; do
    name=${pair%%:*}; pid=${pair#*:}
    read -r ut st < <(awk '{print $14, $15}' "/proc/$pid/stat")
    awk -v n="$name" -v u="$ut" -v s="$st" -v t="$tick" 'BEGIN { printf "{\"process\": \"%s\", \"cpu_s\": %.2f}\n", n, (u + s) / t }'
  done
} > "$OUT/cpu.jsonl"
ip netns exec "$NA" nft -j list ruleset > "$OUT/nft-station-host.json"
ip netns exec "$NB" nft -j list ruleset > "$OUT/nft-listener-host.json"
kill -0 "$STATION" && log "station pid $STATION still the same process at the end"
kill -TERM "$STATION"; sleep 2
for p in "$TUNER" "$EARLY" "$LATE"; do kill -TERM "$p" 2>/dev/null || true; done
sleep 1
log "done: $OUT"
