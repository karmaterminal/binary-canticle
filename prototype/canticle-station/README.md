# canticle-station (spike)

A runnable spike of [RFC-0001](../../rfc/0001-binary-canticle.md) work items
S1 and S2. It implements the frame v2 codec, a looping station and a
listener, which is enough to put TTL items on a `station:stream` and hear
them loop until they expire.

| RFC-0001 | What this spike implements |
|---|---|
| §9 Wire format v2 | `BC` magic, version, kind and key-id header; deterministic CBOR with integer keys; a domain-separated Ed25519 trailer; the ITEM, PLUCK and BEACON key tables; the 1 100 B frame and 1 200 B datagram limits; `crit` and unknown-key handling. |
| §9.4 Strict parsing | A bounded, strict CBOR decoder (definite lengths, shortest form, sorted and unique keys, keys that are integers or text strings only at every depth, depth ≤ 4, ≤ 32 entries, no floats or tags). A bad datagram only ever produces a rejection with a reason. |
| §9.13 Test vectors | Reproduces the RFC's two illustrative vectors byte for byte, using an independent encoder (not `cbor2`). Ships 46 candidate conformance vectors in `vectors/`. |
| §5 Identity | Key-id = SHA-256(pubkey)[0:8]; `stream_id` = SHA-256("canticle-stream/v2" ‖ 0 ‖ name)[0:4]; collisions are refused, never rehashed (#38). |
| §7 Carousel | Signs each item once and resends the same bytes. The expiry is absolute and never reset. A burst goes out at 0, +1, +2 and +4 s, then SAP-style loops with jitter U(2/3, 4/3) and reconsideration. Includes the fair-share regulator with a class floor, the availability ceiling and clamp reasons; supersede-by-key; pluck (a PLUCK loops until the target's expiry); refresh re-issue for keep-on-air; and ring depth. |
| §8 Carrier-beacon | Signed beacons with per-stream `head_seq` and `trail_seq` (the lowest seq still on air, `head_seq + 1` when nothing is; amendment A1), live counts, loop and TTL contracts, `next_beacon_ms` (0 = goodbye) and ±10% jitter. A catalog that does not fit one 1 100-byte beacon at its actual encoded size rotates pages with a catalog digest. Each page is chosen from actual encoded sizes: a cyclic sweep sends the longest run of streams from a cursor that fits the frame, and the cursor moves past them. Any page holds at least as many entries as fit with every field at its CDDL maximum, so `count` is fixed at ceil(streams / that many), and every stream appears at least once in every `count` beacons however entries grow or shrink (#71; the argument is in `Station._beacon`); a station refuses a catalog whose `count` would exceed 8 (§8.4). |
| §7.4-§7.8, §8.6 Listener | Dedup on the identity tuple: a repeat is a no-op, different bytes are an equivocation. Also sticky-pluck, supersession high-water marks, epoch regression, class capability, granted scope, binding scope (a `host` frame heard over UDP is a `scope-violation`) and per-class hop limits from the manifest, all checked before any state changes so a rejected frame is state-neutral; safety state (epochs, dedup digests, sticky PLUCKs, high-water marks) persisted atomically and re-loaded at start, by default (the CLI derives a state file and holds a lease on it; `--ephemeral` is an explicit, warned opt-out, and the library requires `state_path` or `ephemeral=True`), and the §7.8 warm-up for live-state keys, per-key dedup quotas that refuse new tuples rather than evict live ones (supersession marks have their own per-key limit, counted apart from dedup entries and scaled by how much longer marks live; presence keeps at most one share of streams; the beacon stream maps hold one advertised catalog, newest copy of a stream winning: #60), the §9.7 check that a PLUCK carries its held target's `expires_at` and `scope` (evidence `pluck-mismatch`), one class per `state_key` within an epoch (a change in the mark's epoch is dropped as `class-change`; §23.2 q21), and local expiry per RFC §14.6.3: clamped to the class max TTL, moved onto the receiver clock by δ̂, and never longer than the full TTL from first hearing (a PLUCK clamps to the largest class max TTL, since it does not carry its target's class). Presence covers ROOT_UNKNOWN, EQUIPPED_QUIET, EQUIPPED_SPEAKING, UNEQUIPPED_PRESENT and UNOBSERVABLE (with a `signed_off` reason). |
| §10.4 Publisher grants | The station signs only the classes, scopes and streams its manifest entry grants, checked before a `seq` is allocated. The control socket has its own grant, narrower than the key's (`--socket-class`), and never accepts `regulatory`, `alarm` or `control`, because their op-level and typed-body checks (§10.4, §15.4) are not implemented here; `host` scope is refused because this station only speaks UDP; one station per key (an exclusive lease on the key file); epochs from a locked, fsynced counter. |
| §11.1-§11.2 Bindings | Host-local submission over a unix socket (mode 0600, peer uid checked); UDP unicast and LAN multicast (`239.255.13.13:9999`, provisional per D22, IP TTL 1, don't-fragment). |
| §11.2, §13.6, §15.7 Onboarding (#73) | `canticle doctor` checks Python, `cryptography` (with an RFC 8032 known answer), `stations.toml`, the manifest and the listener's UDP address, and only reports multicast. `stations.toml` locates the manifest and the listener's address. `canticle manifest verify` and `show` read the unsigned spike-0 manifest; manifests refuse small-order keys (§9.3) and key-ids that do not match their keys (§10.3). |
| §15.8 Background emitter (#58) | `canticle ambient`: paced, short-TTL items from a fixture file through the station's socket, with no model calls, capped cadence and size, and a bounded run. |
| §18.9 Web tuner (#57) | `canticle tuner`: a loopback-only gateway over one listener, and a read-only page to pick a station:stream and watch its live ring, with expiry and gaps shown honestly. |
| §14.18.3 Record v1 (BC-2, #77) | `canticle/records.py`: the listener's outcomes as receptor record v1 (`hello`, `landing_state`, `frame`, `retract`, `presence`, `health`, `fatal`, `bye`) under the disposition mapping, with fixed health counters and a bounded table of unverified key ids (D34). See [Record v1 and the host daemon](#record-v1-and-the-host-daemon-bc-2-d35-77). |
| §11.1, §14.18.2 Host daemon (D35, #77) | `canticle daemon`: the host's one UDP listener, carrying record v1 to every binding over a unix `SOCK_STREAM` socket with peer-credential checks, a two-record bootstrap per connection and per-connection isolation. |
| §14.18.3 Join snapshot (BC-1b, D36, #84) | `canticle daemon` serves the opt-in join snapshot: an atomic cut at watermark *W*, presence and deliverable frames as `snapshot` records (`snap_seq` 1..n, `rec_seq` *W*), `snapshot_end`, the `min(511, free − 513)` and 1 MiB bound, and the deferred cut of #86 (wait until the live state fits, 2 s bound). See [Join snapshot](#join-snapshot-bc-1b-d36-84). |

Not implemented here, and still open work (see RFC-0001 §23.3):
- relay leases for internet listeners (§11.3)
- signed fleet manifests and the genesis pin; the manifest here is plain JSON (§10.3), so `stations.toml` refuses a `[trust]` table
- the daemon's key store (§15.7); keys are files
- typed-body schemas, content policy and taint checks before signing (§15)
- accord (§10.7) and control frames (§10.6)
- the receptor's landing into agent sessions, banners and taint (§14)
- DNS-SD (§13)
- the ringserver bridge (§18; see [`../ringserver-proofs/`](../ringserver-proofs/))
- the capsid (§8.7)
- work-conserving budget redistribution and burst budget accounting (§7.5-§7.6)
- the receiver side of `trail_seq` (§7.10: waiting up to one `loop_max_ms` for a gap at or above it, and relay repair). The station emits it and the listener holds it (amendment A1, #70); nothing acts on it yet.
- IPv6 groups, and the multicast decision of §11.2's doctor (MTU, peer beacons, the 270 s querier check, Wi-Fi and container detection, broadcast fallback, recording the binding, and its exit codes). `canticle doctor` checks the host and only reports multicast.

The decoder is stricter than the RFC in two places: it rejects floats and tags under every key, not only core keys 1-31; and it accepts only integer and text-string map keys at every depth, including extension values (#66), where the RFC says only that the frame map has integer keys.

## Install and onboard

Requires Python 3.11+ and `cryptography>=45`. Run these from the repository root.
[`docs/state-layout.md`](docs/state-layout.md) says where each file lives, and why.

```sh
python3 -m venv ~/.venvs/canticle && . ~/.venvs/canticle/bin/activate
pip install -e prototype/canticle-station

# 1. A station key, added to the fleet manifest.
mkdir -p -m 700 ~/.binary-canticle/keys
canticle keygen --out ~/.binary-canticle/keys/cael.key --manifest ~/.binary-canticle/fleet.json --name cael \
  --classes chatter,live-state,root --streams chatter,lens.threat,root
canticle manifest verify ~/.binary-canticle/fleet.json

# 2. stations.toml: where the manifest is, and where the listener hears.
cat > ~/.binary-canticle/stations.toml <<'EOF'
version = 1

[manifest]
path = "fleet.json"

[listen]
bind = "0.0.0.0:9999"
multicast = false
EOF

# 3. Check the host: exit 0 when every check passes. With multicast = false (as above) it does not touch
#    the multicast group; --probe runs the loopback probe anyway, --no-probe never runs it.
canticle doctor

# 4. Listen: one JSON event per line. No flags are needed now that stations.toml exists.
canticle listen
```

- **`canticle keygen`** writes the seed (mode 0600, never over an existing file) and adds the station's entry,
  with its key-id, to the manifest. A refused or failed command (a bad `--name`, an unknown class, a manifest
  that does not verify or cannot be written) leaves no key and the old manifest as it was.
- **`canticle manifest verify`** checks the manifest's structure, that every key is a well-formed Ed25519
  point and not one of the small-order points RFC §9.3 says to refuse, and that every key-id is
  SHA-256(public key)[0:8] (§10.3). It lists every problem and exits 1 if there is one. The manifest is
  **unsigned** in this spike, and verify says so: whoever can write the file chooses the keys a listener
  trusts. `canticle manifest show` prints each station's key-id, classes, scopes and stream ids, and also
  exits 1 when verify would.
- **`stations.toml`** holds locators only (RFC §13.6); the schema is in
  [`docs/stations-toml.md`](docs/stations-toml.md). An unknown or misspelt key is an error. `listen`,
  `doctor` and `manifest verify|show` read it when they are not given a manifest; `--manifest` works as
  before and skips the file.
- **`canticle doctor`** checks Python, `cryptography` (it must reproduce RFC 8032's TEST 1), `stations.toml`,
  the manifest, and the listener's UDP address, which must be free or held by this listener. `--json` prints
  the same checks for a script. It exits 1 if any check fails; the multicast line never changes the exit status.
- **Multicast is reported, never decided.** RFC §11.2 allows the multicast binding only after a doctor that
  runs all seven of its steps has passed. This one has a loopback probe only: it joins the group on the
  default interface, sends a probe with IP TTL 0 (the probe never leaves this host), and reports whether it
  came back. The join itself sends an IGMP report the LAN can see, so the probe runs only when multicast is
  configured (`multicast = true` in `stations.toml`, or `--multicast`). Otherwise doctor reports
  `multicast not configured — probe skipped` and joins nothing. `--probe` runs the probe anyway;
  `--no-probe` never runs it, even with multicast on. Doctor never turns multicast on and writes no
  configuration, and its exit codes are not §11.2's (0, 10, 20, 30). Setting `multicast = true` is your
  decision.
- **`canticle listen`** prints the `stations.toml` it used on stderr, and keeps its safety state under
  `$XDG_STATE_HOME/canticle`.

A healthy host with the listener running (from a run of these steps on 2026-10-02, paths shortened; the
multicast line is as doctor prints it since #75):

```text
ok      python        Python 3.11.15 (/home/you/.venvs/canticle/bin/python3.11)
ok      cryptography  cryptography 50.0.2; Ed25519 reproduces RFC 8032 TEST 1
ok      stations      /home/you/.binary-canticle/stations.toml: manifest /home/you/.binary-canticle/fleet.json, bind 0.0.0.0:9999, multicast off
ok      manifest      /home/you/.binary-canticle/fleet.json: 1 station(s), 0 revoked; keys well-formed, key ids match. UNSIGNED: [...]
ok      bind          0.0.0.0:9999 is in use by this listener, which holds /home/you/.local/state/canticle/listener-369385c1dd02.json.lease
report  multicast     multicast not configured — probe skipped (--probe runs it anyway); listener multicast off; a report only: [...]
doctor: every check passed (exit 0). Multicast is reported, not decided (RFC §11.2).
```

To run the listener and stations as services, start from the example user units in
[`docs/systemd/`](docs/systemd/). They are documentation only: nothing installs them.

### Put something on air

```sh
canticle station --key ~/.binary-canticle/keys/cael.key --manifest ~/.binary-canticle/fleet.json \
  --stream chatter --stream lens.threat:live-state --stream root:root --to 127.0.0.1:9999 --control ./cael.sock &

canticle sing --control ./cael.sock --stream chatter --text "port-scan burst from 10.0.0.7" --ttl 30
canticle sing --control ./cael.sock --stream lens.threat --state-key now \
  --text "what is now and threat: elevated" --keep-on-air 120
canticle hush --control ./cael.sock --stream chatter --seq 1
canticle status --control ./cael.sock
```

This station sends to the listener on this host. To reach listeners on other hosts, set `multicast = true`
in their `stations.toml` and start the station with `--multicast` instead of `--to`, once you have decided
that multicast is fine on this LAN.

On 2026-09-27 an earlier form of these commands ran as separate processes over multicast on one host, with `--multicast` on the listener and the station. `sing` returned the effective TTL, loop and clamp, for example `{"ok": true, "stream": "chatter", "seq": 1, "ttl_s": 30.0, "loop_ms": 10000, "clamp": "none", "size": 151, ...}`. The listener printed:

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

## Record v1 and the host daemon (BC-2, D35, #77)

```sh
canticle daemon                       # reads stations.toml; socket $XDG_RUNTIME_DIR/canticle/daemon.sock
canticle daemon --manifest fleet.json --bind 0.0.0.0:9999 --socket /run/user/1000/canticle/daemon.sock
```

`canticle daemon` is the standalone host daemon of RFC-0001 §4.2 and §11.1 (amendment BC-1a, D35). It owns
the host's canticle UDP port and carries receptor record v1 (§14.18.3) to every harness binding on the host.
A binding (frond-ear's `host-daemon` source, the OpenClaw P1 plugin) connects to the socket and reads one JSON
record per line.

**The daemon (`canticle/daemon.py`).**

- **One listener.** The UDP port is bound without `SO_REUSEADDR`, so a second daemon, or a `canticle listen`
  (which sets it), fails to bind; `canticle listen` then says so and exits 1. A lease on the state directory
  (`daemon.lease`) stops a second daemon on the same state.
- **Socket.** `SOCK_STREAM`, in a directory of mode 0700 (created if missing; an existing one that is not ours
  or not 0700 is refused) with the socket at 0600. Every connection's `SO_PEERCRED` uid must be in
  `--allow-uid` (default: the daemon's own uid); where `SO_PEERCRED` is unavailable every connection is refused.
  A stale socket file is replaced; one a live daemon answers on is not.
- **Bootstrap.** Connections are accepted only after the run's first `landing_state`. Each opens with the run's
  `hello` and latest `landing_state`, the same bytes with their original `rec_seq`, then the live stream. Taking
  the two and joining the fan-out is one step of the event loop, with nothing awaited between.
- **Isolation.** Each connection has a queue of at most 1 024 records, and the kernel holds at most one more
  line (the transport's write buffer limit is 0). A `frame`, `presence` or `health` record that does not fit
  is dropped for that connection only, and counted (`health.records.dropped`, and `records_lost` in the next
  `health`). A `retract`, `landing_state`, `hello`, `fatal` or `bye` that does not fit, or that the kernel has
  not taken within 2 s, closes that connection only. At most 16 connections; more are refused at accept. The
  receive path only ever appends to queues.
- **Lifecycle.** Start: lease, manifest, state, UDP bind (and the multicast join if configured), then `hello`
  and the first `landing_state`, then the socket. A failure emits `fatal` (`state_locked`, `manifest_invalid`,
  `state_corrupt`, `state_not_durable`, `bind_failed`, `socket_failed`) and exits 1. SIGTERM or SIGINT emits
  `bye`, waits up to 2 s for it to reach each connection, closes them and removes the socket.
- **Durable publish (write-ahead, #79 review).** Each datagram and each tick is one batch. The records it
  implies are held, the safety state is saved (one atomic replace), and only then are the records numbered and
  sent. If the save fails, none of that batch is sent, retracts included, and no `rec_seq` is spent. The run
  then ends: `fatal` with reason `state_not_durable` (an error elsewhere in the record path ends it the same
  way, reason `internal`), up to 2 s for it to reach each connection, then exit 1, with no `bye`. This
  follows the RFC rather than limping on: a receptor's `health.state` is only `ok` or `degraded`
  (§14.18.3), supersession marks MUST persist across restart (§7.8), `fatal` precedes any non-zero exit, and
  the binding's supervision restarts the receptor with backoff after `fatal` (§14.18.2). A binding treats
  `fatal` as receive health `failed` and delivers nothing more from the run, so withholding a retract
  withdraws nothing it would still deliver. The restarted daemon starts from the last saved state and
  reconciles it (below).
- **Output.** Records go only to the socket: `frame` records carry item text (RFC §19.7). `hello`, `fatal` and
  `bye` are copied to stderr.
- **Inbound.** A peer's first line may be a join-snapshot request ([Join snapshot](#join-snapshot-bc-1b-d36-84)). Publishing over the socket
  (sing/hush, §15) is not in this slice: every other line a peer sends is read, counted
  (`health.snapshots.ignored`) and discarded. End of stream from a peer closes its connection (a half-closed
  peer is not supported).

**Record v1 (`canticle/records.py`).** Every record has `v`, `type`, `rec_seq` (from 1, strictly increasing,
never reused) and `run` (128 random bits, hex, chosen at start). Times are integer ms. Lines are ASCII (non-ASCII
escaped), at most 64 KiB and nesting depth 8; a record that would break that is a bug and raises, never sent.
`idem` is `canticle:<key_id hex>:<epoch>:<stream_id as 8 hex digits>:<seq>`; the RFC leaves the radix of
`stream_id` open, and the prototype shows stream ids as 8 hex digits everywhere else.

| Mapping row (§14.18.3) | Emitted |
|---|---|
| new verified item on a named stream | `frame`, `verified`, `surface`, with `body` (New: no tune set under a binding) |
| stream id with no known name | `frame`, `ringbuffer_only`, `unnamed_stream`, with `body` (New) |
| live-state item held in warm-up | `frame`, `ringbuffer_only`, `warmup_hold`; on release a second `frame`, same `idem`, `surface` (New) |
| held item expired, plucked or superseded before release | `retract` `held_expired` / `held_plucked` / `held_superseded` (New) |
| repeat of an accepted tuple | `health` counter (`admission.duplicate`) |
| item re-heard after a restart | `frame` with `dedup: "resurfaced"` |
| PLUCK re-heard after a restart | `retract` for its target if the target was surfaced before the restart, else a counter (New) |
| superseding item after a restart | `retract` `superseded` for a value surfaced before the restart (New) |
| older or repeated beacon | `health` counter (`beacon.duplicate`; a lower-epoch beacon `beacon.epoch_regression`) |
| class or scope beyond the key's grant | `frame`, `capability_exceeded`, `ringbuffer_only`, no body |
| scope narrower than the binding (a `host` frame over UDP) | `frame`, `scope_violation`, `drop`, no body |
| unknown class code | `frame`, `verified`, `ringbuffer_only`, `unknown_class`, with body |
| hop above the class limit | `frame`, `hop_limit`, `drop`, no body |
| lower epoch, new tuple | `frame`, `verified`, `ringbuffer_only`, `epoch_regression`; supersedes and surfaces nothing (New) |
| lower epoch, repeat | `health` counter (`duplicate`) (New) |
| over quota, pluck mismatch, plucked, superseded, class change | `frame`, that result, `drop`, no body |
| equivocation | `frame`, `equivocation`, `quarantine_set`, no body; the key is quarantined locally (persisted), its surfaced tuples get `retract` `quarantined`, and its later items are `ringbuffer_only`, reason `key_quarantined` (New) |
| unverified (`unknown_key`, `bad_signature`, `revoked`, time window, `malformed`, `crit_unknown`, `version`) | `health` counters only, never attributed to a station (New) |
| valid PLUCK; supersession or local expiry of a surfaced tuple | `retract` `plucked` / `superseded` / `expired` |
| key revoked with surfaced tuples | `retract` `revoked`, at start, for tuples surfaced before the restart |

`health` (every 10 s) carries fixed counters per admission result, disposition, retract reason, beacon outcome
and unverified reason; the unverified key ids, at most 16, kept by space-saving (each listed with its `count`
and the `error` it may overcount by, and `other` for what no listed id accounts for); dedup occupancy; beacon age
per manifest key; `last_datagram_at`; records emitted and dropped and connections closed; and `state` `ok` or
`degraded` with `no_datagrams` (none for 30 s), `records_lost` (a connection dropped a record since the last
`health`) or `clock_skew` (a station's δ̂ beyond 5 s). The receptor keeps which tuples it surfaced, and which
keys it quarantined, in the listener's state file (`"receptor"`), written with the listener's guards in one
atomic replace per datagram. At start, after `hello` and before the first `landing_state` (so before any
connection is served), `Receptor.reconcile` retracts every surfaced tuple the persisted guards say is withdrawn:
key revoked or gone (`revoked`), key quarantined (`quarantined`), a sticky PLUCK on it (`plucked`), a newer
supersession mark (`superseded`) or local expiry passed (`expired`). It is idempotent (#79 review).

The listener change is opt-in: `Listener(receptor_mode=True)` reports the outcomes it was silent on and admits
lower-epoch tuples as above. `canticle listen` and `canticle tuner` behave as before.

**Not emitted yet, or emitted differently** (each a known gap, not a silent one):

- `stream_name_ambiguous`: never emitted. The manifest refuses two names for one stream id at load (§5.4).
- Stream grants: the manifest grants no streams yet, so no item is `capability_exceeded` for its stream (as
  the RFC notes for BC-2).
- `landing_state` never changes on its own: there is no MUTE (§10.6), circuit breaker (§14.8.3) or
  modulation (§14.7) here. It is always `mute: null`, `breaker: "closed"`, `modulation: []`;
  `Receptor.set_landing` is the hook, and only tests call it.
- `quarantine_strengthen` / `quarantine_rescind`: reserved in the RFC, not emitted. A local quarantine has no
  rescind here; it lasts until the daemon's state is removed with the daemon stopped.
- Revocation retracts only at start: the daemon does not reload its manifest while running.
- `gap` is always `"unavailable"` (§7.10's receiver side is not implemented); `station.principal` is always
  null (the spike manifest names none).
- `frame.sha256` and `frame.bytes` point at a hearer-ring copy only for a frame that reaches the ring at §14.1
  step 5, that is, admission `verified` (`surface` or `ringbuffer_only`, including `unnamed_stream`,
  `unknown_class`, `warmup_hold` and `epoch_regression`). A frame refused at steps 3-4 has none, and both
  fields are `null`: `capability_exceeded`, `scope_violation`, `hop_limit`, `over_quota`, `pluck_mismatch`,
  `plucked`, `superseded`, `class_change` and `equivocation` (#79 review). This spike keeps no hearer ring
  (§14.4): for a verified frame the two are the hash and size its ring copy would have.
- Fields a frame does not carry are null: a PLUCK's `class`, `hop`, `state_key`, `purpose`, `intensity` and
  `lens`; the `stream` of an unnamed stream; the `class` of an unknown class code; and `frame.sha256` and
  `frame.bytes` of a refused frame (above). frond-ear#34's consumer requires `stream` and `class` strings, an
  integer `hop`, a string `sha256` and an integer `bytes` on every `frame`, so it counts those records as
  `malformed_record` rather than not deliverable. None of them is deliverable either way.
- The stdout child-process transport of §14.18.2 is not a separate command: only the daemon carries records.
- Mixed-host proof cases (4) and (6) need a harness binding and OC-0, and are not run here. Case (1) is shown
  with sockets in one test host (a second daemon and a `canticle listen` both fail to bind), not with `ss`.

### Join snapshot (BC-1b, D36, #84)

A late join is a state transfer (RFC-0001 §14.18.3, *Join snapshot*). `hello` says `join_snapshot: true`. A
binding that wants the run's current state sends, as its first line on the socket and without waiting for
`hello`:

```json
{"op": "join_snapshot", "v": "canticle-receptor-record/1"}
```

- **One per connection, first line only.** Only the first line is read as a request. Any other line, a second
  request included, and a first line that is not exactly this request (another `op`, another `v`, more than
  64 KiB or nesting depth 8), is ignored and counted. A binding that does not ask receives exactly the stream
  of *Joining a run*, and stays `joined_late`.
- **The cut** is one synchronous step of the event loop, with no receive-path work between: the watermark *W*
  is the run's last `rec_seq` (records dropped for any connection included); the entries are captured; and
  they are queued behind whatever the connection already holds, all of it at or below *W*. The connection
  reads `hello`, `landing_state`, any live records up to *W*, the `snapshot` records, `snapshot_end`, then live
  records from *W* + 1. A `retract`, PLUCK, expiry or presence change after the cut is a live record above *W*.
- **Content.** First one `presence` entry per station with a presence state this run (its latest `presence`
  record's fields, by key id); then one `frame` entry per tuple for which this run emitted a deliverable
  `frame` record (`verified`, `surface`) and no `retract`, whose `local_expiry_at` has not passed: alarm class
  first, then newest `heard_at` first. A frame entry is that record's fields as emitted, without `v`, `type`,
  `rec_seq` and `run`, `dedup` included. Held (`warmup_hold`) and other non-deliverable items are not entries,
  and neither is a tuple surfaced before a restart and not heard since (this run emitted no record for it).
- **Records.** `{"type": "snapshot", "rec_seq": W, "snap_seq": n, "entry": {"presence": {...}}}` or
  `{"entry": {"frame": {...}}}`; then `{"type": "snapshot_end", "rec_seq": W, "watermark": W, "count": n,
  "truncated": bool, "omitted": k}`. `omitted` is always present (0 when the snapshot is complete).
- **Bound.** At most `min(511, free − 513)` entries, `free` being the connection's free queue slots at the cut,
  and 1 MiB of `snapshot` lines; entries beyond either cap, in the order above, are omitted and `snapshot_end`
  says `truncated: true`. So the entries, `snapshot_end` and a 512-slot live-tail reserve always fit the 1 024
  queue: 511 entries on an empty queue, none (only `snapshot_end`) at exactly 513 free.
- **When the cut is taken (#86).** With *N* = `min(511, live entries)`, the cut is taken as soon as
  `free − 513 ≥ N`: at once on an idle connection. Otherwise it is deferred, and live records keep flowing,
  until the connection has drained that far; *W* and the entries are taken then, so a deferred snapshot
  carries all *N* entries. The deferral is bounded at 2 s. At the bound the cut is taken with what fits
  (`truncated` when fewer than *N*, and the binding stays `joined_late`) only if there is room for at least one
  entry beyond `snapshot_end` and the reserve: 514 free slots, or 513 when nothing is live. Otherwise the
  connection is closed as stalled. A snapshot carries no entries only when nothing is live.
- **Never dropped.** `snapshot` and `snapshot_end` count against the queue and are never dropped; one the kernel
  has not taken within 2 s closes the connection, as a `retract` would. No other connection waits on it.
- **Counters.** `health.snapshots`: `requested`, `served`, `truncated`, `deferred`, `closed` (the connection
  ended before its snapshot was written, or its deferral ran out) and `ignored` (inbound lines not served).

## Tests

```sh
python -m unittest discover -s tests      # 234 tests, about 25 s
python -m canticle vectors                # regenerate vectors/frame-v2-candidates.json
```

CI (`.github/workflows/tests.yml`, job `station-tests`) runs the same suite from the repository root with `PYTHONPATH=prototype/canticle-station`, on dependencies locked by hash in `.github/ci/`.

- `test_wire.py` covers:
  - strict CBOR, including RFC 8949 core map-key order checked against bytes from an independent encoder (fxamacker/cbor), and the RFC §9.13 vectors byte for byte;
  - the RFC §9.11 size budget (745 / 720 / 1 100 B);
  - all 46 candidate vectors;
  - a check that the committed vectors file equals the generator's output;
  - a 20 000-case fuzz run (random bytes and mutations of valid frames) in which nothing but a `Reject` ever escapes.
- `test_station.py` drives the carousel on a virtual clock:
  - burst timing, byte-identical repeats, jitter bounds and stopping before expiry;
  - the regulator's fair share, class floor and degraded shedding;
  - supersede, pluck (including a late pluck that must never be shed, a PLUCK that depth never evicts, and a refused hush that must change nothing) and refresh re-issue (which keeps provenance flags), and one class per state_key within an epoch (a change is refused before a seq is used, and a key is forgotten once no receiver can hold its mark, so the table stays bounded);
  - depth, stream-id collisions and beacon pages (including the #71 shrink repro, a growth repro, and a property test that every window of `count` beacons carries every stream, under growth and shrinkage, with every paged beacon the actual-size run from the cursor);
  - a late joiner hearing every live item within `loop_ms × 4/3`;
  - the persisted epoch counter: strictly increasing across same-second restarts and a clock that steps back.
- `test_listener.py` covers the presence state machine, local expiry, the §14.6.3 clock rule (including a station clock an hour behind), state-neutral capability rejection, per-key dedup quotas, the #60 per-key bounds (admitted-only stream hearing, one catalog of beacon stream maps with the newest copy winning, a separate mark limit that still fits honest state_key churn at the §7.4 floor, mark horizons that never shrink under mixed classes, stay bounded whatever the clock offset, tolerate a later rise in δ̂ and are not held open by refused older items, purges that pop only what expires, the resurface path's mark check, a plucked newer value that still supersedes, a plucked older item reported as plucked, refusals that do not advance the epoch, sticky PLUCKs timed on the current δ̂, a class change in the mark's epoch dropped as `class-change` while a new epoch may change it, marks persisting their class, PLUCK expiry clamp and target match, state v3 (marks carry their class, learned on resurface from older state) with v1 and v2 still loading), garbage input and station restarts (a new epoch's beacons count from 1 again; two starts in one second never reuse an identity tuple).
- `test_udp_e2e.py` runs a real station and listener over loopback UDP and the unix control socket: sing, listen, hush, status and goodbye.
- `test_manifest.py` covers the manifest checks and the commands that write or read it:
  - the eight small-order points and malformed encodings refused by the key check, by `Manifest` (what the listener loads) and by `manifest verify`;
  - key-ids: written by `keygen`, optional on read, and refused by verify and by the listener when they do not match the key;
  - every problem `manifest verify` reports, its text and JSON output and exit status, `manifest show`, and the manifest path taken from `stations.toml`;
  - names and stream names with a trailing newline, which `$` used to let through;
  - `keygen` refusals and failed manifest writes that leave no key file behind and the old manifest as it was, a manifest's mode and symlink kept, and a second key under one name (a rotation, §10.3).
- `test_stations.py` covers `stations.toml`: a full file, defaults, paths relative to the file and to `~`, a missing file, malformed TOML, wrong types and values, unknown keys, the refused `[trust]` table, and which locators `listen` uses (the file, flags over the file, `--manifest` skipping it).
- `test_doctor.py` covers each check's pass and fail paths: Python and `cryptography` versions, the RFC 8032 known answer, the manifest, and the address (free, held by another socket, held by this listener or tuner through its lease, or by a listener with its own `--state`). Multicast stays a report whatever the probe finds, the probe datagram has IP TTL 0, the probe joins the group only when multicast is configured or `--probe` is given (`--no-probe` always wins; a socket spy records the join and never makes it), doctor writes nothing, its bind probe never shares a listener's port, and a listener starting during its lease probe waits instead of refusing.
- `test_onboarding.py` runs the onboarding above end to end: `keygen`, `stations.toml`, `doctor`, then `canticle listen` with no flags in a subprocess hearing a station's item over loopback UDP while doctor sees it holding the address.
- `test_ambient.py` runs the emitter on a virtual clock: tick gaps, breaths and repeats, exact requests, the per-minute cap, stop by signal and by duration, refusals, an unreachable station, bounds and fixture loading.
- `test_records.py` covers record v1 row by row: the envelope (`hello` then `landing_state`, `rec_seq`, `run`,
  framing limits), every mapping row above including the BC-2 "New" rows (surface, `unnamed_stream`,
  `warmup_hold` and its release under the same `idem`, the three `held_*` retractions, lower epochs, local
  quarantine on equivocation), retractions on pluck, supersession and expiry, the restart rows (resurfaced
  items, a re-heard PLUCK, supersession and expiry of tuples surfaced before the restart, revocation at start,
  quarantine kept), the start-time reconcile (the #79 crash window: a PLUCK or a supersession mark persisted
  without its retract, with no replay, is retracted at start before the first `landing_state`; also a
  quarantined key, expiry while down, and one state file written once), write-ahead publishing (a failed save
  sends nothing, spends no `rec_seq` and ends the receptor, at start, on a datagram and on a tick; a restart
  without replay owes nothing), null receipt pointers on every pre-ring refusal, presence and beacon counters, unverified counters that never name a station, a 2 000-datagram
  flood of key ids that keeps the table at 16 and the `health` record the same size, and the `health` states.
- `test_daemon.py` runs the daemon in one event loop over loopback UDP and a unix socket in a temporary
  directory, for the local mixed-host proof cases of §14.18.2:
  - (1) a second daemon on the same state refuses (`state_locked`); a second daemon on the port, the embedded
    listener and a `canticle listen` subprocess all fail to bind it;
  - (2) two bindings receive byte-identical streams for a station's carousel;
  - (3) one binding leaving and rejoining leaves the other's stream equal to everything the daemon emitted, with
    no gap, and the rejoin gets the same bootstrap;
  - (5) a late join: `hello` 1, `landing_state` 50, connect at 99, and the joiner receives 1, 50, 100... byte for
    byte as the first binding did;
  - (7) a peer that never reads, while the healthy one receives `frame`, `retract` and `landing_state` in order,
    within a second and with no gap: closed at once when its full queue cannot take the `retract`, or after the
    2 s bound when the queue has room but the kernel does not; its queue and write buffer stay within bounds and
    the daemon keeps receiving datagrams;
  - a failed save with a connected peer: the peer receives `fatal` (`state_not_durable`) and end of stream,
    never the frame; the daemon exits 1, and the restarted daemon, with no replay, owes nothing, and hears the
    item as new when it comes again;
  - socket and directory modes, a refused peer uid, the peer limit, bytes from a peer ignored, `bye` and end of
    stream on a clean stop, a live socket not taken over and a loose socket directory refused.
- `test_join_snapshot.py` runs proof case (5) with a join snapshot (BC-1b, D36), daemon side, with a binding's
  validation and view-application model in the test:
  - (a) `hello` 1, `landing_state` 50, I1 at 60, S's presence at 70, a held item, I2 at 80 plucked at 90, B asks
    at 99: B gets 1, 50, S's presence and I1 (byte-equal to the records A saw, minus the envelope), no I2 and no
    held item, `snapshot_end` *W* 99, then the same live records as A from 100;
  - (b) a PLUCK and a new item in the same event-loop step right after the cut each arrive once, after
    `snapshot_end`, from *W* + 1; a PLUCK before the cut, and a local expiry passed at the cut whose tick runs
    after it, leave no plucked or expired item in the snapshot;
  - (c) entries keep `idem` and `dedup` as emitted (`resurfaced` after a restart); a tuple restored from state
    but not heard this run is not an entry;
  - (d) 600 live items and an alarm on an empty queue: 511 entries, presence then the alarm then newest first,
    `truncated`, `omitted` 91; the 1 MiB cap (scaled down) truncates; a truncated snapshot merges;
  - (e) a binding that asks and never reads is closed within the 2 s bound mid-snapshot, A's stream is every
    record the daemon emitted, the queue stays within 1 024, and the daemon keeps receiving;
  - (f) two bindings joining at different points converge on A's surfaced set and presence;
  - (g) a binding that does not ask gets the case (5) stream and sees neither item nor presence;
  - (h) 100 live records queued and 50 live: cut at once, all 50, *W* above the last queued record; 512 queued
    and 40 live: deferred, cut as soon as `free − 513 ≥ 40` (never at 513), all 40 untruncated; at the 2 s bound
    between 513 and 513 + *N* free (stalled there, or drained part way from below 513): cut with `free − 513`
    entries, truncated (514 free: one entry); exactly 513 free at the bound with anything live: closed; below
    513: closed; nothing live and 512 queued: cut once drained to 513 free, `count` 0, not truncated;
  - one request per connection, first line only: a second request, a junk first line, an over-long first line
    and a wrong `v` are ignored and counted; an error at the cut closes that connection only.
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
- 34 parse-level cases (datagram → `accept` or a rejection reason);
- 14 listener-level sequences (datagrams → events). Two are timed: with optional `at_ms`, time advances to `at_ms[i]` (local expiry applied, its events not listed) before datagram `i` is heard; `per_key_quota` and `per_key_mark_quota` fix the listener's per-key limits for dedup entries and for supersession marks, counted separately (§7.4).

It covers the #48 acceptance set (valid, wrong key, tampered, unknown key, revoked, expired, replayed) and every case RFC-0001 §9.13 lists: repeat-as-no-op, equivocation, non-deterministic CBOR, `crit`-unknown, a 1 101-byte frame, a depth bomb, a float in a core key, a future `issued_at` and pluck-before-original. The #60 sequences pin a PLUCK whose `expires_at` differs from its held target's, a far-future PLUCK that holds its dedup slot for one day at most, and supersession marks held to their own per-key limit. The §23.2 q21 sequences pin a class change in one epoch, newer or older (dropped as `class-change`, which outranks `superseded`), and one across epochs (allowed). It also includes a regression for the prototype's bug B1 (the 11-byte `{"a":1e400}`). The #66 cases pin the map-key rule (a `false`, `null` or byte-string key inside an extension value, and `true` where key 1 belongs, all `bad-cbor`) and the null rule (an ITEM with `8: null` and no `9`, and a BEACON with `9: null`, both `bad-field`: an optional key that is present must be well-typed, so absence and null are not two encodings of one frame). The A1 cases (#70) pin the post-A1 `stream-entry` of §9.8: `valid-beacon` and `beacon-null-catalog-digest` carry the 9-element entry with `trail_seq`, `beacon-entry-with-lens` the 10-element one, a pre-A1 8-element entry is `bad-field` (it would otherwise be read with every field after `head_seq` shifted), and `b_stream = 2^60` is `bad-field` (`uint .size 4` in the CDDL, #66 case 4). The #72 cases pin the receiver rule of §9.8: `beacon-trail-seq-empty-window` (`trail_seq = head_seq + 1`, nothing on air) is accepted, and `beacon-trail-seq-over-head-plus-one` (`head_seq + 2`) is `bad-field`.

Keys are the RFC 8032 §7.1 test keys. The vectors are **candidates**: they become normative when a second, independent implementation (for example the TypeScript codec planned in S1) reproduces them.
