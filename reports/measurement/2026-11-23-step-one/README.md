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

<!-- RESULTS -->

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
