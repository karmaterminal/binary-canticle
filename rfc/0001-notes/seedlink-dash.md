# seedlink-dash: SeedLink wire and ecosystem, ews-concept-new, nerv-ui

Reader: seedlink-dash. Date: 2026-09-27. Second attempt; the first attempt stalled before writing anything.

Legend used in every section:
- **[SAYS]** what a source (spec, doc, README, code comment) states.
- **[IMPL]** what code actually does, verified by reading it or running it here.
- **[ASSESS]** my own judgement.

Scratch evidence for this reader lives in `scratchpad/sdash/`. Paths below are relative to `<review-sandbox>/`.
- `sdash/package/`: `seisplotjs@3.2.7` npm tarball, the exact version pinned in `ews-concept-new/pnpm-lock.yaml`.
- `sdash/seedlink-websocket/`: clone of `bagusindrayana/seedlink-websocket` @ `124b52a`, the WS↔SeedLink proxy that ews is configured to use.
- `sdash/writer.py`, `sdash/client.mjs`, `sdash/synth.mjs`: reproduction scripts, run against a local `ringserver 4.5.4` (built by another reader at `rs/ringserver/ringserver`, source tag `2df558c`).

---

## PART B: ews-concept-new (karmaterminal/ews-concept-new @ `c5134cb`)

### B.1 What it is

- **[IMPL]** SvelteKit 2 / Svelte 5 app deployed with `@sveltejs/adapter-cloudflare` (`svelte.config.js:2,11`; `wrangler.toml`). It is MIT licensed (`package.json:7`, `LICENSE`).
- **[IMPL]** The miniSEED parser is **`seisplotjs` ^3.2.7** (`package.json:36`; lock resolves 3.2.7). seisplotjs is MIT (`sdash/package/package.json:105`). `WaveformService.init()` imports it dynamically (`src/lib/services/WaveformService.ts:12-16`).
- **[IMPL]** Upstream is `bagusindrayana/ews-concept-new`: README "Support me" and links; `src/routes/+page.svelte:2282` links to `github.com/bagusindrayana/ews-concept-new`. The karmaterminal repo is a fork or copy.
- **[IMPL]** Hygiene: `wrangler.toml:6-8` commits a public Mapbox `pk.` token plus production URLs. These are `PUBLIC_WEBSOCKET_URL = wss://seedlink-websocket-production.up.railway.app` (the upstream author's Railway deploy) and `PUBLIC_SOCKET_DATA_URL`. The same keys also appear in `.dev.vars` (values not reproduced here).

### B.2 How the browser reaches SeedLink (the live path)

A browser cannot open raw TCP, so ews uses a **WebSocket-to-TCP proxy**. The chain is:

```
browser (realtime/+page.svelte)
   └─ ws(s):// PUBLIC_WEBSOCKET_URL  (default ws://localhost:8080; prod wss://seedlink-websocket-production.up.railway.app)
        └─ bagusindrayana/seedlink-websocket server.js  (Node, ws + net)
             └─ TCP <host>:18000  SeedLink v3 (HELLO / STATION / SELECT / DATA / END)
```

- **[IMPL] Page side.** `src/routes/realtime/+page.svelte`:
  - `:582` sets `seedLinkHost = dataSource.seedLinkHost ?? new URL(dataSource.baseUrl).host`. With the default data source (`geofon`) that host is **`geofon.gfz.de`**.
  - `src/lib/stores/mapStore.svelte.ts:13-40` lists the FDSN data centres. Only three carry an explicit `seedLinkHost`: `rtserve.earthscope.org` (`:15`), `cwbpub.cr.usgs.gov` (`:20`) and `auspass.edu.au` (`:35`).
  - `:584-586` opens `new WebSocket(env.PUBLIC_WEBSOCKET_URL ?? "ws://localhost:8080")` with `binaryType = "arraybuffer"`.
  - `:588-596` on open, it sends **one JSON message** `{host, net, sta, cha}`. It does not speak SeedLink itself.
  - `:598-629` `onmessage`:
    - It drops frames while in demo or historical mode.
    - It decodes the frame as UTF-8. If `text.trim() == "OK"`, it logs "Server OK" (`:611-614`).
    - Otherwise it calls `waveformService.processMiniseed(buf, 10)` (`:617`).
    - On any exception it logs **`Error parsing miniSEED data: ${err}`** (`:625-626`), followed by the text rendering of the frame (`:627`).
  - Channel hexagons (`:771-838`) re-send the JSON with a new `cha` on click (`:799-823`). The waveform buffer is **not** cleared, so the old and new channels mix. The location code is never sent, so every location matching the channel is selected.
- **[IMPL] Proxy side.** `sdash/seedlink-websocket/server.js`:
  - `:11-12` default host is `geofon.de`, and **`SEEDLINK_PORT = 18000` is hard-coded**.
  - `:89-91` on TCP connect it writes `HELLO\r\n`.
  - `:93-116` on the **first TCP `data` event** (whatever part of the HELLO reply that is), it writes `STATION <sta> <net>`, `SELECT <cha>`, `DATA` (or `DATA ALL <start> [<end>]`) and `END` back-to-back. It then flips to `STREAMING` **without ever consuming the per-command `OK`/`ERROR` reply lines**. Pipelining itself is allowed: SeedLink v4 permits "asynchronous handshaking" (`fdsn-seedlink/protocol.rst:77`), and v3.1 had `BATCH`. The bug is that the replies are never read. Also, `DATA ALL <time>` is **v4** syntax (`protocol.rst:262-277`), but the proxy never sends `SLPROTO 4.0`, so a v3 session gets it. v3 time windows use `TIME y,m,d,h,m,s [..]` or `DATA [hexseq [begin]]` (SeisComP `seedlink.rst` Commands).
  - `:117-121` in `STREAMING` state, **every TCP `data` chunk is forwarded verbatim as one WebSocket message** (`ws.send(chunk)`). There is no SeedLink packet framing.
  - `:47-50` a new JSON request destroys the old TCP socket and starts a new handshake.
  - Consequence: WS message boundaries are TCP segment boundaries. They are not SeedLink packet boundaries, and the handshake replies leak into the data stream.
- **[IMPL] Parser side.** `WaveformService.processMiniseed` (`src/lib/services/WaveformService.ts:123-162`):
  - It does `mseedDataBuffer.slice(8)`. This assumes exactly one 8-byte `SLxxxxxx` v3 header at the start of the message and nothing else (`:129`).
  - It then calls `seis.miniseed.parseDataRecords(...)` (`:130`). That function loops `offset += header.recordSize` until the buffer is consumed (`sdash/package/src/miniseed.mts:26-37`). It is a **miniSEED 2 only** parser: `parseSingleDataRecordHeader` reads the 48-byte SEED fixed header plus blockette 1000 (`miniseed.mts:64-131`).
  - Record timestamps come from the header, falling back to `Date.now()` (`WaveformService.ts:139-146`). The sample interval is `1000/header.sampleRate`, falling back to 10 ms (`:148-151`). Samples are de-meaned per record (`:136-137`).

### B.3 The error "Not enought bytes for header, need 47, found 6"

- **[IMPL] Exact throw site.** `seisplotjs/src/miniseed.mts:64-68` (dist `miniseed.mjs`), inside `parseSingleDataRecordHeader`:
  ```ts
  if (dataView.byteLength < 47) {
    throw new Error(`Not enought bytes for header, need 47, found ${dataView.byteLength}`);
  }
  ```
  It is reached from `parseDataRecords` (`miniseed.mts:26-37`) via `WaveformService.processMiniseed` (`WaveformService.ts:129-130`), and the error is logged at `realtime/+page.svelte:625-626`.
- **What "found 6" means.** After `slice(8)`, the parser met a view with only 6 bytes left. That happens in one of two ways:
  1. The WS message was **14 bytes** of non-record text, so 14 − 8 = 6.
  2. The message was **8 + k·recordSize + 6 bytes**: whole record(s), then 6 stray bytes, for example the first 6 bytes (`"SL0000"`) of the *next* SeedLink packet, split by TCP segmentation.
- **[IMPL] Reproduced here** against local ringserver 4.5.4, using the **unmodified** proxy (`sdash/seedlink-websocket/server.js`, `PORT=8090`) and a client that copies ews's `onmessage` + `processMiniseed` logic (`sdash/client.mjs`). Output:
  ```
  === via seedlink-websocket proxy, cha=LHZ
  msg#1 len=12 head="OK\r\nOK\r\nOK\r\n" -> Error parsing miniSEED data: Error: Not enought bytes for header, need 47, found 4
  msg#2 len=1040 head="SL000005000000D CANT" -> Error parsing miniSEED data: RangeError: Invalid DataView length 17170
  ```
  - `msg#1`: the three command replies (STATION, SELECT, DATA) arrive coalesced as one 12-byte message. It is not exactly `"OK"`, so it goes to the parser and gives "found 4".
  - `msg#2`: two 520-byte SeedLink packets arrive coalesced as one 1040-byte TCP chunk. The parser consumes record 1, then reads `"SL000006"+record` as a SEED header and throws `RangeError`.
- **[IMPL] Synthetic cases** built from real ringserver packets (`sdash/synth.mjs`):
  ```
  520 (one SL packet)            -> ok 1 rec
  526 (packet + 6B of next pkt)  -> Error: Not enought bytes for header, need 47, found 6
  14B 'ERROR\r\nERROR\r\n'       -> Error: Not enought bytes for header, need 47, found 6
  12B 'OK\r\nOK\r\nOK\r\n'         -> Error: Not enought bytes for header, need 47, found 4
  514 (tail of split packet)     -> RangeError: Invalid DataView length 8220
  1040 (two packets coalesced)   -> RangeError: Invalid DataView length 17170
  ```
- **[ASSESS] Root cause.** There is no SeedLink framing anywhere in the chain:
  - The proxy forwards raw TCP chunks and never consumes the handshake replies (`server.js:93-121`).
  - The page only filters a bare `"OK"` (`+page.svelte:611`).
  - The service assumes one message = one packet (`WaveformService.ts:129`).

  The exact "found 6" in the GE.PMBT.VHE screenshot is most likely a **526-byte (or 8+n·512+6) TCP chunk**: one packet plus the first 6 bytes of the next. On a WAN link to `geofon.gfz.de:18000`, arbitrary segment boundaries are normal. A **14-byte text frame** such as two `ERROR\r\n` replies is the alternative. I could not tell them apart without the next log line, which `+page.svelte:627` prints (the frame as text). I also could not reach `geofon.gfz.de:18000` from this sandbox (raw TCP timed out), so the remote HELLO/reply chunking is inferred, not observed.
- **[ASSESS] Why a waveform still renders.** Whenever a TCP chunk happens to be exactly 520 bytes it parses. Low-rate channels like VHE (0.1 sps, so one 512-byte record covers many minutes) produce few packets, so most arrive alone and parse. The errors are intermittent noise, not total failure.
- **Fix (ordered by preference).**
  1. **Delete the custom proxy and talk SeedLink-over-WebSocket directly** to a server that frames one packet per WS message. `ringserver`'s `/seedlink` endpoint does this: it accepts subprotocol `SeedLink3.1` or `SeedLink4.0` (`rs/ringserver/src/http.c:621-650`), and each packet goes out as a single WS frame via `SendDataMB` (`clients.c:728-811`, `slclient.c:2150-2200`). ews **already contains an unused client for exactly this**: `src/lib/seedlink-client.ts` (478 LOC).
     - It opens `new WebSocket(url, "SeedLink3.1")` (`:6,324`).
     - It waits for each command's `OK`/`ERROR` (`:384-427`).
     - In data mode it drops frames under 64 bytes and non-`SL` frames (`:429-452`), then parses a single record (`:458-472`). It decodes Steim1/Steim2/int16/int32/float itself (`:115-260`).
     - Nothing imports it (grep over `src/` returns only its own file).
     - Verified here: with the direct WS path (`node client.mjs direct3 LHZ`), each data packet arrives as its own 520-byte message and parses cleanly (`msg#5/#6 ... parsed XX.CANT..LHZ n=60 sr=1 rs=512`). The HELLO banner and `OK\r\n` replies arrive as separate small messages.
  2. If the proxy must stay (GEOFON etc. only expose TCP 18000), make it frame. It should:
     - read reply lines and wait for `OK` per command;
     - keep a reassembly buffer and emit only complete packets. For v3, an `SL` + 6 hex seq packet is 8 + recordLength bytes, with recordLength from blockette 1000 (practically 512). `SLINFO` packets carry XML INFO and should be dropped or routed separately. For v4, `SE` + fmt + subfmt + u32le len + u64le seq + u8 idlen + id, then len bytes.
     - send text replies as WS text frames, not binary.
  3. Defensive client patch in `WaveformService.processMiniseed`:
     - check bytes 0-1 == `"SL"` and `byteLength >= 8+48`;
     - parse one record with `parseSingleDataRecord(new DataView(buf, 8))`, not `parseDataRecords(buf.slice(8))`;
     - keep a carry-over buffer for split packets.
     - Also clear the buffer on channel switch (`+page.svelte:799-823`) and pass the location code.
- **[ASSESS] Secondary bugs noticed.**
  - `DATA ALL <start> <end>` in `server.js:101-105` is v4 syntax (ISO times) used on a v3 session (no `SLPROTO 4.0`). v3 is `TIME <y,m,d,h,m,s> [<end>]` or `DATA [hexseq [y,m,d,h,m,s]]` (see A.2).
  - `/api/fdsn/{station,dataselect,event}` accept any `?url=` http(s) target (`src/routes/api/fdsn/station/+server.ts:82-97,112-131`). That is an open proxy / SSRF surface on the Cloudflare deployment.

### B.4 Other ews paths the task asked about

- **LOAD MINISEED (local file)** `realtime/+page.svelte:415-461`, button at `:843-901`.
  - It reads the file into an ArrayBuffer and calls `processMiniseedRaw(buf, 10, undefined, true)` (`WaveformService.ts:23-121`).
  - This path **does not** strip 8 bytes. It parses the whole file with `parseDataRecords`: miniSEED 2 only, any record length via blockette 1000.
  - Timestamps are sanity-checked, with chaining fallback (`:56-100`). Buffers are not trimmed (`skipTrim=true`).
  - It is the right path to demo a recorded canticle "carrier" archive offline, but only as miniSEED 2.
- **Historical mode** `+page.svelte:325-406` fetches `${baseUrl}/fdsnws/dataselect/1/query?...&network&station&channel` through `fdsnFetch`. `fdsnFetch` tries a direct fetch, then falls back to the SvelteKit proxy `/api/fdsn/dataselect` on CORS failure (`src/lib/utils/fdsnFetch.ts:24-43`). It then calls `processMiniseedRaw`.
- **Station metadata source** `loadDataStation` `+page.svelte:465-547`:
  - It fetches **FDSN StationXML** from `${dataSource.baseUrl}/fdsnws/station/1/query?network&station&level=response&format=xml`.
  - It converts XML to JSON (`$lib/xmlUtils`) and keeps the open-ended epoch (no `endDate`).
  - It builds `listChannel` and picks the default channel by priority `BHZ`, `SHZ`, `HHZ`, then the first active channel (`:525-540`).
  - **The WS request needs `selectedChannel["@attributes"].code`** (`:593`). If StationXML fails, `selectedChannel` is undefined and `ws.onopen` throws. So a canticle station needs a StationXML endpoint, or a patch.
  - The route is `/realtime?networkCode=..&stationCode=..&source=<host substring of a DATA_SOURCES baseUrl>` (`src/routes/realtime/+page.ts:5-10`, `+page.svelte:562-575`).
- **Channel hexagons** `+page.svelte:771-838` use `HexGrid`/`HexShape` (`src/lib/components/HexGrid.svelte`, 449 LOC; `HexShape.svelte`). There is one hex per StationXML channel code. Orange means an open epoch, red a closed one. The selected channel blinks. Clicking re-requests the stream.
- **ESP32 paths** (two, both Web Serial at 115200 baud):
  - (a) `realtime/+page.svelte:226-322` **reads** newline-delimited JSON `{p1,p2,p3}` (12-bit pots, 0..4095, deadband below 50). A lerp loop maps them to Y-zoom, time window (2 s..300 s) and pan offset (`:193-224`). The ESP32 is a physical knob box.
  - (b) `src/lib/stores/serialStore.ts:22-54` **writes** JSON lines to the ESP32 when `demoStore.gempaAlert` fires (`:58+`). It is an alert annunciator. `SerialStatus.svelte` is mounted on the home page (`src/routes/+page.svelte:37,1191`).
- **Alerts and chatter side-channel** (not SeedLink). The home page connects **socket.io** to `PUBLIC_SOCKET_DATA_URL` (upstream `bagusindrayana/ews-socket`) and handles events `warning`, `message`, `gempa` and `tsunami` (`src/routes/+page.svelte:462-468`). **[ASSESS]** This is the natural sink for discrete canticle TTL items (text/JSON "chatter"), because the waveform path is for numeric series.
- **Event-detail / intensity** `src/routes/event-detail/[slug]/+page.svelte`:
  - It calls `loadEarthquakeDetail(slug)` (`src/lib/utils/mmiParser.ts`), which fetches `/api/earthquakes` and BMKG sources (`cdn.bmkg.go.id`, `bmkg-content-inatews.storage.googleapis.com`). It parses BMKG `stationlist_MMI.txt` into `StationItem{mmi, pgaEw/Ns/Ud, status}` (`mmiParser.ts:1-40`).
  - It renders them through `MagiBusBoard` and `MentalToxicityLevel`. Each station becomes `{active_channel: 10-mmi, inactive_channel: mmi, total_channel: 10}` (`+page.svelte:107-118`), plus `ContourMapCanvas` intensity contours and a table (`:471-505`).
  - **[ASSESS]** This is a reusable "per-agent intensity board". A canticle "threat" lens could map to MMI-like 0..10 intensity per receiving station/agent.
- **Other routes:** `/magi` (MAGI status display, `MagiStatusDisplay.svelte`, `MagiBus*`), `/status-map`, `/status-node`, `/status-ui`, `/3d-map`, `/event-map`, `/showcase`. **[ASSESS]** `/magi` + `MagiBusBoard` is the obvious NGE-MAGI "aspected thought" panel for canticle lenses, with no SeedLink needed.

### B.5 What a canticle station must emit for ews to render it (effort assessment)

**[IMPL] Verified here against ringserver 4.5.4** (`node client.mjs direct3|direct4|proxy`, output in B.3):

| What canticle writes into ringserver (DataLink) | What a v3 client (ews) receives | ews result |
|---|---|---|
| miniSEED **2**, 512 B, int32, 1 sps, `XX.CANT..LHZ` (streamid `FDSN:XX_CANT__L_H_Z/MSEED`) | `SL00000B` + 512 B (520 B/msg on WS) | **parses and renders**: `XX.CANT..LHZ n=60 sr=1 rs=512` |
| miniSEED **3** text record (encoding 0), SID `FDSN:XX_CANT__L_O_G` (`/MSEED3`), 129 B | `SL000010` + 129-B ms3 record (**no 3→2 down-conversion**) | **fails**: `RangeError: Start offset 22586 ...`. seisplotjs `miniseed` is ms2-only |
| same, over a **v4** client (`SLPROTO 4.0`) | `SE3D` + len + seq + `XX_CANT` + ms3 | ews has no v4 parser. It would need `seisplotjs.seedlink4` + `mseed3` |

- **[IMPL]** ringserver's v3 path sends any record that is valid ms2 **or** ms3 with an `SL%06X` header (`slclient.c:569-570,667,2190-2194`). It only *up*-converts 2→3 on request (`slclient.c:631-664`), never 3→2. So a v3 dashboard **must** be fed miniSEED 2 records, or the station must duplicate numeric channels as ms2.

**Minimum for ews live view of a canticle station:**
1. Numeric **miniSEED 2** records (512 B, blockette 1000; int32 or float32; Steim not required) on a SEED channel name. The dashboard's hex grid and waveform key on `NET.STA.LOC.CHA`.
2. A **StationXML** document at `<baseUrl>/fdsnws/station/1/query` listing those channels, plus a `DATA_SOURCES` entry (`mapStore.svelte.ts:13-40`) with `seedLinkHost`. Otherwise `selectedChannel` is undefined (`+page.svelte:593`). ringserver does not serve StationXML, so this is a tiny static file or a 20-line endpoint.
3. A WS endpoint. Either ringserver `/seedlink` with ews switched to `seedlink-client.ts` (recommended), or the proxy fixed per B.3.
4. **Sample-rate semantics.** ews de-means each record (`WaveformService.ts:136-137`). A constant carrier would flatten to 0. Emit a **varying** value, e.g. a sine or sawtooth phase, or a quantity that moves: queue depth, live-item count, sum of remaining TTL seconds, salience. At **1 sps (`L` band)**, a 512-B int32 record holds up to 112 samples, so latency is up to ~2 min before a record fills. At 1 sps, ringserver/libmseed writers normally flush on a timer, so emit **short records** (e.g. 5-10 samples each) to keep the trace "live". ews does not care about record fullness (verified with 60-sample records).

[ASSESS] Effort:
- ~0.5 day to point ews at a local ringserver + static StationXML + a 1-sps carrier (switch `realtime` to `seedlink-client.ts` or fix the proxy).
- ~1-2 days to add a text/JSON lane (socket.io `message`/`warning` events, or seisplotjs `mseed3`/`seedlink4` for `LOG` channels).

---

## PART A: SeedLink, miniSEED and ringserver (the wire and ecosystem inspiration)

Source handling. `docs.fdsn.org`, `www.seiscomp.de`, `www.iana.org`, `folkworm.ceri.memphis.edu` and `manual.raspberryshake.org` were **egress-blocked** here. I therefore read the specs from their canonical GitHub sources:
- `FDSN/seedlink` @ `b57d317` (2025-02-06). This is the source of https://docs.fdsn.org/projects/seedlink/en/latest/protocol.html, cloned to `sdash/fdsn-seedlink/`.
- `FDSN/miniSEED3` @ `b306f6c` (2026-04-27), in `sdash/fdsn-ms3/`.
- `FDSN/source-identifiers` @ `1712638`, in `sdash/fdsn-sid/`.
- `SeisComP/seedlink` @ `5abc328` (2026-09-17), sparse, in `sdash/sc-seedlink/`.
- `EarthScope/ringserver` v4.5.4 `2df558c`, in `rs/ringserver/`.
- `raspishake/rsudp`, in `sdash/rsudp/`.

Earthworm facts come from web-search snippets only; they are marked as such.

### A.1 SeedLink v4 (FDSN spec) **[SAYS]**

- **Transport: TCP only.** "SeedLink communication takes place over TCP/IP connections. The default port is TCP 18000 … and 18500 when using TLS" (`fdsn-seedlink/protocol.rst:12`).
  - WebSocket (RFC 6455) is an optional appendix (`:442-454`). Commands and replies go as text messages of 1 frame. **Each packet, INFO included, goes as a binary message of 1 frame** (`:450`). The server MAY switch to HTTP/WS if the first command is an HTTP verb (`:69`).
  - There is **no UDP transport anywhere in the spec.**
- **No formal v3 spec.** "There is no formal specification of earlier versions" (`:14`).
- **Handshake.**
  - The server sends nothing until the client speaks (`:69`).
  - Commands are ASCII lines ending CRLF, max 255 chars, case-insensitive (`:71-73`, `:244`).
  - Every command except HELLO, INFO, END and ENDFETCH answers `OK` or `ERROR <CODE> [desc]` (`:75`).
  - Pipelining ("asynchronous handshaking") is allowed (`:77`).
  - Commands:

    | Command | Notes |
    |---|---|
    | `AUTH USERPASS|JWT` {CAP:AUTH} | `:248` |
    | `BYE` | `:259` |
    | `DATA [seq [start [end]]]` | `seq` may be `ALL`; ISO-8601 `…Z` times need the TIME cap; filter is `packet.end_time > start_time` (`:262-277`) |
    | `END` (real-time) / `ENDFETCH` (dial-up, server sends bare `END` after queued data) | `:279-284`, `:229` |
    | `HELLO` | Two lines; line 1 `SeedLink vX.Y (impl) :: SLPROTO:A.B …` (`:285-292`) |
    | `INFO ID|FORMATS|CAPABILITIES|STATIONS|STREAMS|CONNECTIONS` | Returns one JSON packet (format `J`, subformat `I`/`E`); "INFO ID" is recommended as keep-alive (`:294-301`) |
    | `SELECT [!]stream_pattern[.fmt_subfmt][:filter]` | Filters `native` and `3` (convert to ms3) (`:331-360`) |
    | `SLPROTO 4.0` | Mandatory first in v4 (`:362`) |
    | `STATION pattern` | `:365` |
    | `USERAGENT` | `:390` |

  - Error codes: UNSUPPORTED, UNEXPECTED, UNAUTHORIZED, LIMIT, ARGUMENTS, AUTH, INTERNAL (`:399-422`).
  - Capabilities: `SLPROTO:x.y`, `AUTH:type`, `TIME`, `SEQWILDCARD` (`:424-440`).
- **Naming.**
  - Station ID `NET_STA`; stream ID `LOC_B_S_SS` (`:45`). The spec calls these "agnostic to other standards … or within closed ecosystems" (`:47`).
  - Wildcards are `*` and `?`, anchored (`:49-53`).
- **Packet framing (v4)** (`:182-193`):

  | Bytes | Field |
  |---|---|
  | 2 | `"SE"` |
  | 1 | format |
  | 1 | subformat |
  | 4 | u32 LE payload length |
  | 8 | u64 LE sequence |
  | 1 | u8 station-ID length |
  | n | station ID |
  | … | payload |

  Reserved format codes (`:199-225`):
  - `2` = miniSEED 2 (subformats D/E/C/T/L/O: data, event, calibration, timing, log, **opaque**);
  - `3` = miniSEED 3 with FDSN SID (D);
  - `4..9` reserved;
  - `J` = JSON (I info / E error);
  - `X` = XML.

  Other codes "can be assigned dynamically" and are discovered via `INFO FORMATS` (`:227`). The payload is "usually a miniSEED record, but other formats are possible, as long as they include time and stream identification" (`:39`).
- **Sequence numbers.**
  - 64-bit, per station, strictly increasing and SHOULD be consecutive; resumable across sessions on the same server (`:59-63`).
  - "a gap in sequence numbers does not imply missing packets" (`:63`).
  - Reconnection examples, including a shared server-wide seq space with wildcards (`:128-176`).
- **v3 → v4 differences** (`:478-510`): new header; variable-length packets; decimal (not hex) seq; JSON INFO instead of XML; AUTH, SLPROTO, USERAGENT. Removed: BATCH, CAPABILITIES, CAT, INFO GAPS and TIME, the last replaced by `DATA … start end`. A v4 server can still serve v3 clients (`:480`).

### A.2 SeedLink v3 (SeisComP implementation doc) **[SAYS]**

All citations below are to `sc-seedlink/apps/seedlink/descriptions/seedlink.rst`.
- "The SeedLink protocol is based on TCP" (`:3`).
- **Packets:** "an 8-byte SeedLink header followed by a 512-byte miniSEED record. The SeedLink header is an ASCII string consisting of the letters "SL" followed by a six-digit hexadecimal packet sequence number" (`:189-191`).
  - Sequence numbers are per station and wrap at `FFFFFF` (`:200`).
  - "no error detections or flow control because these functions are performed by the TCP protocol" (`:207-208`).
  - In dial-up mode the server appends `END` after the last packet (`:216-219`).
  - The 512-byte record length is hard-coded (`MSEED-RECLEN`) (`:28-32`).
- **Commands:**
  - `HELLO` (2 lines) (`:227`);
  - `CAT` (`:230`);
  - `BYE`;
  - `STATION sta [net]`, which enables multi-station mode (`:236`);
  - `SELECT [pattern]` with the `LLCCC.T` selector syntax, T ∈ `DECOTL` (`:242-246`);
  - `DATA [n [begin time]]` with time as `year,month,day,hour,minute,second` (`:248`);
  - `FETCH [n [begin]]` for dial-up (`:251`);
  - `TIME [begin [end]]` (`:254`);
  - `INFO level`, which returns **XML embedded in a miniSEED log record** (`:257`).
- **INFO framing in v3 [IMPL]:** ringserver sends INFO as miniSEED 2 records with header `"SLINFO *"` (more to come) or `"SLINFO  "` (last) (`rs/ringserver/src/slclient.c:2282-2284`). **These are 8-byte headers that start with `SL` but are not data. A naive `SL`+seq parser must special-case them.**
- **UDP in the SeeLink ecosystem [SAYS].** UDP appears only on the *ingest* side, digitizer → server, via SeisComP seedlink plugins:
  - Quanterra **Q330 (UDP/IP)** (`sc-seedlink/plugins/q330plugin/descriptions/seedlink_q330.xml:19,31`);
  - **Güralp SCREAM!** "By default the data is received via UDP" on port 1567 (`plugins/scream_plugin/descriptions/seedlink_scream.xml:5,15,21`);
  - NIED **WIN** "UDP port to receive data packets", default 18000 (`plugins/win_plugin/descriptions/seedlink_win.xml:6-8`);
  - GFZ **GDRT** "converts GDRT UDP messages to miniSEED channels", port 9999 (`plugins/gdrt_plugin/descriptions/gdrt_plugin.xml:14,119-121`).
  - There is **no UDP *client-facing* SeedLink variant**. `slarchive`/`slinktool` are TCP clients.
- **Other UDP precedents.** These are the closest analogues to canticle's "lossy radio":
  - **Earthworm `ringtocoax`/`coaxtoring`** (web-search snippets of https://folkworm.ceri.memphis.edu/ew-doc/ovr/ringtocoax_ovr.html and `ringtocoaxII_cmd.html`; not fetched): these broadcast shared-memory "transport ring" messages as **UDP broadcast** on a LAN. A message of 1466 bytes or less goes in one datagram; longer ones are fragmented and reassembled. There is never more than one message per datagram. They are designed for short-distance LAN replication. **[ASSESS]** This is a 25-year-old precedent for "ring buffer replicated by lossy LAN UDP". The known failure mode is gappiness under loss (see the forum thread "coax2ring gappiness issues"). Earthworm inter-site `import/export_generic` are TCP.
  - **Raspberry Shake UDP "datacast"** (`sdash/rsudp/rsudp/raspberryshake.py:17,226,236-342`): default port 8888. Each datagram is a text-ish packet `b"{'EHZ', 1582315130.292, 14168, 14927, …}"`, i.e. channel, epoch time, samples. It is received with `recvfrom(2048)`. This is a live, lossy UDP time-series feed used by hobbyist dashboards: exactly the shape of a canticle carrier.

### A.3 miniSEED 2 vs 3 **[SAYS]**

- **miniSEED 2** (SEED 2.4 data-only):
  - 48-byte fixed header: 6-char ASCII seq, quality, reserved, STA(5) LOC(2) CHA(3) NET(2), BTIME, nsamp, rate factor/multiplier, flags, number of blockettes, time correction, data offset, first blockette offset.
  - Blockette 1000 gives encoding, word order and record length 2^n. Records are typically 512 B for SeedLink and 256-4096 B in general.
  - The seisplotjs parser mirrors this layout (`sdash/package/src/miniseed.mts:64-131`). ews's own parser does the same (`ews-concept-new/src/lib/seedlink-client.ts:57-113`). Hence "need 47".
  - Text: SEED encoding 0 is ASCII text. libmseed now names it `DE_TEXT` (UTF-8) (`rs/ringserver/libmseed/libmseed.h:1533,1543`). SeedLink v3 carries station console logs as `LOG` channel records with encoding 0 (SELECT type `L`).
- **miniSEED 3** (`fdsn-ms3/definition.rst:22-70`):
  - All little-endian. Total length = 40 + len(SID) + len(extra headers) + len(payload).
  - Fixed 40 B: `MS`, version 3, flags, start time (ns u32, year u16, doy u16, h, m, s), **encoding u8 @15**, **sample rate/period f64 @16** (negative = period), nsamp u32, **CRC-32C u32 @28** over the record with the CRC field zeroed (`:150-155`), publication version, SID length u8, extra-header length u16, payload length u32.
  - Then the **SID** (URI, "commonly" an FDSN SID, `:189-194`), then **extra headers = compact JSON** (`:196-207`), then the payload.
  - No padding is allowed in the record (`:183-186`).
- **Encodings** (`fdsn-ms3/data-encodings.rst:11-31`):
  - **0 = "Text, UTF-8 allowed … no structure defined"**;
  - 1 = int16, 3 = int32, 4 = f32, 5 = f64;
  - 10/11/19 = Steim-1/2/3;
  - **100 = "Opaque data - only for use in special scenarios, not intended for archiving"**.
- **Extra headers** (`fdsn-ms3/extra-headers.rst:11-58`): an anonymous JSON object. The key `"FDSN"` is reserved. Other organisations "should" use their own root key, e.g. `"BC"`/`"Canticle"`, and publish a JSON Schema.
- **Can arbitrary non-seismic JSON ride miniSEED 3? Yes.**
  - **[SAYS]** Encoding 0 (text) is spec-sanctioned. Put the JSON document in the payload, set nsamp to the byte count, and put per-item metadata (TTL, lens, loop Hz) in extra headers.
  - **[IMPL]** Verified here: a 129-byte ms3 text record with extra headers `{"BC":{"ttl":60}}` and SID `FDSN:XX_CANT__L_O_G` was written via DataLink and delivered over SeedLink v4 as `SE3D…` (`sdash/client.mjs direct4`, and the other reader's `dlproof/sl_data.py` + `proof.out`).
  - **[ASSESS] Caveats:**
    - a v3 client or seisplotjs `miniseed` (ms2) cannot parse it (B.5);
    - the FDSN `X`/`Y` source codes are deprecated (`fdsn-sid/channel-codes.rst:614-673`);
    - network `XX` "is reserved for test data … Data with this network code should never be distributed" (`fdsn-sid/network-codes.rst:71-73`).
- **FDSN SID** (`fdsn-sid/definition.rst:48-80`): `FDSN:<net>_<sta>_<loc>_<band>_<source>_<subsource>`, e.g. `FDSN:IU_COLA_00_B_H_Z`. Single-char B/S/SS map 1:1 to SEED 2.4 `CHA` (`channel-codes.rst:37-40`).
  - Band codes relevant to canticle (`channel-codes.rst:43-93`): **L ≈ 1 sps** (a 1 Hz carrier), **V 0.1-1 sps** (a ~0.1 Hz payload cadence), **U 0.01-0.1**, and **I = irregularly sampled** (discrete TTL items).
  - Reserved special channels (deprecated): **`L_O_G`** (console log) and **`S_O_H`** (state of health) (`channel-codes.rst:35-36`).
  - Source `E` = "Electronic Test Point … Subsource: designate as desired" (`channel-codes.rst:291-308`). **[ASSESS]** This is the least-bad FDSN-legal code for a synthetic carrier or health trace, e.g. `L_E_C`.

### A.4 ringserver (EarthScope) **[SAYS]** + **[IMPL]**

- **What it is.** A "Generic packet ring buffer with network interfaces … The supported protocols are all TCP-based: DataLink, SeedLink and HTTP/WebSocket" (`rs/ringserver/README.md:1-5`). The ring is a FIFO in which new packets push old ones out, and the payload is format-agnostic (`README.md:7-9`). The buffer is a memory-mapped file that survives restarts, or it can be `-VOLATILE` (`doc/ringserver.md:40,119-120`).
  - **Eviction is by size (`RingSize`), not by TTL.** **[ASSESS]** So canticle TTL must be enforced by readers or by time-window requests (see A.6).
- **Feeding it.** Via **DataLink** (TCP, default 16000) or the built-in miniSEED file scanner (`README.md:72-75`).
  - DataLink framing: a `DL` preamble, a 1-byte header length and an ASCII header (`sdash/../venv-dali/.../simpledali/socketdali.py:29`).
  - Write command: `WRITE <streamid> <hpdatastart> <hpdataend> <flags A|N> <size>` (`simpledali/abstractdali.py:137`).
  - Stream-ID conventions: `FDSN:NET_STA_LOC_B_S_SS/MSEED`, `…/MSEED3`, or any label such as `…/JSON` (`abstractdali.py:151-214`). Other commands: `POSITION SET|AFTER`, `MATCH`, `REJECT`, `READ`, `STREAM`, `ENDSTREAM`, `INFO`, `AUTHORIZATION`.
  - Write permission is limited by `WriteIP`, localhost by default (`README.md:79-83`; `doc/ringserver.md:128-147`).
  - Tools: `slink2dali`, `ew2ringserver`, `orb2ringserver`, `libdali` (C), `simpledali` (Python) (`README.md:86-101`).
- **Serving.**
  - `-L 18000` serves all protocols on one port; `-DL 16000` is the DataLink listener (`README.md:66-71`).
  - HTTP endpoints: `/id`, `/streams`, `/status`, `/connections`, **`/seedlink` and `/datalink` WebSocket upgrades** (`README.md:121-135`).
  - Accepted subprotocols: `SeedLink4.0`/`SeedLink3.1` (`src/http.c:621-650`) and `DataLink1.1`/`DataLink1.0` (`http.c:696-707`).
  - CORS through `HTTPHeader "Access-Control-Allow-Origin: *"` (`doc/ring.conf:422`).
  - TLS via `TLSCertFile`/`TLSKeyFile`.
  - **HAProxy PROXY protocol v2 per listen port** (`doc/ringserver.md:227`; `doc/ring.conf:53-67`, `ListenPort <port> [DataLink] [SeedLink] [HTTP] [IPv4] [IPv6] [TLS] [PROXYv2] [TRUSTED]`).
  - IP ACLs: `AcceptIP`, `DenyIP`, `AllowedStreamsIP`, `ForbiddenStreamsIP`, `WriteIP`, `TrustedIP`. Auth via `AuthCommand` (USERPASS or JWT, checked by an external command) and `AuthRequiredForStreams` (`doc/ringserver.md:128-170`).
- **Sequence semantics [IMPL].**
  - One shared packet-ID space for all streams.
  - v4 seq = the ring packet ID (u64). v3 seq = the low 24 bits (`src/slclient.c:6-27`), emitted as `SL%06X` (`:2190-2194`).
  - v4 header built at `:2170-2186`.
  - **External packet IDs** (DataLink 1.1) let "multiple servers … share common packet IDs for use with a network load balancer" (`doc/ringserver.md:356-362`).
- **Format rules [IMPL].**
  - SeedLink clients only ever see packets whose ring stream ID ends in `/MSEED` or `/MSEED3` (`slclient.c:2399-2400` regex), with a valid ms2/ms3 header (`:569-570`).
  - **`/JSON` packets are DataLink-only.**
  - ms2→ms3 conversion happens on request (`SELECT …:3`) (`:631-664`). **There is no ms3→ms2 path.** A v3 client is sent raw ms3 records behind an `SL` header (reproduced in B.5).
- **Verified here [IMPL]:**
  - (a) ms2/ms3 over SeedLink v3 and v4, TCP and WS (B.3, B.5);
  - (b) **a JSON TTL item written via DataLink TCP is readable by a browser-style DataLink-over-WebSocket client** at `ws://…:18000/datalink` (`sdash/dlws.py`: `ws read: PACKET XX_CANT_LENS_HEALING/JSON 23 {"station": "XX_CANT", "lens": "healing", …}`);
  - (c) the TTL-window trick in A.6.
  - Build: `rs/ringserver/ringserver -V` gives `ringserver version: 4.5.4`.

### A.5 Reconciling "UDP + SeedLink" **[ASSESS]**

SeedLink is not a UDP protocol and never was. v3 and v4 are TCP (plus WebSocket over TCP), with ordered, reliable, resumable delivery (A.1, A.2). What the owner wants is **SeedLink's model** plus a lossy radio: station/stream naming, seq and head, format-tagged self-describing records, loop and replay. That is precisely Silas's reading in `binary-canticle/spike/silas-seedlink-mapping.md:30-38`: "SeedLink's value is the *conceptual model*, not the wire protocol."

The coherent shape is **two tiers joined at a ring**:

```
 LIVE / LOSSY (UDP)                         REPLAY / CATCH-UP / DASHBOARDS (TCP, WS)
 ─────────────────                          ────────────────────────────────────────
 station ──UDP datagrams──► hearers          relay/"membrane" ──DataLink WRITE──► ringserver
   • carrier-beacon 1 Hz (~35 B CBOR,          (a canticle hearer that also           │  SeedLink v3/v4 :18000 (TCP)
     stations-and-streams-v0.2.md:17-32)        writes what it hears)                 │  SeedLink/DataLink over WS
   • payload frames (TTL items), looped                                               │  (/seedlink, /datalink), HTTP /streams
   • LAN: broadcast/multicast; WAN: unicast                                           ▼
     fan-out to registered listeners           ews / nerv-ui consoles, slinktool/slarchive, obspy, seisplotjs
```

- **UDP tier.**
  - Keep canticle's own frames (CBOR carrier-beacon, payload frames) as the authority. Optionally allow the payload bytes to be a **miniSEED 3 record**, which is self-delimiting (payload length field) and self-checking (CRC-32C). Then a relay can write the datagram body into ringserver unchanged (`writeMSeed3`), and the "lossless mapping" is the identity.
  - Datagram budget: stay under ~1200 B for internet paths (IPv6 minimum MTU is 1280). Earthworm's 1466-B LAN rule is the historical analogue.
  - Loop and re-broadcast cadence is a sender concern. The ring stores **one** copy per item, not every loop repetition: dedupe by item id or ms3 CRC at the relay.
- **TCP/WS tier (ringserver).** It provides:
  - replay/catch-up by seq (`DATA <seq>`) or time (`DATA ALL <iso>`);
  - browser access (WS);
  - ACLs and auth;
  - PROXYv2 behind HAProxy.

  It is also the only thing the existing dashboards can consume.
- **Why not SeedLink over UDP.** SeedLink's resume semantics assume an ordered byte stream. Its v3 framing has no length field: the record length sits in blockette 1000 inside the payload. Its commands are request/response. Faking it over UDP would just re-invent TCP badly. Earthworm's UDP ring replication "gappiness" is the cautionary precedent.
- **LAN multicast practicality** (brief; network readers own this):
  - Link-local broadcast or IPv4 multicast works on a flat L2 LAN without special hardware.
  - Crossing subnets needs IGMP/PIM-capable routers.
  - Internet multicast is effectively unavailable.
  - The internet listener story is therefore unicast fan-out from a relay, or TCP/WS from ringserver.
  - HAProxy 3.5 community (the config manual another reader saved at `scratchpad/haproxy-conf.txt`) uses UDP only for QUIC and log forwarding (`:269,1530-1542,1598,1684-1704`). It fits the TCP tier (PROXYv2 + ACL + rate limits) and not the UDP one.

### A.6 A useful protocol coincidence: SeedLink time windows can serve as a TTL filter **[IMPL] + [ASSESS]**

- The v4 `DATA` filter is `packet.end_time > start_time` (`fdsn-seedlink/protocol.rst:268-273`). If a canticle item's record **end time = its expiry** (ms3 text record with `sampleRate = nbytes / ttl`, so the span equals the TTL), then `DATA ALL <now>` returns **exactly the unexpired items**. That is a late-joiner "what's still on air" query for free.
- Verified against ringserver 4.5.4 (`sdash/ttlwin.py`). I wrote three items (two expired, one live) and requested `DATA ALL 2026-09-27T07:29:19.0Z`; the output was `received: b'SE3D' FDSN:XX_TTL__L_O_G {"item":"live-c","ttl":300}` only.
- [ASSESS] Caveat: this bends "sample rate" semantics. It is fine for an `L_O_G`/`I`-band text channel, but do not do it on channels meant for waveform plotting.

---

## PART C: nerv-ui (karmaterminal/nerv-ui @ `b0009c5`, 2026-08-31)

- **[IMPL] Identity.** npm package **`@mdrbx/nerv-ui` 1.0.8**, **MIT** (`package.json:2-7`; `LICENSE` "Copyright (c) 2026 NERV-UI Contributors").
  - Upstream is `github.com/mdrbx/nerv-ui` (`package.json:8-11`). The karmaterminal repo is a fork or mirror at the same 1.0.8 (`CHANGELOG.md` `[1.0.8] - 2026-08-28`).
  - It is published: `npm view` returns version 1.0.8, license MIT, modified 2026-08-28.
  - README disclaimer: "an independent fan-inspired open-source project … not affiliated with … Neon Genesis Evangelion" (`README.md:257`).
- **[IMPL] How to consume.**
  - Install with `npm install @mdrbx/nerv-ui framer-motion`.
  - Import `@mdrbx/nerv-ui/styles.css` once. Tailwind is optional, via `@mdrbx/nerv-ui/tailwind.preset`.
  - Peer dependencies: React 18/19, `framer-motion` 11/12, optional Tailwind 3.4/4 (`package.json:78-87`; `skills/nerv-ui/SKILL.md:13-36`).
  - Builds as ESM + CJS via `tsup` (`package.json:35-57`), with `"use client"` components for Next.js.
  - **React-only.** It cannot drop into ews (Svelte 5) or OpenClaw's Control UI (Lit 3.3.3, `openclaw/ui/package.json`) without a React island.
- **[IMPL] `skills/` directory.** It holds one canonical skill, `skills/nerv-ui/SKILL.md` (92 lines), plus `references/component-catalog.md` and `references/recipes.md`. It is exposed by symlink at `.claude/skills/nerv-ui` and `.agents/skills/nerv-ui` (`SKILL.md:38-65`). This is also the `nerv-ui` skill available in this session.
  - Rules: black surfaces, squared corners; orange for hierarchy, cyan/green for live data, red only for exceptional states; reduced-motion respected; "use invented operational copy … never use assets, layouts, or text copied from another project or show" (`SKILL.md:67-74`).
  - Catalogue of 48 exports (`SKILL.md:76-80`). Recipes: dashboard, monitoring terminal, authentication (`references/recipes.md`).
- **Components useful for a canticle ops console** (props read from `src/components/*/*.tsx`):

  | Need | Component | Fit / caveat |
  |---|---|---|
  | Aspected-thought lenses (MAGI) | `MagiSystemPanel` `{votes: {name, status: "idle"\|"computing"\|"accepted"\|"rejected"}[], trapezoidal}` (`MagiSystemPanel.tsx:6-22`) | Map three lenses (e.g. threat / healing / now) to three units; status = lens activity. |
  | Live chatter / log console | `TerminalDisplay` `{lines: string[], color, typewriter, maxHeight, showLineNumbers, prompt}` (`TerminalDisplay.tsx:6-29`) | Render decoded TTL items; drop lines on expiry. |
  | Item table | `DataGrid` `{columns, data, autoScroll, color}` (`DataGrid.tsx:6-30`) | station:stream, seq, TTL remaining, loop Hz. |
  | TTL countdown | `CountdownTimer` `{initialSeconds, onExpire}`; `SegmentDisplay` `{value, countdown, format, criticalThreshold}` | Per-item TTL / expiry. |
  | Gauges / pressure | `Gauge` `{value,min,max,threshold,variant}`; `GradientStatusBar` `{value, zones[]}`; `SyncProgressBar`; `BarChart` `{bars}` | Chemokine "concentration" per lens, relay loss %, listener count. |
  | Station health grid | `PhaseStatusStack` `{phases:[{label,status: ok\|warning\|danger\|inactive}]}`; `SurveillanceGrid` `{feeds:[{id,label,status: active\|signal-lost\|warning\|offline}]}` | Carrier-drop → `signal-lost`. |
  | Threat banner | `PatternAlert` `{designation, pattern, bloodType, visible}`; `EmergencyBanner`; `StatusStamp` | "Security threat" broadcast state. |
  | Hex texture | `HexGridBackground` `{hexSize, color, animated}` (`HexGridBackground.tsx:11-21`) | **Decorative only.** For interactive per-channel hexagons, use ews's `HexGrid`/`HexShape`. |
  | Waveform / oscilloscope | **none.** `SyncRatioChart` draws two *synthetic* sine waves from `frequencyA/B, amplitudeA/B, phaseA/B` (`SyncRatioChart.tsx:6-30`) and takes **no sample data**. | For real traces, use seisplotjs `animatedseismograph.createRealtimeDisplay` (`sdash/package/src/animatedseismograph.mts:84-184`; framework-agnostic custom elements) or ews's canvas `WaveformChart.svelte` (716 LOC). |

- **[ASSESS] Recommendation.**
  - The quickest demo is **ews** (Svelte): it already has the SeedLink WS client (unused), the waveform canvas, hex channels, MAGI bus boards and a socket.io alert lane.
  - For a standalone **React** canticle console, use nerv-ui for chrome and status, and seisplotjs (MIT) for WS SeedLink/DataLink clients and the realtime seismograph.
  - For in-OpenClaw surfaces (Lit), use seisplotjs custom elements directly. nerv-ui does not fit there.

---

## RECOMMENDATIONS

### R1. Minimal SeedLink-compatible surface: borrow, don't build

1. **Run ringserver 4.5.x as the station's (or relay's) replay tier.** Do not implement SeedLink.
   - `ringserver -Rd ring -L "18000 SeedLink HTTP" -DL "16000 DataLink"`, plus `HTTPHeader "Access-Control-Allow-Origin: …"`, TLS on 18500, and `WriteIP` = relay only.
   - Put it behind HAProxy (TCP mode) with `PROXYv2` on the listen port (`doc/ringserver.md:227`).
   - This gives SeedLink v3 + v4, DataLink, WS for browsers, INFO/streams JSON, resume by seq/time, and ACLs, for free.
2. **Canticle relay = UDP hearer + DataLink writer.** It listens on the canticle UDP surface, dedupes looped re-broadcasts (same item id / ms3 CRC), and writes:
   - **(a) the carrier** as a **miniSEED 2** numeric channel (512-B records, int32, 1 sps) so v3 dashboards (ews) render a live heartbeat;
   - **(b) TTL items** as **miniSEED 3 text** (encoding 0, JSON payload, `{"BC":{ttl,lens,loop_hz,item_id}}` extra headers, record span = TTL per A.6) on an `L_O_G`-style channel for v4 clients;
   - **(c)** optionally the raw canticle JSON as `…/JSON` DataLink packets for browser consoles via `/datalink`.

   The existing prototype's private DataLink publisher seam (`binary-canticle/prototype/ringserver-udp-cue/`, other reader's `dlproof/proof.py`) is the start of (c).
3. **Carrier wave as a miniSEED channel** (answers "existing dashboards show a live heartbeat trace"):
   - SID `FDSN:<NET>_<STA>__L_E_C` (SEED `LEC`): L band ≈ 1 sps matches the 1 Hz beacon (`stations-and-streams-v0.2.md:17`); source E = test-point/health (`fdsn-sid/channel-codes.rst:291-308`).
   - The sample value must **vary**, because ews de-means per record (`WaveformService.ts:136-137`). Good candidates: live-item count, sum of remaining TTL seconds, `head_seq` delta per second, or a phase ramp.
   - Companion channels: `LEQ` (queue/ring depth), `LE1..3` (per-lens intensity for MAGI panels).
   - Flush short records (5-10 samples) for liveness.
   - Carrier-drop = no records. SeedLink has no heartbeat of its own beyond `INFO ID` keep-alive (`protocol.rst:301`).
4. **Naming map.**
   - v4/ms3 SIDs can carry longer codes.
   - v3/ms2 (ews) needs NET ≤ 2, STA ≤ 5, LOC ≤ 2, CHA 3. Keep a static table `canticle station_id (ULID) → NET.STA`, e.g. `XX.SILAS`, `XX.CAEL`, published in StationXML.
   - Streams (`cael:thoughts`, lens names) map to **location codes** (`T0` threat, `H0` healing) or to channel subsource digits.
   - `XX` is test-only and "should never be distributed" (`network-codes.rst:71-73`). For anything shared beyond the cohort, request an FDSN temporary network code or accept the private-namespace status explicitly.
5. **Sequence alignment.**
   - ringserver has one global ID space (`slclient.c:18-27`), so SeedLink seq ≠ canticle per-station `head_seq` unless there is **one ringserver per station**.
   - Otherwise, carry canticle `head_seq` in ms3 extra headers and let the ring assign IDs.
   - DataLink 1.1 external packet IDs (`ringserver.md:356-362`) allow multi-ringserver LB with shared IDs if the relay tier is replicated.
6. **Fix ews to consume it** (B.3):
   - point `realtime/+page.svelte` at `wss://<ring>/seedlink` using the existing `src/lib/seedlink-client.ts`, or seisplotjs `seedlink`/`seedlink4`;
   - add a `DATA_SOURCES` entry with `baseUrl` serving static StationXML;
   - clear the buffer on channel switch;
   - add a v4 + `mseed3` path so text/`LOG` channels render in a log pane rather than the waveform.

### R2. DNS SRV naming proposal

This extends `binary-canticle/proto/protocol-spec-v0.1.md:252-274`, which already has `_canticle._udp.<zone>` and `_canticle-listen._udp.<zone>`.

```
; live, lossy tier (existing canticle names)
_canticle._udp.<zone>.         SRV 10 100 9999  station-a.<zone>.
_canticle-listen._udp.<zone>.  SRV 10 100 9998  relay-1.<zone>.     ; unicast fan-out registration/ingest (WAN listeners)
; replay tier (ringserver)
_seedlink._tcp.<zone>.         SRV 10 100 18000 ring-1.<zone>.      ; SeedLink v3+v4 plain
_seedlink._tcp.<zone>.         SRV 20 100 18500 ring-1.<zone>.      ; TLS (TXT tls=1) — or a separate _seedlinks._tcp
_datalink._tcp.<zone>.         SRV 10 100 16000 ring-1.<zone>.      ; write tier, WriteIP/auth-restricted
ring-1.<zone>. TXT "v=1" "sl=4.0,3.1" "fmt=2D,3D,J" "ws=wss://ring-1.<zone>/seedlink"
                   "dl=wss://ring-1.<zone>/datalink" "stationxml=https://ring-1.<zone>/fdsnws/station/1/query"
                   "net=XX" "carrier=LEC"
```

- Browsers do not resolve SRV, so the WS URLs must travel in TXT or in static config. That is exactly how ews already works (`PUBLIC_WEBSOCKET_URL`).
- **[ASSESS]** I found no existing `_seedlink._tcp` convention (web search, no hits). I could not check the IANA service-name registry (egress blocked). Before using `_seedlink`/`_datalink`/`_canticle` beyond `.local`/private zones, check IANA registration (RFC 6335). DNS-SD (RFC 6763) on `.local` is fine as is.

### R3. What not to do

- Do not ship `bagusindrayana/seedlink-websocket` as the bridge. It has no framing, hard-codes port 18000 and opens a TCP connection to **any host a browser names** (`server.js:24-61,89`). That is an open TCP relay, i.e. SSRF.
- Do not put canticle JSON on SeedLink v3 expecting ews to cope. ringserver sends ms3 to v3 clients unconverted and ews breaks (B.5).
- Do not treat ringserver eviction as TTL. Ring eviction is size-based. Use the end time = expiry convention (A.6) or client-side filtering on DataLink `hpdataend`.

---

## OPEN RISKS / CONTRADICTIONS

1. **Owner intent vs protocol.** The "SeedLink over UDP" wording contradicts both SeedLink specs (TCP only: `protocol.rst:12`; SeisComP `seedlink.rst:3`). The canticle docs already say the same (`spike/silas-seedlink-mapping.md:30-38`). The two-tier resolution (A.5) is my assessment and has not been decided anywhere.
2. **Exact cause of "found 6" is not pinned.** Two byte-exact reproductions exist: 526-B coalesced TCP chunk; 14-B `ERROR\r\nERROR\r\n`. The GEOFON HELLO/reply chunking was not observed (raw TCP egress blocked). The next log line from `+page.svelte:627` would settle it.
3. **Sample-rate semantics mismatch.** TTL items are discrete. SeedLink/miniSEED are time series. The A.6 span-equals-TTL trick and the `I` (irregular) band are workable but unconventional. Waveform dashboards need numeric channels, not items.
4. **Network code.** `XX` is test-only by FDSN rule. A real temporary code needs an FDSN request.
5. **nerv-ui is React.** ews is Svelte and OpenClaw's UI is Lit. Picking one console stack is an open decision.
6. **ews production config points at a third-party Railway proxy** (`wrangler.toml` `PUBLIC_WEBSOCKET_URL`), and `/api/fdsn/*` is an open fetch proxy. Both need attention before any canticle deployment reuses ews.
7. **Earthworm and Raspberry Shake facts** come from search snippets, not fetched pages (egress blocked). rsudp code was read directly.

## Scratch artifacts and cleanup

- The repro scripts stay in `scratchpad/sdash/`. The local ringserver (ports 18000/16000) and proxy (8090) were stopped after the runs, and the 1 GiB ring directory `sdash/ring/` was deleted. No repository working tree was modified.
