# canticle-station (spike)

A runnable spike of [RFC-0001](../../rfc/0001-binary-canticle.md) work items
S1 and S2. It implements the frame v2 codec, a looping station and a
listener, which is enough to put TTL items on a `station:stream` and hear
them loop until they expire.

| RFC-0001 | What this spike implements |
|---|---|
| §9 Wire format v2 | `BC` magic, version, kind and key-id header; deterministic CBOR with integer keys; a domain-separated Ed25519 trailer; the ITEM, PLUCK and BEACON key tables; the 1 100 B frame and 1 200 B datagram limits; `crit` and unknown-key handling. |
| §9.4 Strict parsing | A bounded, strict CBOR decoder (definite lengths, shortest form, sorted and unique keys, depth ≤ 4, ≤ 32 entries, no floats or tags). A bad datagram only ever produces a rejection with a reason. |
| §9.13 Test vectors | Reproduces the RFC's two illustrative vectors byte for byte, using an independent encoder (not `cbor2`). Ships 31 candidate conformance vectors in `vectors/`. |
| §5 Identity | Key-id = SHA-256(pubkey)[0:8]; `stream_id` = SHA-256("canticle-stream/v2" ‖ 0 ‖ name)[0:4]; collisions are refused, never rehashed (#38). |
| §7 Carousel | Signs each item once and resends the same bytes. The expiry is absolute and never reset. A burst goes out at 0, +1, +2 and +4 s, then SAP-style loops with jitter U(2/3, 4/3) and reconsideration. Includes the fair-share regulator with a class floor, the availability ceiling and clamp reasons; supersede-by-key; pluck (a PLUCK loops until the target's expiry); refresh re-issue for keep-on-air; and ring depth. |
| §8 Carrier-beacon | Signed beacons with per-stream heads, live counts, loop and TTL contracts, `next_beacon_ms` (0 = goodbye) and ±10% jitter. Beyond 24 streams it rotates pages with a catalog digest. |
| §7.4-§7.8, §8.6 Listener | Dedup on the identity tuple: a repeat is a no-op, different bytes are an equivocation. Also sticky-pluck, supersession high-water marks, epoch regression, class capability from the manifest, local expiry clamped to the class max TTL, and δ̂ clock offset that only ever makes expiry earlier. Presence covers ROOT_UNKNOWN, EQUIPPED_QUIET, EQUIPPED_SPEAKING, UNEQUIPPED_PRESENT and UNOBSERVABLE (with a `signed_off` reason). |
| §11.1-§11.2 Bindings | Host-local submission over a unix socket (mode 0600, peer uid checked); UDP unicast and LAN multicast (`239.255.13.13:9999`, provisional per D22, IP TTL 1, don't-fragment). |

Not implemented here, and still open work (see RFC-0001 §23.3):
- relay leases for internet listeners (§11.3)
- signed fleet manifests; the manifest here is plain JSON (§10.3)
- accord (§10.7) and control frames (§10.6)
- the receptor's landing into agent sessions, banners and taint (§14)
- DNS-SD (§13)
- the ringserver bridge (§18; see [`../ringserver-proofs/`](../ringserver-proofs/))
- the capsid (§8.7)
- work-conserving budget redistribution and burst budget accounting (§7.5-§7.6)
- IPv6 groups and `canticle doctor`

The decoder is stricter than the RFC in one place: it rejects floats and tags under every key, not only core keys 1-31.

## Try it

Requires Python 3.11+ and `cryptography>=45`.

```sh
cd prototype/canticle-station
python3 -m venv .venv && . .venv/bin/activate && pip install -e .

canticle keygen --out cael.key --manifest fleet.json --name cael \
  --classes chatter,live-state,root --streams chatter,lens.threat,root

canticle listen --manifest fleet.json --bind 0.0.0.0:9999 --multicast &      # one JSON event per line
canticle station --key cael.key --stream chatter --stream lens.threat:live-state --stream root:root \
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

### From an agent harness

- **Claude Code.** Run `canticle listen …` as a background command under the Monitor tool: each line becomes an event the session sees. Put items on air with `canticle sing` through Bash.
- **OpenClaw.** Call `canticle sing` from an exec tool.

Do not pipe heard text straight into a session. RFC-0001 §14 and §16 require a banner outside the external-content wrapper, taint after hearing, and receiver-local wake policy. That landing layer is work item S3.

## Tests

```sh
python -m unittest discover -s tests      # 28 tests, about 6 s
python -m canticle vectors                # regenerate vectors/frame-v2-candidates.json
```

- `test_wire.py` covers:
  - strict CBOR, and the RFC §9.13 vectors byte for byte;
  - the RFC §9.11 size budget (745 / 720 / 1 100 B);
  - all 31 candidate vectors;
  - a check that the committed vectors file equals the generator's output;
  - a 20 000-case fuzz run (random bytes and mutations of valid frames) in which nothing but a `Reject` ever escapes.
- `test_station.py` drives the carousel on a virtual clock:
  - burst timing, byte-identical repeats, jitter bounds and stopping before expiry;
  - the regulator's fair share, class floor and degraded shedding;
  - supersede, pluck (including a late pluck that must never be shed) and refresh re-issue;
  - depth, stream-id collisions and beacon pages;
  - a late joiner hearing every live item within `loop_ms × 4/3`.
- `test_listener.py` covers the presence state machine, local expiry, the clock-offset rule and garbage input.
- `test_udp_e2e.py` runs a real station and listener over loopback UDP and the unix control socket: sing, listen, hush, status and goodbye.

## Vectors

[`vectors/frame-v2-candidates.json`](vectors/frame-v2-candidates.json) contains:
- 23 parse-level cases (datagram → `accept` or a rejection reason);
- 8 listener-level sequences (datagrams → events).

It covers the #48 acceptance set (valid, wrong key, tampered, unknown key, revoked, expired, replayed) and every case RFC-0001 §9.13 lists: repeat-as-no-op, equivocation, non-deterministic CBOR, `crit`-unknown, a 1 101-byte frame, a depth bomb, a float in a core key, a future `issued_at` and pluck-before-original. It also includes a regression for the prototype's bug B1 (the 11-byte `{"a":1e400}`).

Keys are the RFC 8032 §7.1 test keys. The vectors are **candidates**: they become normative when a second, independent implementation (for example the TypeScript codec planned in S1) reproduces them.
