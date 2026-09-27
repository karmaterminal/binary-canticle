#!/usr/bin/env bash
# Build (once) and start a local ringserver, then run the proofs against it.
#
#   ./run.sh            # build if needed, start ringserver, run proofs 01-05 (+06 if node deps present)
#   ./run.sh build      # only clone + build ringserver v4.5.4 into ./.work/ringserver
#
# Environment: PYTHON (default python3), DLPORT and SLPORT (default: two free ports picked at start),
# RINGSERVER (path to binary). The proofs write synthetic records, so the runner only proceeds once the
# ringserver it started is alive and owns both ports; it never runs against a server it did not start.
set -euo pipefail
cd "$(dirname "$0")"

WORK=.work
PYTHON=${PYTHON:-python3}
free_port() { "$PYTHON" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])'; }
export DLPORT=${DLPORT:-$(free_port)}
export SLPORT=${SLPORT:-$(free_port)}
[[ "$DLPORT" != "$SLPORT" ]] || { echo "DLPORT and SLPORT must differ" >&2; exit 1; }
RINGSERVER=${RINGSERVER:-$WORK/ringserver/ringserver}

build() {
  if [[ -x "$RINGSERVER" ]]; then return; fi
  mkdir -p "$WORK"
  git clone --depth 1 --branch v4.5.4 https://github.com/EarthScope/ringserver.git "$WORK/ringserver"
  make -C "$WORK/ringserver" >"$WORK/build.log" 2>&1
}

build
[[ "${1:-}" == "build" ]] && exit 0

rm -rf "$WORK/ring" && mkdir -p "$WORK/ring"
# 512-byte packets so miniSEED2 512-byte records fit; one port serves SeedLink + HTTP/WebSocket + DataLink.
"$RINGSERVER" -Rd "$WORK/ring" -Rs 16777216 -Rp 512 -NOMM \
  -L "$SLPORT DataLink SeedLink HTTP" -L "$DLPORT DataLink" >"$WORK/ringserver.log" 2>&1 &
RS_PID=$!
trap 'kill $RS_PID 2>/dev/null || true' EXIT

# Proceed only when the process started above is alive and listening on both ports itself.
owns() { ss -ltnpH "sport = :$1" 2>/dev/null | grep -q "pid=$RS_PID,"; }
for _ in $(seq 50); do
  kill -0 "$RS_PID" 2>/dev/null || { echo "ringserver exited; see $WORK/ringserver.log" >&2; exit 1; }
  owns "$DLPORT" && owns "$SLPORT" && break
  sleep 0.2
done
owns "$DLPORT" && owns "$SLPORT" || {
  echo "ringserver (pid $RS_PID) does not own ports $DLPORT and $SLPORT; refusing to run proofs" >&2; exit 1; }
echo "ringserver pid $RS_PID on DataLink $DLPORT, SeedLink/HTTP $SLPORT"

for p in 01_cue_to_datalink.py 02_seedlink_v4_vs_v3.py 04_ttl_window.py 05_datalink_websocket.py; do
  echo "=== $p"
  "$PYTHON" "$p"
done
if [[ -d node_modules/seisplotjs ]]; then
  echo "=== 06_ews_parser_repro.mjs"
  PYTHON="$PYTHON" node 06_ews_parser_repro.mjs
else
  echo "=== 06 skipped (run 'npm install' here for seisplotjs + ws)"
fi
