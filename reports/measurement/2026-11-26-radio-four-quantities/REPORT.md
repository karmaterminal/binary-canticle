# RFC-0002 §7.1: 🌊's four quantities on the built path (ronan, 2026-11-26)

**Status:** this is a measurement report for RFC-0002 §7.1 ("what the radio remembers") and
[frond-ear#116](https://github.com/karmaterminal/frond-ear/issues/116). It is read-only: nothing was sung,
hushed, tuned, granted, restarted or reconfigured. The method and instruments were committed and pushed at
`a3768b1` (09:10:20Z), before the window opened at 09:10:26Z. They are in [METHOD.md](METHOD.md) and
[`harness/`](harness/). The published data is in [`results/`](results/), and every number below comes from
`results/summary.json`, which [`harness/summarize.py`](harness/summarize.py) computes. No heard text, station
name, key id, address or session id appears anywhere in this directory.

**Window:** 2026-11-26 09:10:26Z to 09:55:27Z (2 701 s) on ronan (aarch64), at the host daemon and the two
receivers bound to it: 🌿's frond-ear seat and 🌊's OpenClaw binding. For context, the report also gives the
daemon's counters over its whole run (4.12 days, since 2026-11-22 06:58Z) and frond-ear's custody history since
2026-11-22 04:29Z.

## Headline

| # | Quantity (🌊, [#161](https://github.com/karmaterminal/binary-canticle/issues/161#issuecomment-7087387526)) | Observed today | What the code permits |
|---|---|---|---|
| 1 | **Catalog size** | 8 stations and 15 `station:stream` pairs are licensed (9 stream names). 6 stations have beaconed this daemon run; **5 were on air for the whole window** and 1 had signed off. **Items came from 1 stream of 1 station** in the window | no cap on stations; 32 streams a station; 12 500 live items per key |
| 2 | **Traffic at the host daemon** | **5.11 datagrams/s**: 5.00 beacons/s (98.0 %), 0.10 items/s (4 first copies, 274 repeats), 0 plucks, 0 unverified, **0 kernel drops**. About **0.93 KB/s** (0.79–1.31), almost all of it beacons. Only the first copies' 756 B is observed; the rest is derived | 16 kbit/s of items per station, plus a beacon a second; no admission control before verify |
| 3 | **Streams one seat tunes** | 🌿's seat tunes 5 patterns, which resolve to **4 licensed pairs** on 3 stations. One pattern names a stream no manifest entry licenses. frond-ear may push from 2 of those pairs, and only 1 of those may wake. 🌊's binding tunes **1 pair**. **No tuned stream carried an item in the window** | any number of patterns; 4 096 live records an ear |
| 4 | **Items admitted to a turn** | **0 in the window**: no push, no `hear` read, no custody row, no OpenClaw read. Since 2026-11-22: **7 exposures on the seat** (4 pushes, each echoed by the session's own turn, and 3 `hear` returns, which are host-returned only). On the OpenClaw seat, nothing can reach a session unasked, no session may read heard text, and no session ever has | 300 pushed records an hour per ear by default, 3 600 at most; on OpenClaw, explicit reads of at most 20 entries a call |

So today the broadcast plane at this host carries presence. 98 % of datagrams are beacons. The only items in
the window were refreshes of one untuned live-state stream. A seat tunes four streams, and almost nothing heard
reaches a turn. That is because of the seat's allowlist and class gates, not because of the transport.

## The refs

| Ref | Value |
|---|---|
| product/base | binary-canticle `main` `2eb1a56d8fe4f1b250d4da3adec5611292f66948` (local = tracking = server at the lane's start) |
| running canticle code | the live clone's HEAD `ba980e32eaa203390a59b73806bdfaf04a14abb3`. `wire.py`, `cbor.py`, `records.py`, `daemon.py`, `listener.py`, `station.py`, `ids.py` and `manifest.py` are byte-identical to `2eb1a56`, so every pointer into them below is good at both (`__main__.py` is not; its one pointer gives both lines). `main` adds `beacon.py`, `dns_browse.py` and `grant.py`, which this host does not run |
| frond-ear | `405e49183f76ed03066fe4d93bd4f75c2cdcc541` (`main`, server-equal; `frond-ear.service` started after the merge, at 2026-11-24 18:05:19Z) |
| OpenClaw binding | `~/.openclaw/extensions/canticle`: its `index.ts` and 13 `src/*.ts` are byte-identical to `prototype/openclaw-canticle` at `8db697f6d65ce8881c1ecac4234467d0728c8433` (and back to `89cc546d`). Loaded by `openclaw-gateway.service` since 2026-11-17 |
| lane | `codeagent/radio-four-quantities`: method at `a3768b1`, this report after it |
| CI | none: `tests.yml` runs nothing under `reports/`, and no product code changed |
| presentation | N/A |

## 1. Catalog size

| What | Source | Command | Raw count |
|---|---|---|---|
| licensed stations | the manifest the daemon loaded. Its `hello` says its SHA-256 matches `~/.binary-canticle/fleet.json` (spike-0, unsigned) | `harness/catalog.py` | **8** stations |
| licensed `station:stream` pairs | the same | the same | **15** pairs, 9 distinct stream names. By station: 5, 3, 2, 1, 1, 1, 1, 1. 1 public stream |
| classes licensed | the same | the same | chatter 7 stations, live-state 3, advisory 1, ambient 1, finding-ref 1 |
| stations heard this run | `health.beacon_age_ms` (one age per station whose beacon the daemon verified) | `harness/daemon_records.py` | **6** of 8 |
| stations on air | the same, at each of 270 health records | the same | **5** at every record (age ≤ 5 s and ≤ 30 s alike). The sixth's last beacon was 37 h old |
| presence | the join snapshot plus live `presence` records | the same | 5 `ROOT_UNKNOWN` (on air), 1 `UNOBSERVABLE:signed_off`; **0 changes** in the window |
| streams carrying items | `frame` records: the join snapshot at t0 plus live ones | the same, then `harness/sanitize.py` | **1** stream of **1** station: 5 live-state items, all refreshes, each frame 189 B with a 39-byte CBOR body |
| streams advertised in beacons | not in record v1: beacon stream entries stay inside the listener | — | this host's own two stations sing 3 and 1 streams (from their command lines). Neither sings to this daemon. **The other stations' advertised streams need their hosts**, so the count stops here |

What the code permits for the catalog:

| Bound | Value | Where (binary-canticle `2eb1a56`, `prototype/canticle-station/canticle/`) |
|---|---|---|
| stations a manifest may list | no cap in the spike's loader | `manifest.py` |
| streams one station may sing | **32** at the default budgets. Each stream keeps at least 500 bit/s of B_station's 16 000, so a 33rd is refused ("stream budgets cannot fit B_station"). The beacon's 8-page catalog alone would allow 136 (17 entries a page) | `station.py:33`, `:218-230`; `:36`, `:188`; computed by `harness/code_bounds.py` and `harness/beacon_sizes.py` |
| stream ids | 32 bits of SHA-256 of the name. A collision is refused, never rehashed | `ids.py:71-84` |
| items one key may have live at the daemon | 12 500: the 100 000-entry dedup store split across the manifest's 8 keys | `listener.py:155`, `:493-497` |

## 2. Traffic on the wire at the host daemon

**Datagrams** (observed: the daemon's own `health` counters, cumulative since the run began. Δ is from the first
to the last of 270 health records in the window, 2 690 s apart; kernel drops come from 271 samples of the socket's
row in `/proc/net/udp`):

| Kind | Counter | Δ in window | Per second | Per hour | Whole run (4.12 d), per second |
|---|---|---|---|---|---|
| beacon | `beacon.verified` (+ `duplicate`, `epoch_regression`: 0) | **13 461** | **5.00** | 18 013 | 4.74 (1 687 235) |
| item, first copy | `admission.verified` | **4** | 0.0015 | 5.4 | 0.0031 (1 122, about 270 a day) |
| item, repeat | `admission.duplicate` | **274** | 0.10 | 367 | 0.107 (37 980) |
| pluck | `retract.plucked` + `held_plucked` (a first-copy pluck is not an admission; `records.py:373-377`) | 0 | 0 | 0 | 0 |
| unverified (unknown key, bad signature, expired, malformed…) | `unverified.*` | **0** | 0 | 0 | 0 |
| dropped by the kernel before the daemon read it | `/proc/net/udp` `drops` | **0** (0 since the socket opened; receive queue never above 0 B) | 0 | 0 | 0 |
| **total** | | **13 739** | **5.11** | 18 385 | |

No datagram in the window was a manifest: frame v2 has no manifest kind (`wire.py:22`). The manifest is a local
file.

**Bytes.** The daemon records bytes only for a verified first copy (`frame.bytes`, `records.py:458`). Beacons and
repeats are counted, never sized, so their bytes are derived:

| Part | How | Bytes in window | Per second |
|---|---|---|---|
| first copies | observed: Σ `frame.bytes` | 756 (4 × 189) | 0.28 |
| repeats | **derived**: 274 × the size of the items live in the window. All 5 were 189 B, and a repeat is the same signed bytes (I-4), so this one is tight | 51 786 | 19.3 |
| beacons | **derived**: 13 461 × the size the running codec gives a beacon with 2 stream entries (182 B; the manifest's mean is 1.9 streams a station). Range: 153 B (1 idle entry) to 257 B (5 entries, the largest grant) | 2 449 902 (2 059 533 – 3 459 477) | 911 (766 – 1 286) |
| **total** | | | **930 B/s (785 – 1 305)** |

Exact beacon bytes would need the senders' counters on their hosts, or a root capture of packet headers on
this host. This lane took neither (METHOD.md).

**Records to each binding** (observed): the daemon emitted 277 records in the window (0.10/s): 270 `health`,
4 `frame` and 4 `retract` (supersession of the refreshed items), most of them health. Over the whole run it
emitted 69 383 records (0.19/s) and dropped none for any binding. It used 11.6 s of CPU in the 45 minutes
(0.43 % of one core) and stayed at 24 MiB resident.

What the code permits for the wire:

| Bound | Value | Where |
|---|---|---|
| a station's item traffic | B_station 16 kbit/s across its streams (4 kbit/s a stream before fitting), plus one beacon every 1 s ± 10 % | `station.py:32-33`, `:505-508`; `__main__.py:766` (`:640` at the running `ba980e3`) |
| one frame / one datagram | 1 100 / 1 200 bytes | `wire.py:25-26` |
| admission at the first hop | none at this SHA. Every datagram is parsed and verified, and each new item waits for a durable write. #171 measured about 40 new items/s sustained on this host, beyond which the kernel drops silently. Fair admission (#173) is held | `daemon.py:489-491`; RFC-0002 §2.7 |
| bindings | 16 connections, 1 024 records queued each | `daemon.py:63-64` |

Against those bounds: the daemon took 0.0015 new items/s in the window, about 1/27 000 of #171's sustained rate.
Five stations on air could send up to 80 kbit/s of items by budget. They sent about 0.15 kbit/s, and the
beacons about 7 kbit/s.

## 3. Streams one seat tunes

**🌿's seat** (frond-ear ear `frond-scribe`; `canticle.tune`, `wakeKeys` and `delivery` in its config, unchanged
since before `frond-ear.service` started). Patterns are numbered in config order; stations and streams are not
named:

| Pattern | Resolves to | Allowlisted on `wakeKeys` | Delivery mode | Classes that key may wake ∩ licensed classes | What frond-ear does with a record |
|---|---|---|---|---|---|
| P1 (`*:` a stream name) | **0 pairs**: no manifest entry licenses that stream name | — | — | — | nothing to hear |
| P2 | 1 pair | no | immediate | — | passed over, `not_allowlisted`; readable with `hear` |
| P3 | 1 pair (same station as P2) | no | immediate | — | passed over, `not_allowlisted` |
| P4 | 1 pair | yes (key with classes) | immediate | chatter | **pushed, and wakes** |
| P5 | 1 pair | yes (bare key: alarm only) | immediate | none (the station is licensed ambient only) | passed over for good, `wake_withheld:ambient` (#176 decision 1) |

So the seat tunes **4 licensed pairs on 3 stations**. 2 of them are allowlisted, and 1 can ever reach the session
unasked. The ear-wide ceiling is `off`; the per-station entries are `immediate`.

| What | Source | Command | Raw count |
|---|---|---|---|
| records on the tuned streams in the window | daemon `frame` records matched against the tune, as frond-ear matches it | `daemon_records.py`, `sanitize.py` | **0** frames and 0 streams. The 5 items in the window were all on one untuned stream |
| frond-ear's own delivery counters | `frond-ear status`, every 120 s (24 samples) | `host_sampler.py` | **Δ 0** for every counter. Since frond-ear started (39.8 h before t1): `not_allowlisted` 125, `wake_withheld:ambient` 3, nothing pushed |
| frond-ear's live set | the same | the same | 1 record (the untuned stream's current item) of 4 096; 0 omitted; receive health `ok`, connected throughout |
| presence as frond-ear sees it | the same | the same | 5 `ROOT_UNKNOWN`, 1 `UNOBSERVABLE:signed_off` (agrees with §1) |

**🌊's OpenClaw binding** (`plugins.entries.canticle.config`, binding `ronan`):

| What | Raw count |
|---|---|
| tune | 1 pattern → **1 licensed pair** (P4's pair) |
| delivery | `explicit` (the only mode this version has); `listen.payloadSessions`: **0** sessions; `includeSelf` off; publish off |
| tools | `canticle_listen`, `canticle_status` and `canticle_mute` are on the gateway's `tools.alsoAllow`. AGENTS.md's map says no seat runs this spike, and its README asks that no seat allowlist its tools until §23.2 question 24 is decided (`prototype/openclaw-canticle/README.md:43-45`). Both statements are out of step with this host. Noted for 🌊; this lane changed nothing |
| heard journal in the window | **0** entries of any kind |
| heard journal, all it retains | 4 835 entries, all `presence`, between 02:07Z and 05:06Z today. They alternate (2 418 `ROOT_UNKNOWN`, 2 417 `UNOBSERVABLE`, all live, one daemon run): a station flapping in and out of presence about every 2 s for three hours. That was before the window, and there were 0 presence changes in it. It is outside the four quantities and is noted for 🌊, who owns the join |

What the code permits for tuning:

| Bound | Value | Where |
|---|---|---|
| patterns a frond-ear ear may tune | any number; each `station:stream`, with `*` allowed for the station and the stream exact | frond-ear `src/config.ts:356-375`, `src/daemon.ts:396` |
| what an ear holds | 4 096 live records (each tuned stream a share of its own, every untuned stream one share together) and 256 stations' presence | frond-ear `src/canticle/records.ts:34-40`, `:58-59` |
| what may be pushed | a record on a tuned stream, from a `wakeKeys` key, sung at hop 0 and not wake-derived, under a mode that pushes, and of a class the key may wake (a bare key: alarm only). Otherwise it is passed over and counted by reason, and stays readable with `hear` | frond-ear `src/canticle/delivery.ts:1332-1340`, `:934-962`; `src/config.ts:445` |
| the OpenClaw binding's view | 1 024 items; a journal of 5 000 entries, 8 MiB or 24 h | `prototype/openclaw-canticle/src/receive.ts:159`, `src/journal.ts:74` at `8db697f` |
| the daemon | hears every stream. Selection at the tower (RFC-0002 §2.4 step 1) is not built | RFC-0002 §2.4 |

## 4. Items admitted to a turn

Layers as RFC-0002 §0.5 names them. A row is reported at the layer it reached, never above it.

| What | Source | Command | In the window | Since 2026-11-22 04:29Z (custody is whole from then) |
|---|---|---|---|---|
| pushes (`immediate` or `report`) | frond-ear `canticle_custody`, read-only | `harness/window_close.py` | **0** | **4** `immediate` pushes, 1 record each (11-22 07:11Z, 11-22 10:42Z, 11-24 00:01Z, 11-24 13:22Z). All 4 were offered (host-returned) and then echoed: the session named each push's whole batch id with `ack`. That is prince-encountered for that token |
| `hear` returns | the same | the same | **0** | **3** (11-24 19:59Z – 20:42Z). `hear` stamps custody `echoed` at its return, before the model has seen the result, so these are host-returned only (RFC-0002 §0.5) |
| model-seen | — | — | unknown | unknown: Claude Code has no model-input settlement (§0.5) |
| store counters | `canticle_pushes`, `canticle_records_pushed` | `host_sampler.py` | Δ 0, Δ 0 | 12 and 12 over the store's life |
| push budget in use | `frond-ear status`: pushes in the last hour, records waiting, holds | the same | 0 of 60; 0 waiting; no hold | — |
| exposure ledger (frond-ear#117) | `canticle.exposure` | `catalog.py` | off (the default), 0 rows | — |
| the OpenClaw seat | config and `state.json` | `catalog.py`, `host_sampler.py` | **0**: nothing is pushed (`explicit`). No session may read heard text, so a read returns digests only. 0 taint marks; the one checkpoint last moved 2026-11-14 | 0 taint marks ever |

What the code permits for admission:

| Bound | Value | Where |
|---|---|---|
| pushes to one frond-ear ear | 5 records a push (at most 10) and 60 pushes an hour (at most 360): **300 records an hour by default, 3 600 at most**. An immediate burst coalesces for at least 5 s, and each push is capped at `limits.maxNotificationChars` (6 000 on this seat) | frond-ear `src/config.ts:578`, `:582-590`, `:241-244`, `:834-838` |
| an OpenClaw session | nothing unasked (`delivery.mode` has only `explicit`). Heard text goes only to sessions listed in `listen.payloadSessions`; a read returns at most 20 entries | `prototype/openclaw-canticle/src/config.ts:78`, `:88`, `src/tools.ts:53` at `8db697f` |

Against those bounds: 0 of 300 in the window, and 7 exposures in 4.2 days.

## What each number implies for §7.1's options

RFC-0002 §7.1 keeps two options open. Its owners are 🍃 and 🌿, with the princes' approval:

- **(A) A declared exception.** RFC-0001 §21 gains an exception for recovered streams, as it did for relay
  repair (A2). §2.5's publisher spool and §2.2's replayable rings then sit on the broadcast plane.
- **(B) A separate surface.** Recovered streams leave the broadcast plane. The carousel stays live and lossy.

What the numbers support, and no more:

1. **Catalog.** 15 licensed pairs, 5 stations on air, and 1 stream with items in 45 minutes. Today's catalog is
   about three orders of magnitude below the 10 000 `station:stream`s of figs's framing (#161), and below the
   code's own bounds (32 streams a station, 12 500 live items a key). At this size, neither option is forced
   by catalog size: per-stream bookkeeping (a cursor and a retention class per stream) would be small either
   way. Nothing measured here says how either option behaves at 10 000.
2. **Wire.** The plane carries presence: 98 % of datagrams are beacons, at about 0.9 KB/s. The 0.10 items/s
   are repeats of live-state refreshes. No stream declares §2.1's axes, and no recovered or replayable stream
   exists to measure, so neither option's extra traffic can be measured yet.
   - Under (A), recovered items would cross the same first hop. That hop took 0.0015 new items/s here, against
     #171's sustained 40/s, beyond which loss is silent. A ring downstream cannot recover first-hop loss
     (frond-ear#116 amendment 1).
   - Under (B), they would not cross it.

   The numbers say the first hop has room today. They do not measure a ring, a spool or their cost (§7.3).
3. **Streams one seat tunes.** One seat tunes 4 pairs and the other receiver 1. The per-reader replay state
   either option needs (a cursor per tuned stream) is 4 entries or fewer per seat today. None of the tuned
   streams spoke in the window. In the 39.8 h before t1, frond-ear counted 128 records on the seat's tuned
   streams, and passed over every one.
4. **Items admitted to a turn.** 0 in the window, against a permitted 300 an hour. 7 exposures in 4.2 days.
   What keeps the turn small today is policy (2 of 15 licensed pairs may push to the seat, 1 may wake, and the
   OpenClaw seat reads explicitly and gets digests). The transport plays no part. The numbers do not
   distinguish (A) from (B) on admission: under either one, what reaches a turn would pass the same ear gates.

**What these numbers cannot decide:**

- whether any prince needs a recovered stream (no stream declares one);
- what a ring per retention class or a publisher spool costs (§7.3);
- behaviour at 10 000 streams;
- the other hosts' views. 🍃's ear is on silas, and the other stations sing from their own seats.

## Gaps, and what needs another host

- **Streams advertised in beacons** by the five remote stations heard here. Record v1 does not carry beacon
  stream entries, so the count needs each sender's host: its `canticle station` command line, as §1 read it for
  this host's own two stations. Stopped here.
- **Exact wire bytes for beacons and repeats.** These need the senders' counters on their hosts, or a root
  capture of packet headers on ronan. Neither was taken (TROUBLE posted at the window's start). The derived
  figures above give their method and bounds.
- **🍃's seat on silas.** It is the second Claude-seat receiver, with its own tune, custody and host daemon.
  Its numbers need silas.

## How the numbers were checked

- **Integrity** (`summary.json`, `integrity`):
  - one probe connection, held from t0 to the deadline, under one daemon run and one daemon process;
  - every health counter, the socket's `drops` and frond-ear's counters non-decreasing across the window, so no
    restart fell inside it;
  - `records.dropped` Δ 0 and `peers_closed` Δ 0, so the probe cost no binding a record;
  - health `ok` with no reasons, and the manifest the daemon loaded matches the file;
  - frond-ear attached at all 24 samples.
- **Observer effect.** The probe took one daemon connection and added one to the daemon's `snapshots.requested`
  and `served`. `frond-ear status` ran 24 times. frond-ear's store was opened read-only.
- **Independent review after the window opened.** A separate reviewer read the harness for leaks and wrong
  numbers. The instruments that collected the data are unchanged since `a3768b1`. Its findings changed what
  happens after collection:
  - `harness/sanitize.py` builds the published `results/` from the raw files. Per-frame records (a salted
    station label, a class and an arrival time) would let a reader follow one station's timeline wherever its
    licensed class is unique. That is the "river" tier display grants leave to the station (#137), so frames are
    published only as window counts (`frames.json`). Their records, with the rest of the raw output, stay on the
    seat under `~/.local/state/frond-scribe/radio-four-quantities-2026-11-26/raw/`. The sanitizer also turns the
    daemon's run id into a label, keeps store counter names only up to a `.` (frond-ear names some per ear),
    closes class names, and drops the manifest digest prefix.
  - `harness/summarize.py` counts plucks from `retract.plucked` (none occurred), subtracts warm-up releases
    (none), uses the plain mean size of live items for repeats (a snapshot entry's remaining life is not in the
    projected record), compares the seat model over verified, surfaced records only, and checks for restarts.
  - `harness/code_bounds.py` computes the station and dedup bounds with the running code.
    `harness/leak_check.py` compares the published files with every manifest name and key id, the seat's tuned
    stream names, the session ids and custody digests in frond-ear's store, the OpenClaw binding's session keys,
    IPv4 addresses, long numeric ids and unexpected digests. It printed **0 hits**.
- **Limits that remain in the instruments:**
  - `closed()` without a word set accepts any short lowercase word. Each such field was checked against its
    source and carries only closed words at the running SHAs.
  - `frond-ear status`'s custody counts drop the camel-case states (`echoedBoundaryUnknown`,
    `echoedBeforeBoundary`); the custody table read covers custody.
  - The seat model does not model a mute or a key listed twice; neither occurs in this config.
  - The ≤ 5 s beacon-age test assumes 1 s beacons. The presence states agree: 5 on air.
  - The beacon-byte estimate uses the mean stream count over all 8 licensed stations (1.9, so 2 entries). METHOD.md
    said the stations on air, but salted labels cannot be joined to the manifest. The 153–257 B range covers every
    licensed count.

## Reproduce

From this directory, on a host whose own owner agrees (read-only, about 46 minutes):

```sh
harness/run.sh <raw-dir> 2700                     # catalog, beacon sizes, the record probe, the sampler, the close
~/.venvs/canticle/bin/python -B -I harness/code_bounds.py --out <raw-dir>/code-bounds.json
python3 -B -I harness/sanitize.py <raw-dir> results
python3 -B -I harness/summarize.py results > /dev/null    # writes results/summary.json
python3 -B -I harness/leak_check.py results               # exit 1 on any hit
```

`summarize.py` and `leak_check.py` reproduce every number here from `results/`, except that `leak_check.py`
also reads the seat's own files to compare against.
