#!/usr/bin/env bash
# Control experiment: same carousel semantics over (A) raw UDP + minimal relay, (B) NATS core via nats-server.
set -u
D=$(cd "$(dirname "$0")" && pwd); cd "$D"; PY=$D/venv/bin/python; OUT=$D/results; mkdir -p "$OUT"
N=${N:-50}; ITEMS=${ITEMS:-20}; LOOP=${LOOP:-1000}
rss() { awk '/VmRSS/{print $2}' /proc/$1/status 2>/dev/null; }

echo "== A: raw UDP station -> relay -> $N leased listeners (loss 0 and 0.3)"
$PY relay_udp.py --run 42 > $OUT/a_relay.txt & RELAY=$!
sleep 0.5
$PY station.py udp 127.0.0.1:47110 --items $ITEMS --loop-ms $LOOP --run 40 > $OUT/a_station.txt & ST=$!
$PY listener.py udp 127.0.0.1:47111 --n $N --loss 0.0 --join 5 --listen 15 > $OUT/a_listen_loss0.txt & L1=$!
$PY listener.py udp 127.0.0.1:47111 --n $N --loss 0.3 --join 22 --listen 15 > $OUT/a_listen_loss30.txt & L2=$!
sleep 14; echo "rss_kB relay=$(rss $RELAY) station=$(rss $ST) listeners($N)=$(rss $L1)" | tee $OUT/a_rss.txt
wait $L1 $L2 $ST $RELAY
cat $OUT/a_*.txt

echo "== B: NATS core station -> nats-server -> $N subscribers"
rm -rf $D/jsdata; ./bin/nats-server -p 4333 -m 8333 -js -sd $D/jsdata > $OUT/b_server.log 2>&1 & NS=$!
sleep 1; echo "rss_kB nats-server idle=$(rss $NS)" | tee $OUT/b_rss.txt
$PY station.py nats nats://127.0.0.1:4333 --items $ITEMS --loop-ms $LOOP --run 25 > $OUT/b_station.txt & ST=$!
$PY listener.py nats nats://127.0.0.1:4333 --n $N --join 5 --listen 15 > $OUT/b_listen.txt & L1=$!
sleep 14; echo "rss_kB nats-server=$(rss $NS) station=$(rss $ST) listeners($N)=$(rss $L1)" | tee -a $OUT/b_rss.txt
wait $L1 $ST
curl -s localhost:8333/varz | $PY -c 'import json,sys; v=json.load(sys.stdin); print({k:v[k] for k in ["version","in_msgs","out_msgs","in_bytes","out_bytes","mem","connections"]})' | tee $OUT/b_varz.txt
kill $NS; wait $NS 2>/dev/null
cat $OUT/b_station.txt $OUT/b_listen.txt
