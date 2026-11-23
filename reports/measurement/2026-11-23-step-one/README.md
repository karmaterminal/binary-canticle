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

<!-- RESULTS -->

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
