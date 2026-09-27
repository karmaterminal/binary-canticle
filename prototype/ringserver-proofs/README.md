# ringserver proofs

Runnable evidence for the SeedLink/ringserver tier discussed in
[`rfc/0001-binary-canticle.md`](../../rfc/0001-binary-canticle.md) and its review notes in
[`rfc/0001-notes/`](../../rfc/0001-notes/).
These are proofs, not product code: each script answers one question against a
real [EarthScope ringserver](https://github.com/EarthScope/ringserver) v4.5.4
built from source.

Tracked by [#49](https://github.com/karmaterminal/binary-canticle/issues/49)
(the native Ringserver/DataLink proof it lists as missing) and
[#12](https://github.com/karmaterminal/binary-canticle/issues/12) (SeedLink dashboards).

## What each proof shows

| # | Script | Question | Result (2026-09-27, ringserver 4.5.4 @ `2df558c`) |
|---|---|---|---|
| 01 | `01_cue_to_datalink.py` | Can a signed UDP cue go through `canticle_receptor` into ringserver over DataLink and be read back? | Yes. Two cues accepted, written as `BC_CUE/JSON`, read back over DataLink. The repeated third send is **rejected as `replay`**, which RFC-0001's carousel semantics must change (a repeat is a no-op). SeedLink `INFO STREAMS` lists `BC_CUE` with format `?`: JSON packets are **not** served over SeedLink. |
| 02 | `02_seedlink_v4_vs_v3.py` | Can a text "thought" reach SeedLink clients? | A miniSEED3 record with encoding 0 (text) and `{"BC":{...}}` extra headers reaches a **SeedLink v4** client intact (`SE3D` packet). On 4.5.4 a **SeedLink 3.1** client gets `SL`+raw miniSEED3 bytes, which a miniSEED2 parser (ews-concept-new) cannot read; ringserver ≥4.5.5 skips miniSEED3 records for 3.x clients instead (ChangeLog v4.5.5). Either way, 3.1 dashboards need miniSEED2 channels. |
| 03 | `03_carrier_writer.py` | Helper: can a carrier wave render as a trace? | Writes 1-sps int32 miniSEED2 records for `XX.CANT..LHZ` (a varying value; ews de-means each record, so a constant carrier would draw flat) plus one ms3 text record. |
| 04 | `04_ttl_window.py` | Can SeedLink v4 act as a late-joiner "what is on air now" query? | Yes. If an item's record span is its TTL (end time = expiry), `DATA ALL <now>` returns only unexpired items: 2 expired + 1 live written, only `live-c` returned. |
| 05 | `05_datalink_websocket.py` | Can a browser-style client read JSON items? | Yes, over DataLink-over-WebSocket at `ws://<ring>:<SLPORT>/datalink`. |
| 06 | `06_ews_parser_repro.mjs` | Where does ews' `Not enought bytes for header, need 47, found 6` come from? | Reproduced byte-exactly: the seisplotjs miniSEED2 parser is fed a WebSocket message that is not exactly one SeedLink packet (a packet + 6 bytes of the next, or `ERROR\r\nERROR\r\n`). One-packet-per-message from ringserver's own `/seedlink` WebSocket parses fine. The third-party `bagusindrayana/seedlink-websocket` proxy forwards raw TCP chunks and causes this. Fix: point ews at ringserver `/seedlink` with its own (currently unused) `src/lib/seedlink-client.ts`. |

Caveats:
- Everything ran on loopback in one sandbox. This says nothing about LAN multicast, NAT or Wi-Fi.
- `XX` is the FDSN test network code and must not be used for anything distributed (see RFC-0001 §18).
- The DataLink proof uses `simpledali`, not `dalitool`, which #49 names; it is the same protocol.

## Run it

```sh
cd prototype/ringserver-proofs
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # also installs ../ringserver-udp-cue in editable mode
npm install                              # optional: seisplotjs + ws for proof 06
PYTHON=.venv/bin/python ./run.sh         # clones + builds ringserver v4.5.4 into .work/ on first run (~1 min)
```

`run.sh` starts ringserver with a 16 MiB in-memory ring (`-NOMM`), 512-byte packets, a
`DataLink SeedLink HTTP` listener on `SLPORT` (default 18000) and a DataLink-only
listener on `DLPORT` (default 16000), then runs the proofs and stops the server.
Override with `DLPORT`, `SLPORT`, `RINGSERVER` (path to an existing binary) and `PYTHON`.
`cryptography>=45` is required by the receptor; older distro packages fail on import.
