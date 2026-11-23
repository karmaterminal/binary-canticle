# Step one is measurement: the built canticle path, and the flood acceptance test

**Status:** measurement report for [#168](https://github.com/karmaterminal/binary-canticle/issues/168),
design `docs/design/sense-organ.md` §2.8 (branch `gloss/sense-organ-doc` at `5acceec3`). No design or
component code was changed. Every instance measured here was a throwaway built from source in a scratch
directory, on loopback only; the live daemon, the live `frond-ear.service`, the live stations and the room
were never touched. Raw files are under [`results/`](results/), and the harness is under [`harness/`](harness/).

<!-- HEADLINE -->

## What was measured, and at which SHAs

| Ref | Value | Notes |
|---|---|---|
| product/base | binary-canticle `origin/main` `08c11127d4e11ed00f307a7006d85581c8674a28` | station, host daemon, codec. The live clone runs `ba980e32`, an ancestor; `wire.py`, `cbor.py`, `ids.py`, `manifest.py`, `listener.py`, `records.py`, `daemon.py`, `station.py` and `runner.py` are byte-identical between the two |
| frond-ear | `origin/main` `7c9bbd3179c50e6ad6870dcb0c74f68d47b4229d` | `src/` and `pnpm-lock.yaml` are identical to the installed `43dab0e5`. Read-only clone; `node_modules` is the same-host install at the same lock |
| lane branch | `codeagent/canticle-step-one-measurement-2` | this report |
| CI | this repository's own `tests.yml` | nothing here is tested by it; the report adds no product code |
| presentation | N/A | not merged by this lane |
| design/proof | `gloss/sense-organ-doc` `5acceec3a6527bbd3bb918cb7e945fc2d904abf1` | §2 read whole; §2.8 is the brief |

Runtimes: Python 3.12.3 with `cryptography` 50.0.1 from `.github/ci/requirements-station.txt` (the live
venv runs 3.12.3 with 50.0.2; there is no Python 3.11 on ronan). The frond-ear daemon ran on the live
unit's node (v26.12.1), and its shim on the live session's node (v26.9.0).

## The machine: ronan, aarch64. These numbers do not carry to silas (x86_64)

| | |
|---|---|
| host / arch | **ronan, aarch64**, kernel `7.0.0-1019-nvidia` |
| CPU | 20 cores, no SMT, **two core types**: 10 × Cortex-X925 up to 3.9 GHz (cpus 5-9, 15-19) and 10 × Cortex-A725 up to 2.8 GHz (cpus 0-4, 10-14). Path processes were not pinned, so the scheduler put them on either type; the isolated microbenchmarks were pinned to one core of each type and are reported per type |
| RAM | 122 GiB |
| disk | ext4 on NVMe (`nvme0n1`, scheduler `none`). Scratch state lived on this same filesystem as the live daemon's `~/.local/state/canticle/daemon`, so a fsync costs what it costs the seat |
| loopback | `lo`, MTU 65 536. `net.core.rmem_default` 212 992 B (the daemon sets no `SO_RCVBUF`), `rmem_max` 4 MiB |
| niceness | every process of this lane ran under `nice -n 19 ionice -c3`, in this session's cgroup (`app.slice/scribe-rez.service`), never in `openclaw-gateway.service`. With the NVMe scheduler at `none`, the kernel does not arbitrate I/O by ionice class, so `-c3` is recorded but had no effect |
| neighbours | 🌊's live gateway and an unrelated uid's CI-like node jobs shared the host. The 1-minute load average is in every sampler row (`samples.csv`, column `loadavg1`) and in each table below; it stayed under `nproc` (20) except where a table says otherwise |

**Do not extrapolate.** The two costs that set every ceiling below are an Ed25519 verify (CPU) and a
durable save (disk). Both differ between ronan's two core types, and both will differ on silas.

## The path, as the live seats configure it (multicast off, unicast)

The live configuration was read for its transport shape only (no keys, no payloads, no key ids):

- host daemon: `canticle daemon --stations ~/.binary-canticle/stations.toml --bind <LAN addr>:9999 --no-multicast --socket $XDG_RUNTIME_DIR/canticle/daemon.sock`; `stations.toml` `[listen] bind = "<LAN addr>:9999"`, `multicast = false`;
- stations: `canticle station … --stream chatter [--stream facts:live-state:900 --stream display:live-state:900] --to <peer>:9999` × 4, unicast, default `--beacon-ms 1000` and budgets (B_station 16 kbit/s, b_stream 4 kbit/s);
- frond-ear: `canticle.source: "host-daemon"`, `hostSocket` unset (so the daemon's default socket), one ear, 5 tune patterns, 2 wake keys, `delivery: {mode: "off", stations: {<3 stations>: "immediate"}}`, every other delivery setting at its default (`debounceMs` 5 000, `maxAgeMs` 30 000, `windowMs` 60 000, `maxItems` 5, `bufferPerStream` 32, `maxPushesPerHour` 60), `limits.maxNotificationChars` 6 000;
- at the time of reading, the live daemon held 23.9 MiB resident (peak 31.6 MiB) and an 875-byte state file, and the live frond-ear 61 MiB (peak 111 MiB).

The lab reproduces that shape on loopback: `canticle daemon --manifest <lab>/fleet.json --bind 127.0.0.1:<port> --no-multicast --socket <lab>/run/canticle/daemon.sock --state-dir <lab>/state/canticle-daemon --health-interval 1`;
real `canticle station … --to 127.0.0.1:<port>` processes; frond-ear `src/cli.ts daemon` with
`source: "host-daemon"`, `hostSocket` set explicitly to the lab socket, and the live delivery shape.
Differences from the seat: loopback instead of the LAN NIC, one `--to` destination instead of four, a
1 s health interval instead of 10 s (so health is visible per second), and a dead loopback port standing
in for Discord (`DISCORD_GATEWAY_URL`, `DISCORD_API_BASE`; the gateway retries on its backoff and never
connects; canticle delivery doesn't depend on it).

```
producer ──UDP──▶ kernel socket buffer ──▶ canticle daemon ──record v1 / unix socket──▶ frond-ear daemon ──ear protocol──▶ shim ──stdio MCP──▶ session
 (station or       (212 992 B; drops       (verify, dedup,                              (RecordConsumer:            (delivery:                (notifications/
  blast.py)         counted only in         write-ahead save,                            live set ≤ 4 096,          tune, wakeKeys,            claude/channel)
                    /proc/net/udp)          fan-out ≤ 16 peers,                          rec_seq gaps)              debounce, caps)
                                            1 024 records each)
```

## 1. The flood acceptance test

> *An unrelated producer floods the tower; memory and model admission stay bounded; the quiet tuned stream
> keeps arriving; loss, lag and gaps are reported honestly. A saturated link with an overwhelmed prince is
> a failed radio.* (design §2.8)

**Setup, every cell.** A fresh lab. One ear (the live seat has one): a frond-ear daemon with the live
delivery shape, `tune: ["quiet:quiet"]`, `wakeKeys: [<quiet key>]`, `delivery: {mode: "off", stations:
{quiet: "immediate"}}`, defaults otherwise, and a fake session on frond-ear's real shim. The **quiet tuned
stream** is a real `canticle station` (`--stream quiet:chatter`, unicast to the daemon) driven through its
control socket with one 64-byte item every 10 s ([`singer.py`](harness/singer.py) `--interval 10`); the
station sends each item at once, then a 3-copy burst at +1, +2 and +4 s, then loops it until its 60 s TTL
runs out. The **flood** is untuned (not in the tune, not on `wakeKeys`) and comes from a key the manifest
licenses unless the cell says otherwise. The flood producers and the quiet singer run for the cell's
duration, then the lab keeps listening for the drain (8 s for F0 and F1, 60 s or more for later cells),
so items the carousel recovers after the flood stops are seen. Command:
`nice -n 19 ionice -c3 python run_cells.py ../results/flood @../results/flood/cells-rest.json` (F0 and F1
from `cells.json`, F1b to F9 from `../results/flood2/cells.json`); every cell's parameters are in its
`result.json`.

<!-- FLOOD-TABLES -->

**PASS criteria, one by one:**

| criterion | verdict | evidence |
|---|---|---|
| the quiet tuned stream keeps arriving | **FAIL** | Whenever the flood exceeded the daemon's capacity by more than an order of magnitude, the quiet stream all but stopped while it ran. Valid-key flood: 0 of 60 arrived while it ran (F1; 3 arrived in the 8 s after it stopped, too late to be pushed before the cell ended), 1 of 18 (F1b). Real station flooded through its own control socket: 1 of 30 (F5); the quiet stream on that same station: 2 of 30, neither pushed (F6). One captured frame replayed: 1 of 30 (F4). Forged signatures: 5 of 30 (F2b). Unknown key at 1 M datagrams/s: 23 of 30 arrived, 19 pushed (F3b). A flood the daemon could keep up with still cost quiet items at the ear once it filled frond-ear's live set: 5 of the 20 sung after that point (F9, Finding 4). The stream survived only where the daemon kept up and the live set had room: unknown key at 73 k/s (F3, 30 of 30, within 71 ms), or a valid flood at 100/s (F7) and 40/s (F8), where every quiet item arrived but up to 8 s late |
| memory stays bounded | **PASS**, for these durations | No process grew without bound in any cell: daemon at most 53 MiB, frond-ear at most 112 MiB, shim at most 108 MiB (tables above; traces below). The daemon grows with its dedup set (32 → 53 MiB in F9 at about 4 500 entries), which its per-key quota (100 000 / keys in the manifest) caps; no cell drove it there. frond-ear rose 100 → 106 MiB over F1's 10 minutes and 103 → 112 MiB in F9 while its live set filled to its 4 096-record bound; nothing here says where it levels off past that |
| model admission stays bounded | **PASS** | The untuned flood never reached the session in any cell: it isn't tuned and isn't on `wakeKeys`. The session got at most one push per quiet item, at most 3 records a push |
| the push rate stays under the cap | **PASS** in every flood cell, but see §4 | The most pushes in any flood cell was 30 in 300 s (F3), under `maxPushesPerHour` 60. The quiet stream alone (360 items an hour) is six times that cap, so on the live settings it reaches the cap after about 10 minutes without any flood (§4, cell A4) |
| loss, lag and gaps for the flood are reported, not silent | **FAIL** | In every cell the daemon's health said `ok` with no reasons, and frond-ear's receive health said `ok`. Kernel drops (13.9 M to 323 M per cell) appear in no record, status or push. A forged or unknown-key flood is visible in the daemon's counters (`bad_signature`, `unknown_key`, and the D34 key-id table naming the impersonated key ids), but nothing reports what it cost. A valid-key flood looks like ordinary traffic. For what did arrive, lag is honest per record (`age=33s` in the push), but a hole in the quiet stream shows only as a jump in item numbers (`item=…/3`, then `…/17`), and records promised to "the next push" can expire with no push to say so (Finding 3) |

**Verdict: FAIL.** The prince was not overwhelmed (admission stayed bounded), but the quiet tuned stream
stopped arriving under any flood the daemon couldn't keep up with, and nothing said so.

## 2. Verify cost, per item (and why it isn't the ceiling)

Method: [`harness/verify_bench.py`](harness/verify_bench.py), one process pinned with `sched_setaffinity`
to cpu 19 (Cortex-X925) and then cpu 14 (Cortex-A725), 3 000 frames per step, `perf_counter_ns` around
each call; frames are chatter ITEMs signed by a throwaway key, bodies of 64 B, 512 B and the largest that
fits the frame. Raw: [`results/verify/verify.json`](results/verify/verify.json). Command:
`nice -n 19 ionice -c3 python verify_bench.py ../results/verify/verify.json`.

**Batches: not measurable yet.** Frame v2 carries one Ed25519 signature per datagram and the daemon
verifies one per datagram; batch roots and membership proofs are unbuilt (design §2.8).

**On payload size.** The workorder's "1 200 B" is the datagram cap (`MAX_DATAGRAM`). A frame may be at
most 1 100 B (`MAX_FRAME`, RFC §9), so the largest payload is a body of about 975 B in a 1 098 B frame.
That is what "max" means everywhere in this report.

| step (ronan, aarch64) | frame | X925 mean µs (p99) | X925 per core /s | A725 mean µs (p99) | A725 per core /s |
|---|---|---|---|---|---|
| sign (what the station pays, for scale) | 186 B | 23.1 (25.6) | 43 206 | 52.0 (57.3) | 19 250 |
| sign | 1 098 B | 24.8 (26.7) | 40 400 | 54.8 (64.5) | 18 264 |
| Ed25519 verify alone | 186 B | 40.5 (42.8) | 24 722 | 101.4 (105.5) | 9 866 |
| Ed25519 verify alone | 635 B | 40.8 (43.0) | 24 518 | 101.8 (105.8) | 9 819 |
| Ed25519 verify alone | 1 098 B | 41.1 (43.2) | 24 344 | 102.3 (106.1) | 9 775 |
| CBOR decode + re-encode (the determinism check) | 1 098 B | 12.2 (14.0) | 82 302 | 23.6 (26.8) | 42 417 |
| whole admission parse, `wire.parse` | 186 B | 57.6 (60.0) | 17 367 | 136.0 (144.6) | 7 354 |
| whole admission parse, `wire.parse` | 1 098 B | 58.9 (61.2) | 16 993 | 138.4 (148.3) | 7 226 |
| `Listener.hear`, new item, no state file | 186 B | 65.2 (81.1) | 15 330 | 155.0 (189.3) | 6 453 |
| `Listener.hear`, duplicate (a carousel repeat) | 186 B | 61.7 (64.7) | 16 196 | 146.1 (160.0) | 6 843 |

Verify is flat in payload size: SHA-512 over 1 KB costs nothing next to the curve arithmetic. An A725
core is 2.3–2.5 × slower than an X925 core at every step.

**What a new item actually costs the daemon.** The daemon's `Receptor.hear` is write-ahead (RFC §14.18.2;
`records.py` `Receptor._batch`): before it emits a new item's record, it saves the whole safety state,
which is a JSON document of every live dedup entry and every surfaced tuple, written to a temporary file,
fsynced, renamed and the directory fsynced. The same call with its state on the lab disk, then on
`/dev/shm` (where fsync is free), as the dedup set grows:

| live dedup entries before | state file after | X925, ext4/NVMe: ms per new item mean (p99) | X925, tmpfs | A725, ext4/NVMe | A725, tmpfs |
|---|---|---|---|---|---|
| 0 | 56 KB | 8.2 (26.2) | 0.6 | 8.1 (12.3) | 1.2 |
| 1 000 | 280 KB | 12.5 (20.9) | 4.3 | 16.2 (22.4) | 9.1 |
| 2 000 | 506 KB | 16.1 (20.4) | 8.2 | 26.9 (88.2) | 17.2 |
| 3 000 | 732 KB | 20.7 (27.8) | 12.2 | 40.6 (100.8) | 24.8 |
| 3 500 | 845 KB | 22.7 (30.5) | 14.2 | 44.5 (57.8) | 29.6 |

A durable save of a tiny file alone (`atomic_write_json`, two fsyncs) took 7.4 ms mean, 13.8 ms p99,
500 samples. So a new item costs about **7 ms of fsync plus about 4 µs per live dedup entry on an X925
core (8 µs on an A725)**, about 226 B of state per entry, while a duplicate costs only its verify
(62.6 µs X925, 150.9 µs A725, no save). Verify is under 1 % of a new item's cost.

A dedup entry lives for the item's local expiry plus 5 s, so at a steady rate *r* of new chatter items
(TTL 60 s) the daemon holds about 65·*r* entries, and the ceiling is where *r* × cost(65·*r*) = 1 s. On an
X925 core that is about 50 items/s, on an A725 core about 35/s, for every stream and every payload size.
For live-state items at the 900 s TTL the live `facts` and `display` streams use, the same arithmetic
gives about 16/s on an X925 core. At the per-key quota of 100 000 entries (one key in the manifest), a
save would be about 22 MB of JSON and over 400 ms. These are predictions from the isolated costs; the
in-path numbers below are what the built path did.

## 3. Ingest and fan-out through the daemon

**Method.** 5 stream counts (1, 10, 100, 1 000, 10 000 logical streams, round-robin, all on one producer
key so that only the stream count changes) × 3 payloads (64 B, 512 B, max) × 1 and 4 ears (each ear a
frond-ear daemon with a fake session; the probe tap is one more binding, so 2 or 5 connections on the
daemon socket). Each combination ran twice, each time in a fresh lab: **saturated** (one producer flat
out, 20 s) for the ceiling, and **40 items/s** (30 s, below the ceiling on fresh state) for latency.
Each ear tuned the producer's first stream, with the producer on `wakeKeys` and `immediate` delivery,
so pushes happened on the live settings. Then three cells tuned every stream (100, 1 000 and 10  000
patterns) to show what a large tune costs frond-ear. Latency is CLOCK_MONOTONIC from the producer's
`sendto` to the probe's receipt of the item's `frame` record (send→record), and to the fake session's
read of the push carrying it (send→push). CPU% is of one core; RSS is the maximum over the cell. Raw:
[`results/ingest/`](results/ingest/); command:
`nice -n 19 ionice -c3 python run_cells.py ../results/ingest @../results/ingest/cells.json`.

<!-- INGEST-TABLES -->

## 4. Admission bound: what reaches the session under load, on the live settings

**Method.** frond-ear's real settings as the live seat runs them: `immediate` per station, `debounceMs`
5 000, `maxAgeMs` 30 000, `maxItems` 5, `bufferPerStream` 32, `maxPushesPerHour` 60,
`maxNotificationChars` 6 000. A producer on `wakeKeys` sings into one tuned stream: A1 at 30 items/s for
7 minutes (under the daemon's ceiling, so every item reaches the ear), A2 the same with `digest` (the
other mode the config allows, `windowMs` 60 000), A3 flat out for 5 minutes (the daemon saturated). A4
is the §2.8 quiet stream alone, one item every 10 s for 12 minutes, with no flood. Pushes and their
records are counted as the fake session read them. Raw: [`results/admission/`](results/admission/);
command: `nice -n 19 ionice -c3 python run_cells.py ../results/admission @../results/admission/cells.json`.

<!-- ADMISSION-TABLE -->

## 5. Reconnect storm

**Method.** [`harness/scenario_reconnect.py`](harness/scenario_reconnect.py). Under load (a producer at
30 items/s on one tuned, allowlisted stream with `immediate` delivery, plus the quiet station), four ears
and the probe, so every daemon restart is five bindings reconnecting at once, each asking for a join
snapshot. Restarts, in seconds after the load starts: SIGKILL the daemon at 30 and restart it at 33
(same state directory); SIGTERM it at 70 (it sends `bye`) and restart at 72; SIGKILL frond-ear `ear0` at
110 and restart it at 113 (same database; its shim reconnects by itself); a storm of five daemon SIGKILLs
4 s apart from 150, each restarted 1 s later; at 200, SIGKILL the daemon and all four frond-ears at once,
all restarted at 203; the load ends at 260. frond-ear's status was read every second. Raw:
[`results/reconnect/`](results/reconnect/), with the per-restart analysis from
[`harness/reconnect_report.py`](harness/reconnect_report.py) in `reconnect-analysis.json`.

<!-- RECONNECT-TABLE -->

## Findings, with reproductions

These are written up, not fixed (workorder rule: measurement only). Each reproduction runs in a fresh
throwaway lab from `harness/`, niced, and touches nothing live.

### Finding 1: silent loss at the first hop (TROUBLE posted)

**What happens.** The daemon reads datagrams one at a time on one event loop. A new valid item costs
8–25 ms (§2: two fsyncs plus a JSON rewrite of every live dedup entry), so on ronan it sustains about 40
new items/s, falling as its dedup set grows. Anything faster fills the socket's receive buffer (212 992 B,
the kernel default; the daemon sets no `SO_RCVBUF`), and the kernel drops what doesn't fit, quiet stream
and flood alike. Those drops are counted only in `/proc/net/udp` and `RcvbufErrors`. The daemon's health
stayed `ok` with no reasons in every flood cell, frond-ear's receive health stayed `ok`, record v1's `gap`
is `"unavailable"`, and no push mentions it. In F1 that was 92 020 097 datagrams over 10 minutes.

**Reproduction** (about 4 minutes):

```sh
cd reports/measurement/2026-11-23-step-one/harness
nice -n 19 ionice -c3 ~/.venvs/canticle-measure-2/bin/python run_cells.py /tmp/repro-1 \
  '[{"name":"repro-1","prod_keys":2,"mode":"valid","rate":0,"payload":"64","prod_wake":false,"ear_tune":"none","quiet_interval":10,"duration":120,"drain":60,"sample_every":1000}]'
```

Expected on ronan: `kernel_drops` in the millions, quiet items reaching the daemon during the flood in
single digits or zero, daemon `health.state` `ok`, frond-ear `receiveHealth` `ok`.

### Finding 2: one captured frame, replayed, is enough (no key needed)

A valid frame resent unchanged is a duplicate: the daemon still verifies it before dedup finds the
repeat, at about 70 µs each in the path (F4: 13 941 duplicates/s at a mean of 80 % of a core). Replaying
one frame from two processes (1.09 M datagrams/s) dropped 98.7 % of everything at the kernel, and 1 of 30
quiet items arrived while it ran. A frame stays replayable until it expires (60 s for chatter), and live
traffic supplies fresh ones. The pilot-host kit's nft table (`docs/pilot-host/canticle-pilot.nft`) admits
only listed peer addresses and has no per-source rate meter; whether a seat runs it was not checked (that
needs root, and it's the host owner's). Reproduction: as Finding 1 with `"mode":"dup"`.

### Finding 3: "N more records wait for the next push", and then nothing

When the carousel recovered quiet items after a flood, frond-ear pushed the fresh ones and routed the ones
older than `maxAgeMs` (30 s) to the next digest report, which is due a `windowMs` (60 s) later. With 10–30 s
of life left they expired first. The push that went out said `(3 more records wait for the next push.)`;
no later push came, so the session was never told they went off air. Only `ear_status`
(`off_air_unpushed: 3`) knows. Seen in F1b, F4, F5 and F6. Reproduction: as Finding 1; read the last
push in `session0.pushes.jsonl` and `frond_ear.ear0.canticleDelivery.counts` in `result.json`.

### Finding 4: untuned streams can starve the ear's live set (TROUBLE posted)

frond-ear's record v1 consumer keeps one live set for every `station:stream` the daemon emits, tuned or
not, bounded at 4 096 records (`src/canticle/records.ts` `MAX_LIVE`; the tune is applied later, when an
ear's view is read). When it is full and nothing in it has expired, a new record is refused and counted
`live_overflow`. The daemon emits one `frame` record per item (repeats are a `no_op`), so a refused item
is never offered to the ear again, even though its station keeps looping it.

F9: an untuned producer at **15 chatter items/s with a 300 s TTL** (chatter's class maximum), well inside
the daemon's capacity (0 kernel drops, every item verified), filled the set after about 273 s. From then
on 5 of the 20 quiet tuned items sung (n = 28, 29, 34, 40, 46) reached the daemon within 60 ms and were
never pushed. frond-ear's `receiveHealth` stayed `ok` with no reasons; only `counts.live_overflow` (414)
in its status shows it, and nothing reaches the session. Reproduction (9 minutes):

```sh
nice -n 19 ionice -c3 ~/.venvs/canticle-measure-2/bin/python run_cells.py /tmp/repro-4 \
  '[{"name":"repro-4","producers":1,"mode":"valid","rate":15,"ttl":300,"payload":"64","prod_wake":false,"ear_tune":"none","quiet_interval":10,"duration":480}]'
```

## What the numbers say to §2's owners (observations, not proposals)

For 🍃 and 🌿 (§2) and 🌫, to weigh. Nothing here was changed.

- **§2.4 step 2 ("bound the receiver first … before any token budget") is the step that failed.** The
  built daemon has no per-source byte, queue or work cap; it serves datagrams in arrival order until the
  kernel buffer overflows, so whoever sends most decides what everyone hears. The most expensive thing a
  sender can hand this receiver is a *new valid item* (8–25 ms of durable save), not a forged one (60–70 µs
  in the path, F2b and F4). So the cheapest blackout comes from a licensed key, or a station gone wrong: <!-- BRACKET -->;
  without a key, replaying one captured frame does it at about 1 M datagrams/s (F4).
- **The write-ahead save sets the host's new-item ceiling.** Rewriting the whole state with two fsyncs per
  item caps ronan at about 40 new items/s, and lower as the dedup set grows (≈16/s predicted for 900 s
  live-state items). Any ring or carriage that wants more items per second through this daemon meets this
  first.
- **§2.4 step 6 ("gaps are reported, never silently skipped") has a source available**: the kernel counts
  every datagram it drops for the socket (`SO_RXQ_OVFL`, `/proc/net/udp`), and today nothing reads it. The
  per-stream sequence hole is computed only in `style: counts` digests.
- **The ear's bound is shared across tuned and untuned streams** (Finding 4). §2.4 step 1 ("untuned streams
  never reach the ear where avoidable") isn't the case on the built path: the daemon has no tune, so every
  verified item becomes a record every binding parses and holds.
- **The push cap and the quiet stream.** The live delivery settings allow 60 pushes an hour; a stream of
  one item every 10 s is 360 items an hour (§4, cell A4).

## Not measurable yet

| §2.8 quantity | Why not, on the built path |
|---|---|
| ringserver ingest and fan-out | no ring adapter is built: neither the station, the daemon nor frond-ear speaks DataLink (`prototype/ringserver-proofs/` is evidence about ringserver itself, not a path). Every number here is the UDP + daemon baseline the design asks for before a ring is compared |
| verify cost per batch | frame v2 has one signature per datagram and no batch root or membership proof (design §2.8 lists batch signatures as unbuilt) |
| the shared ear core, the guide, the publisher spool, `find`/`tune`/`peek`/`now` | unbuilt (design §2.8) |
| the OpenClaw ear (`prototype/openclaw-canticle/`) | no seat runs it, and its continuing-reader drain is unproved (design §3); only frond-ear was measured |
| per-source caps before verification (§2.4 step 2) | not implemented in the daemon: it reads every datagram the kernel hands it, in arrival order, with no per-key byte, queue or work budget. What happens without them is measured in §1 |
| the receiver's own record of kernel loss | the daemon doesn't read `SO_RXQ_OVFL` or `/proc/net/udp`, so no layer can report it (see below); this harness read it from outside |
| multicast | off on the live seats and off here (🍃's third condition); not measured |
| reception on a LAN NIC | loopback only (workorder rule); a NIC adds interrupt and softirq cost this report doesn't see |

## What each layer can report about loss, and what it can't

| Layer | Counter or signal | Where it shows | Sees kernel socket drops? |
|---|---|---|---|
| kernel | per-socket `drops` and `rx_queue` (`/proc/net/udp`); host-wide `RcvbufErrors` (`/proc/net/snmp`) | nowhere in canticle; only this harness reads it | it is them |
| host daemon | `health.counters.admission` (verified, duplicate, over_quota, …) and `.unverified` (unknown_key, bad_signature, expired, …), the D34 key-id table, `records.dropped` and `peers_closed` (a slow binding's queue), reasons `no_datagrams`, `records_lost`, `clock_skew` | `health` records every 10 s (1 s here) | **no**: it only counts what `recvfrom` returned. Record v1's per-item `gap` is `"unavailable"` (RFC §14.18.3 table: not until beacons carry `trail_seq`) |
| record v1 binding (frond-ear `RecordConsumer`, this harness's probe) | `rec_seq` gaps → `records_lost` (and the live set cleared), `exit_without_bye`, `joined_late`, join-snapshot `truncated`/`omitted`, `live_overflow`, `malformed_record` | frond-ear `status` → `canticle.receiveHealth`, `reasons`, `counts`; `ear_status` | no |
| frond-ear delivery | per-ear `counts`: `dropped` (per-stream buffer full), `off_air_unpushed`, `routed_late`, `not_allowlisted`, `muted`, `push_budget` (as `held`) | `ear_status` → `canticleDelivery`; and **in the push itself**: footer lines such as `prod:s00000: 380 dropped from a full buffer.` and `(27 more records wait for the next push.)`, and a `late` line on a record past `maxAgeMs` | no |
| the session | what the push says | the channel event | no |

## Harness

| File | What it does |
|---|---|
| [`harness/mlib.py`](harness/mlib.py) | The lab: a scratch directory under `~/.cache/canticle-measure-2/`, throwaway Ed25519 keys and an unsigned manifest, the daemon, real stations and frond-ear daemons started with scrubbed environments, a guard that refuses any live path, a 0.5 s CPU/RSS sampler, and the kernel's per-socket drop counter |
| [`harness/blast.py`](harness/blast.py) | A producer that ignores the station regulator: frame v2 ITEMs built with `canticle.wire.encode_item` (valid, a replayed duplicate, a forged signature, or an unknown key), at a set rate or flat out, logging send times |
| [`harness/singer.py`](harness/singer.py) | Drives a real `canticle station` through its control socket: the quiet stream (one item every 10 s), or a station flood (sing as fast as the socket answers) |
| [`harness/tap.py`](harness/tap.py) | The measurement's own record v1 binding on the daemon socket (join snapshot, `rec_seq` gaps, arrival times, health) |
| [`harness/fake_session.py`](harness/fake_session.py) | Stands in for the Claude session: runs frond-ear's real shim and speaks stdio MCP to it; logs every `notifications/claude/channel` push |
| [`harness/cells.py`](harness/cells.py), [`harness/run_cells.py`](harness/run_cells.py) | One measurement cell = one fresh lab; scenario lists are `results/<scenario>/cells.json` |
| [`harness/verify_bench.py`](harness/verify_bench.py) | Isolated verify and admission costs, pinned per core type |
| [`harness/scenario_reconnect.py`](harness/scenario_reconnect.py) | The restart storm |
| [`harness/summarize.py`](harness/summarize.py), [`harness/plot_svg.py`](harness/plot_svg.py) | The tables and charts in this README, from the result files |
| [`harness/queue.sh`](harness/queue.sh), [`harness/smoke.py`](harness/smoke.py) | The run order used; a 40-second end-to-end check |

To rerun (from `reports/measurement/2026-11-23-step-one/`, with frond-ear cloned beside the worktree as
`frond-ear-step-one-measurement-2-ro`, or `MEASURE_FROND_EAR` set):

```sh
python3 -m venv ~/.venvs/canticle-measure-2
~/.venvs/canticle-measure-2/bin/pip install --require-hashes --only-binary=:all: --no-deps -r ../../../.github/ci/requirements-station.txt
cd harness
nice -n 19 ionice -c3 ~/.venvs/canticle-measure-2/bin/python verify_bench.py ../results/verify/verify.json
nice -n 19 ionice -c3 ~/.venvs/canticle-measure-2/bin/python run_cells.py ../results/flood @../results/flood/cells.json
nice -n 19 ionice -c3 ~/.venvs/canticle-measure-2/bin/python run_cells.py ../results/ingest @../results/ingest/cells.json
nice -n 19 ionice -c3 ~/.venvs/canticle-measure-2/bin/python run_cells.py ../results/admission @../results/admission/cells.json
nice -n 19 ionice -c3 ~/.venvs/canticle-measure-2/bin/python scenario_reconnect.py ../results/reconnect
python summarize.py ../results
```

A rerun is a new measurement on whatever host runs it, not a reproduction of these numbers.
