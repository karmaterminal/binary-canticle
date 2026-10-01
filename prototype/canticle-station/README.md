# canticle-station (spike)

A runnable spike of [RFC-0001](../../rfc/0001-binary-canticle.md) work items
S1 and S2. It implements the frame v2 codec, a looping station and a
listener, which is enough to put TTL items on a `station:stream` and hear
them loop until they expire.

| RFC-0001 | What this spike implements |
|---|---|
| §9 Wire format v2 | `BC` magic, version, kind and key-id header; deterministic CBOR with integer keys; a domain-separated Ed25519 trailer; the ITEM, PLUCK and BEACON key tables; the 1 100 B frame and 1 200 B datagram limits; `crit` and unknown-key handling. |
| §9.4 Strict parsing | A bounded, strict CBOR decoder (definite lengths, shortest form, sorted and unique keys, depth ≤ 4, ≤ 32 entries, no floats or tags). A bad datagram only ever produces a rejection with a reason. |
| §9.13 Test vectors | Reproduces the RFC's two illustrative vectors byte for byte, using an independent encoder (not `cbor2`). Ships 37 candidate conformance vectors in `vectors/`. |
| §5 Identity | Key-id = SHA-256(pubkey)[0:8]; `stream_id` = SHA-256("canticle-stream/v2" ‖ 0 ‖ name)[0:4]; collisions are refused, never rehashed (#38). |
| §7 Carousel | Signs each item once and resends the same bytes. The expiry is absolute and never reset. A burst goes out at 0, +1, +2 and +4 s, then SAP-style loops with jitter U(2/3, 4/3) and reconsideration. Includes the fair-share regulator with a class floor, the availability ceiling and clamp reasons; supersede-by-key; pluck (a PLUCK loops until the target's expiry); refresh re-issue for keep-on-air; and ring depth. |
| §8 Carrier-beacon | Signed beacons with per-stream heads, live counts, loop and TTL contracts, `next_beacon_ms` (0 = goodbye) and ±10% jitter. Beyond 24 streams it rotates pages with a catalog digest. |
| §7.4-§7.8, §8.6 Listener | Dedup on the identity tuple: a repeat is a no-op, different bytes are an equivocation. Also sticky-pluck, supersession high-water marks, epoch regression, class capability, granted scope, binding scope (a `host` frame heard over UDP is a `scope-violation`) and per-class hop limits from the manifest, all checked before any state changes so a rejected frame is state-neutral; safety state (epochs, dedup digests, sticky PLUCKs, high-water marks) persisted atomically and re-loaded at start, by default (the CLI derives a state file and holds a lease on it; `--ephemeral` is an explicit, warned opt-out, and the library requires `state_path` or `ephemeral=True`), and the §7.8 warm-up for live-state keys, per-key dedup quotas that refuse new tuples rather than evict live ones (supersession marks have their own per-key limit, counted apart from dedup entries and scaled by how much longer marks live; presence keeps at most one share of streams; the beacon stream maps hold one advertised catalog, newest copy of a stream winning: #60), the §9.7 check that a PLUCK carries its held target's `expires_at` and `scope` (evidence `pluck-mismatch`), one class per `state_key` within an epoch (a change in the mark's epoch is dropped as `class-change`; §23.2 q21), and local expiry per RFC §14.6.3: clamped to the class max TTL, moved onto the receiver clock by δ̂, and never longer than the full TTL from first hearing (a PLUCK clamps to the largest class max TTL, since it does not carry its target's class). Presence covers ROOT_UNKNOWN, EQUIPPED_QUIET, EQUIPPED_SPEAKING, UNEQUIPPED_PRESENT and UNOBSERVABLE (with a `signed_off` reason). |
| §10.4 Publisher grants | The station signs only the classes, scopes and streams its manifest entry grants, checked before a `seq` is allocated. The control socket has its own grant, narrower than the key's (`--socket-class`), and never accepts `regulatory`, `alarm` or `control`, because their op-level and typed-body checks (§10.4, §15.4) are not implemented here; `host` scope is refused because this station only speaks UDP; one station per key (an exclusive lease on the key file); epochs from a locked, fsynced counter. |
| §11.1-§11.2 Bindings | Host-local submission over a unix socket (mode 0600, peer uid checked); UDP unicast and LAN multicast (`239.255.13.13:9999`, provisional per D22, IP TTL 1, don't-fragment). |
| §15.8 Background emitter (#58) | `canticle ambient`: paced, short-TTL items from a fixture file through the station's socket, with no model calls, capped cadence and size, and a bounded run. |
| §18.9 Web tuner (#57) | `canticle tuner`: a loopback-only gateway over one listener, and a read-only page to pick a station:stream and watch its live ring, with expiry and gaps shown honestly. |

Not implemented here, and still open work (see RFC-0001 §23.3):
- relay leases for internet listeners (§11.3)
- signed fleet manifests and the genesis pin; the manifest here is plain JSON (§10.3)
- typed-body schemas, content policy and taint checks before signing (§15)
- accord (§10.7) and control frames (§10.6)
- the receptor's landing into agent sessions, banners and taint (§14)
- DNS-SD (§13)
- the ringserver bridge (§18; see [`../ringserver-proofs/`](../ringserver-proofs/))
- the capsid (§8.7)
- work-conserving budget redistribution and burst budget accounting (§7.5-§7.6)
- IPv6 groups and `canticle doctor`
- `trail_seq` in beacon stream entries (amendment A1, added to RFC-0001 §9.8 after this spike). The beacons and candidate vectors here still use the 8-field entry.

The decoder is stricter than the RFC in one place: it rejects floats and tags under every key, not only core keys 1-31.

## Try it

Requires Python 3.11+ and `cryptography>=45`.

```sh
cd prototype/canticle-station
python3 -m venv .venv && . .venv/bin/activate && pip install -e .

canticle keygen --out cael.key --manifest fleet.json --name cael \
  --classes chatter,live-state,root --streams chatter,lens.threat,root

canticle listen --manifest fleet.json --bind 0.0.0.0:9999 --multicast &   # one JSON event per line; state under $XDG_STATE_HOME/canticle
canticle station --key cael.key --manifest fleet.json --stream chatter --stream lens.threat:live-state --stream root:root \
  --multicast --control ./cael.sock &

canticle sing --control ./cael.sock --stream chatter --text "port-scan burst from 10.0.0.7" --ttl 30
canticle sing --control ./cael.sock --stream lens.threat --state-key now \
  --text "what is now and threat: elevated" --keep-on-air 120
canticle hush --control ./cael.sock --stream chatter --seq 1
canticle status --control ./cael.sock
```

On 2026-09-27 this ran as separate processes over multicast on one host. `sing` returned the effective TTL, loop and clamp, for example `{"ok": true, "stream": "chatter", "seq": 1, "ttl_s": 30.0, "loop_ms": 10000, "clamp": "none", "size": 151, ...}`. The listener printed:

```json
{"event": "presence", "station": "cael", "state": "ROOT_UNKNOWN", ...}
{"event": "item", "station": "cael", "stream": "chatter", "seq": 1, "class": "chatter", "text": "port-scan burst from 10.0.0.7", ...}
{"event": "item", "station": "cael", "stream": "lens.threat", "seq": 1, "class": "live-state", "state_key": "now", "text": "what is now and threat: elevated", ...}
{"event": "withdrawn", "station": "cael", "stream": "chatter", "seq": 1, "by_seq": 2, "reason": 0}
{"event": "presence", "station": "cael", "state": "UNOBSERVABLE:signed_off", ...}
```

Each item was heard once, although the station sent it many times. The last line is the goodbye beacon the station sends on shutdown.

The station keeps its epoch counter next to its key (`cael.key.epoch`; `--epoch-file` overrides the path). Each start takes `max(previous + 1, unix seconds)` and writes it before the first frame, so a restart never reuses a `seq` (RFC §5.2).

### From an agent harness

- **Claude Code.** Run `canticle listen …` as a background command under the Monitor tool: each line becomes an event the session sees. Put items on air with `canticle sing` through Bash.
- **OpenClaw.** Call `canticle sing` from an exec tool.

Do not pipe heard text straight into a session. RFC-0001 §14 and §16 require a banner outside the external-content wrapper, taint after hearing, and receiver-local wake policy. That landing layer is work item S3.

### Background emitter (#58, RFC §15.8)

```sh
canticle station --key room.key --manifest fleet.json --stream hymn:ambient --multicast --control ./room.sock &
canticle ambient --control ./room.sock --stream hymn --fixture proofs/web-lanes/hymn.txt \
  --ttl 60 --min-gap 2 --max-gap 10 --breath 0.2 --duration 600 --log emit.jsonl
```

- **One process, one job.** The emitter is a separate process that talks to the station's control socket. It never signs, listens or learns who hears; the station keeps the carousel.
- **Cadence.** Each tick, after a random 2-10 s, it either sings one fixture line with a 60 s TTL, or takes a breath and sends nothing (`--breath` is the chance of a breath). Lines may repeat: a repeat is a new item with the same body, which adds no weight (RFC §12.1).
- **Bounds.** Only `ambient` or `chatter`. At most `--max-per-minute` items, no line longer than `--max-bytes`, and at most one tick a second. The run ends after `--duration` seconds (at most 3 600) or on SIGINT/SIGTERM.
- **Stopping.** Items already on air are not plucked; they loop until they expire naturally. The emitter also gives up after three consecutive failures to reach the station.
- **Log.** Each tick writes one JSON line (`sing` with `seq`, `size`, `loop_ms` and the text; `breath`; `capped`; `refused`). The first and last lines record `model_calls: 0`.
- **Sources.** Only a fixture file. A source derived from session logs would be a separate opt-in boundary (RFC §15.4, §15.8), and is not implemented.

### Web tuner (#57, RFC §18.9)

```sh
canticle tuner --manifest fleet.json --multicast --http 127.0.0.1:8765
# then open http://127.0.0.1:8765/
```

- **What it shows.** The gateway runs one listener, which hears and verifies every stream its manifest names. The page lists the stations whose beacons verified (key, epoch, presence, beacon age) and their streams (head, live count, loop). Tune a named stream to watch its live ring. Each item shows its text, `seq`, copies heard and a countdown to local expiry. Items that just left the air are listed for 60 s, labelled expired, withdrawn or superseded. Sequence numbers up to the head that this listener never heard are listed as gaps.
- **What it is not.** Tuning is local to the gateway, and nothing is sent to a station. It is not a session tune: nothing lands anywhere. The gateway has no control socket and cannot sing or hush. A late page sees only what is on air now.
- **Trust boundary.**
  - It binds loopback only, and refuses any other address.
  - It answers only requests whose `Host` is its own address, which blocks DNS rebinding, and refuses cross-origin POSTs and non-JSON bodies.
  - It serves a strict CSP (`script-src 'self'`, no inline script), plus `nosniff`, `no-referrer` and `no-store`.
  - Heard text is set with `textContent` only, never parsed as markup.
  - Unverified datagrams are counted, never shown or attributed to a station.
- **Budget.**
  - Channels: at most 16 tuned at once; each lapses after 30 s without a poll.
  - Polling: at most 4 ring polls a second per channel (the page polls every second).
  - Responses: at most 64 items, with 512 characters of text each; up to 32 tombstones and 64 gap checks.
  - Memory: per channel, the gateway keeps at most 128 heard `seq` values (the gap window, moving up with the head and reset at each epoch) and 32 tombstones. The listener's own per-key quotas bound the rest (RFC §7.4).

Unnamed streams (not in the manifest) are verified and listed, but can't be tuned (RFC §5.4). The beacons in this spike carry no `trail_seq`, so a gap can't be told apart from an item that is still looping.

### Same-host proof for #57 and #58

[`proofs/web-lanes/`](proofs/web-lanes/) holds a bounded run as root (`run.sh`), its analysis (`analyze.py`) and the results. The station and emitters run in one network namespace; the listeners, tuner and headless Chromium run in another, joined by a veth pair over LAN multicast. That is **same-host** evidence, on one kernel and one clock. It is not a second host.

## Tests

```sh
python -m unittest discover -s tests      # 75 tests, about 7 s
python -m canticle vectors                # regenerate vectors/frame-v2-candidates.json
```

CI (`.github/workflows/tests.yml`, job `station-tests`) runs the same suite from the repository root with `PYTHONPATH=prototype/canticle-station`, on dependencies locked by hash in `.github/ci/`.

- `test_wire.py` covers:
  - strict CBOR, including RFC 8949 core map-key order checked against bytes from an independent encoder (fxamacker/cbor), and the RFC §9.13 vectors byte for byte;
  - the RFC §9.11 size budget (745 / 720 / 1 100 B);
  - all 37 candidate vectors;
  - a check that the committed vectors file equals the generator's output;
  - a 20 000-case fuzz run (random bytes and mutations of valid frames) in which nothing but a `Reject` ever escapes.
- `test_station.py` drives the carousel on a virtual clock:
  - burst timing, byte-identical repeats, jitter bounds and stopping before expiry;
  - the regulator's fair share, class floor and degraded shedding;
  - supersede, pluck (including a late pluck that must never be shed, a PLUCK that depth never evicts, and a refused hush that must change nothing) and refresh re-issue (which keeps provenance flags), and one class per state_key within an epoch (a change is refused before a seq is used, and a key is forgotten once no receiver can hold its mark, so the table stays bounded);
  - depth, stream-id collisions and beacon pages;
  - a late joiner hearing every live item within `loop_ms × 4/3`;
  - the persisted epoch counter: strictly increasing across same-second restarts and a clock that steps back.
- `test_listener.py` covers the presence state machine, local expiry, the §14.6.3 clock rule (including a station clock an hour behind), state-neutral capability rejection, per-key dedup quotas, the #60 per-key bounds (admitted-only stream hearing, one catalog of beacon stream maps with the newest copy winning, a separate mark limit that still fits honest state_key churn at the §7.4 floor, mark horizons that never shrink under mixed classes, stay bounded whatever the clock offset, tolerate a later rise in δ̂ and are not held open by refused older items, purges that pop only what expires, the resurface path's mark check, a plucked newer value that still supersedes, a plucked older item reported as plucked, refusals that do not advance the epoch, sticky PLUCKs timed on the current δ̂, a class change in the mark's epoch dropped as `class-change` while a new epoch may change it, marks persisting their class, PLUCK expiry clamp and target match, state v3 (marks carry their class, learned on resurface from older state) with v1 and v2 still loading), garbage input and station restarts (a new epoch's beacons count from 1 again; two starts in one second never reuse an identity tuple).
- `test_udp_e2e.py` runs a real station and listener over loopback UDP and the unix control socket: sing, listen, hush, status and goodbye.
- `test_ambient.py` runs the emitter on a virtual clock: tick gaps, breaths and repeats, exact requests, the per-minute cap, stop by signal and by duration, refusals, an unreachable station, bounds and fixture loading.
- `test_tuner.py` covers the tuner's view and gateway:
  - verified stations with heads, and unnamed streams that can't be tuned;
  - the live ring, then labelled expiry and withdrawal;
  - a late view that sees only what is on air, with the missed `seq` as a gap;
  - a lost burst repaired by the next loop copy;
  - subscriptions (leave, retune, idle lapse, the cap);
  - bounded memory on a long stream (600 items, at most 128 heard `seq` values kept, the one lost recent item still shown as the only gap), and a fresh window after an epoch change;
  - the HTTP boundary: headers and CSP, tune, ring, leave and retune, the poll limit, `Host` and `Origin` checks, content type, methods, no write endpoints, loopback only.

## Vectors

[`vectors/frame-v2-candidates.json`](vectors/frame-v2-candidates.json) contains:
- 23 parse-level cases (datagram → `accept` or a rejection reason);
- 14 listener-level sequences (datagrams → events). Two are timed: with optional `at_ms`, time advances to `at_ms[i]` (local expiry applied, its events not listed) before datagram `i` is heard; `per_key_quota` and `per_key_mark_quota` fix the listener's per-key limits for dedup entries and for supersession marks, counted separately (§7.4).

It covers the #48 acceptance set (valid, wrong key, tampered, unknown key, revoked, expired, replayed) and every case RFC-0001 §9.13 lists: repeat-as-no-op, equivocation, non-deterministic CBOR, `crit`-unknown, a 1 101-byte frame, a depth bomb, a float in a core key, a future `issued_at` and pluck-before-original. The #60 sequences pin a PLUCK whose `expires_at` differs from its held target's, a far-future PLUCK that holds its dedup slot for one day at most, and supersession marks held to their own per-key limit. The §23.2 q21 sequences pin a class change in one epoch, newer or older (dropped as `class-change`, which outranks `superseded`), and one across epochs (allowed). It also includes a regression for the prototype's bug B1 (the 11-byte `{"a":1e400}`).

Keys are the RFC 8032 §7.1 test keys. The vectors are **candidates**: they become normative when a second, independent implementation (for example the TypeScript codec planned in S1) reproduces them.
