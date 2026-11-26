# Method: 🌊's four quantities on the built path (fixed before the window)

This file was committed and pushed before the measurement window opened, so the method is fixed before any of
the window's numbers were read. [REPORT.md](REPORT.md) gives the results and points back here. The work is
bound to [frond-ear#116](https://github.com/karmaterminal/frond-ear/issues/116) and to RFC-0002 §7.1
(`rfc/0002-binary-canticle-sense-organ.md`).

## The question, as 🌊 framed it

🌊 Ronan, in the 2026-11-22 addendum to the #161 host design
([issuecomment-7087387526](https://github.com/karmaterminal/binary-canticle/issues/161#issuecomment-7087387526),
"high-concurrency radio requirement"):

> Separate four quantities in tests: global catalog cardinality, simultaneous wire traffic/bytes, per-seat tuned
> subscriptions, and the tiny bounded subset admitted to a model turn.

The workorder names them:

1. **Catalog size:** how many stations and streams exist and are advertised.
2. **Traffic on the wire:** datagrams and bytes per second, by kind, at the host daemon.
3. **Streams one seat tunes:** what a receiver actually subscribes to (the frond-ear seat; the OpenClaw prince's
   station listener).
4. **Items admitted to a turn:** of what is heard, how many reach a model turn, by delivery mode.

The workorder asks about three kinds: beacon, item and manifest. Frame v2 at the running SHA has three:
item `0x01`, beacon `0x02` and pluck `0x03` (`prototype/canticle-station/canticle/wire.py:22`). No manifest
travels on the wire, because the manifest is a local file. So each quantity is reported for item, pluck and
beacon, with unverified datagrams and kernel drops as further rows.

## Named refs

| Ref | Value | Local / tracking / server |
|---|---|---|
| product/base | binary-canticle `main` `2eb1a56d8fe4f1b250d4da3adec5611292f66948` | equal (checked at the lane's start) |
| code the host runs | binary-canticle clone `~/flesh_beast_best_beast/source/binary-canticle` at `ba980e32eaa203390a59b73806bdfaf04a14abb3` (HEAD since 2026-11-04; the daemon started 2026-11-21, the stations 2026-11-09 and 2026-11-14). `wire.py`, `cbor.py`, `records.py`, `daemon.py`, `listener.py` and `station.py` are byte-identical at `ba980e3` and `2eb1a56` | clean worktree |
| frond-ear | `main` `405e49183f76ed03066fe4d93bd4f75c2cdcc541`: the live clone's HEAD, merged at 2026-11-24 10:05:19 PST; `frond-ear.service` restarted after it, at 10:05:19.72 | equal |
| OpenClaw binding | the `openclaw-canticle` spike (#97) installed under `~/.openclaw/extensions/canticle` on 2026-10-24, loaded by `openclaw-gateway.service` (started 2026-11-17) | file digests in `results/catalog.json` |
| lane | `codeagent/radio-four-quantities`, published unchanged at `2eb1a56` before this commit | equal |
| CI/workflow | none. This repository's `tests.yml` does not run anything under `reports/`, and no product code changes | N/A |
| presentation | N/A | N/A |
| docs/proof | this directory on the lane branch | this commit |

## The host and the window

- **Host:** ronan, aarch64, kernel 7.0.0-1019-nvidia, 20 cores. The host daemon is
  `canticle daemon --stations ~/.binary-canticle/stations.toml --bind <LAN addr>:9999 --no-multicast`.
  Two stations run on this host. They sing to four peers and not to this daemon, so this daemon hears only
  other hosts' stations.
- **Window:** 45 minutes (2 700 s), starting at `t0`, which `harness/run.sh` writes to `results/window.json`
  (epoch ms, the host's clock). Every instrument runs at `nice -n 10`.
- **One window, one host.** These numbers describe this host today. They are not a fleet total, and they are
  not a ceiling.

## Rules for every instrument

- **Read-only.** Nothing sings, hushes, tunes, grants, mutes, restarts or reconfigures anything. The only writes
  go to `results/`.
- **No heard text, anywhere.** Every instrument keeps a closed list of fields: counts, sizes, ages and closed
  words (`harness/common.py`, `closed()`). No item text, purpose, state key, lens, lineage, digest, idem, key id,
  session id or address is written, and nothing heard is printed.
- **No station names.** The repository is public. RFC-0001 §18.9 and display grants (#137, on `main`) keep live
  station activity off human views without the station's consent. Stations and streams are therefore
  counted, never named. Where a file must tell them apart, it uses a hash salted once per process, and the
  salt is never written.
- **Observer effects, declared:**
  - `daemon_records.py` is one more binding on the daemon's socket. It takes one of 16 connections and
    adds one copy of each record to the fan-out. Its join-snapshot request adds one to the daemon's
    `snapshots.requested` and `served` counters. If it fell more than 1 024 records behind, the daemon would
    count `records.dropped`, and every binding would see health `records_lost`. The summary checks that
    `records.dropped` did not move.
  - `host_sampler.py` runs `frond-ear status` every 120 s, one CLI connection to the frond-ear daemon each
    time. It opens frond-ear's SQLite store read-only, as `frond-ear exposure` does.
- **Instrument checks before this commit.** The instruments were run twice against the live host (20 s and
  12 s), into a scratch directory outside the repository, to fix projection bugs and to check that their
  output held no names, key ids, addresses or text. Those outputs are not data and are not used here.
  Before the method was written, the lane also read the configurations, the manifest's counts, the
  daemon's cumulative counters and frond-ear's custody table (7 rows) to learn which surfaces exist. The
  window's numbers come only from the instruments below.

## Per quantity: source, command, formula

`Δ` is a counter's value at the last sample inside the window minus its value at the first. A rate is `Δ`
divided by the seconds between those two samples.

### 1. Catalog size

| What | Source | How |
|---|---|---|
| licensed stations and `station:stream` pairs | the manifest the daemon loaded (`~/.binary-canticle/fleet.json`). The daemon's `hello` carries its SHA-256, and `daemon_records.py` checks that it matches the file | `catalog.py`: count of stations, sum of their streams, classes and scopes |
| stations on air | the daemon's `health.beacon_age_ms`, one age per station heard (`records.py:543`) | at each health record in the window, the number of ages ≤ 5 000 ms (a 1 s beacon with jitter); reported as min / median / max over the window. Also the presence records (join snapshot plus live), by state |
| streams carrying items | `frame` records in the window (join snapshot plus live) | distinct `station:stream` labels |
| streams advertised in beacons | **not observable here.** Beacon stream entries stay inside the listener, and record v1 does not carry them | for this host's own two stations, the `--stream` count from their command lines. For the other stations, their hosts: say which, and stop |
| what the code permits | `wire.py`, `station.py`, `listener.py`, `manifest.py`, `ids.py` at `2eb1a56` | caps, with file:line, in REPORT.md. `beacon_sizes.py` computes the per-station advertising bound with the running codec |

### 2. Traffic on the wire at the host daemon

| What | Source | How | Observed or derived |
|---|---|---|---|
| datagrams by kind | the daemon's `health` counters, every 10 s, cumulative since the run began (`records.py:195`, `:548`) | beacons: `Δ beacon.{verified, duplicate, epoch_regression}`. Items and plucks: `Δ` of every `admission.*` counter. Unverified: `Δ unverified.*` | observed |
| datagrams the kernel dropped before the daemon read them | `/proc/net/udp`, the daemon socket's `drops` (matched by inode), every 10 s | `Δ drops`; also the maximum `rx_queue` | observed |
| whole-run average | the same counters at the last health record, over the time since the daemon started (`/proc` start time) | counter ÷ uptime | observed |
| first copies of items: bytes | `frame` records with `source=live`, `admission=verified`, `dedup=first` | count and Σ `frame.bytes` | observed |
| repeats of items: bytes | `Δ admission.duplicate` × the mean `frame.bytes` of the items live during the window (snapshot plus live first copies). Repeats are the same signed bytes (I-4) | bounds: × the smallest and × the largest | **derived** |
| beacons: bytes | `Δ beacons` × the size `beacon_sizes.py` encodes for a beacon with the stream counts the manifest licenses to the stations on air | bounds: the idle 1-entry size up to the typical size at the largest licensed stream count | **derived** |
| record v1 traffic to each binding | `Δ records.emitted`, and Σ `line_bytes` of the live records this probe read | count and bytes per second | observed |

Exact wire bytes for beacons and repeats would need a capture of packet headers on this host, which needs
root, or the senders' own counters on their hosts. This lane does neither. The workorder limits it to the
daemon's and frond-ear's own read surfaces.

### 3. Streams one seat tunes

| What | Source | How |
|---|---|---|
| the seat's tune (🌿, frond-ear ear `frond-scribe`) | `canticle.tune.frond-scribe`, `wakeKeys`, `delivery` in `~/.config/frond-ear/frond-ear.json`, loaded since `frond-ear.service` started (the file is older) | `catalog.py`: patterns, the manifest pairs each resolves to, and what frond-ear's push boundary does with each (allowlisted, mode, wake classes ∩ licensed classes) |
| what the seat's tune caught | `frame` records in the window, each matched against the tune as frond-ear matches it (`station:stream`, where the station may be `*`) | frames and distinct streams, tuned and untuned |
| what frond-ear itself counted | `frond-ear status`: `canticle.counts`, `liveSet` and `ears[frond-scribe].canticleDelivery.counts` | `Δ` over the window, per counter |
| the OpenClaw prince's listener (🌊, binding `ronan`) | `plugins.entries.canticle.config` in `~/.openclaw/openclaw.json`, and its heard journal `~/.openclaw/canticle/<binding>/journal/` | patterns and resolved pairs, delivery mode, payload sessions. Journal entries in the window, by kind; heard entries by disposition and tuned or not |
| a model of frond-ear's pass-over | `daemon_records.py`'s `seat_gate_model`, mirroring `delivery.ts` `#passOver` order | a cross-check only. frond-ear's own counts are the result |

### 4. Items admitted to a turn

| What | Source | How |
|---|---|---|
| exposures to the seat's session | frond-ear's `canticle_custody` table: one row per record pushed (`immediate` or `report`) or returned by `hear`, with claimed, offered (the host handed it to the session) and echoed (the session named the push's whole batch id) | rows claimed in the window, by path, mode and how far each got (`window_close.py`). For context, every row since `canticle.custody.since` |
| pushes and pass-overs | frond-ear's store counters `canticle_pushes`, `canticle_records_pushed`, and the delivery counts in `frond-ear status` | `Δ` over the window |
| the exposure ledger (frond-ear#117) | `canticle.exposure.enabled` | reported as configured. It is off by default, and off it writes nothing |
| the OpenClaw seat | its config (`delivery.mode`, `listen.payloadSessions`), and its state file's checkpoints and taint marks | counts, and how many are newer than `t0` |

Layers are kept apart, as RFC-0002 §0.5 requires. An `offered` push is host-returned. An `echoed` push is
prince-encountered for that token. Model-seen is not proven on either host. "Admitted to a turn" is reported
at the layer each row reaches, never above it.

## After the window

`window_close.py` reads the custody rows, the journals' counts and the OpenClaw heard journal over
`[t0, t1]`. `summarize.py` computes every number in REPORT.md from `results/`, using the formulas above.
REPORT.md separates what the code permits from what was observed, and lists the options §7.1 names with what
each number implies for them. It recommends nothing beyond that.
