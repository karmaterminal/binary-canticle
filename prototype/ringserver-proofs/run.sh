#!/usr/bin/env bash
# Build (once) and start a local ringserver, then run the proofs against it.
#
#   ./run.sh            # build if needed, start ringserver, run proofs 01-05 (+06 if node deps present)
#   ./run.sh build      # only clone + build ringserver v4.5.4 into ./.work/ringserver
#
# Environment: PYTHON (default python3), DLPORT (16000), SLPORT (18000), RINGSERVER (path to binary).
set -euo pipefail
cd "$(dirname "$0")"

WORK=.work
PYTHON=${PYTHON:-python3}
export DLPORT=${DLPORT:-16000}
export SLPORT=${SLPORT:-18000}
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
sleep 1

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
