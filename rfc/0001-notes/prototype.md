# Prototype review: `binary-canticle/prototype/ringserver-udp-cue/`

Reviewer: prototype reader (workflow sub-agent), 2026-09-27. Repo `/home/user/binary-canticle` at `b46a45a` (main).
Every file in the prototype was read in full (1,173 lines across 14 files, plus `prototype/README.md`).

Labels used below:
- **[SAYS]**: what a source document or README claims.
- **[IMPL]**: what the code actually does, verified by reading it and/or running it.
- **[ASSESS]**: my own judgment.

Scratch evidence (all under `<review-sandbox>/`):
- `proto-run/`: the copied prototype that the tests were run against.
- `venv/`: pytest plus the editable install.
- `probe/probe1.py`, `probe/probe2.py`, `probe/probe3.py`: bug probes.
- `probe/cli.log`: the crash trace from the live CLI.
- `rs/ringserver/ringserver`: EarthScope ringserver 4.5.4 built from source.
- `venv-dali/`: simpledali 0.8.3 and simplemseed 1.0.2.
- `dlproof/proof.py`, `dlproof/proof.out`, `dlproof/rs.log`: native DataLink proof.
- `dlproof/sl_data.py`: SeedLink v4/v3 probe.
- `pipdl-seis/`: downloaded wheels.

---

## 0. Provenance and status

- [IMPL] The code landed on main as `65e6705` ("proto: add localhost UDP cue receptor (#49)", author Elliott, 2026-07-25). It added the 14 files under `prototype/` (1,173 insertions).
- [IMPL] PR #50 (`prototype/ringserver-seedlink-udp`, head `54fce69`, base `8498d8a`) is **still open and unmerged**, but its code is byte-identical to main. I compared sha1 for all 8 modules; every one reported `same`.
  - PR #50 uses a root-level layout: `canticle_receptor/`, `tests/`, `pyproject.toml`.
  - It adds `PROTOTYPE-NOTES.md` (on main this became `prototype/ringserver-udp-cue/README.md`).
  - It also adds two lane files: `.lane-workorder-ringserver-seedlink-udp.md` and `.codeagent-outcome-ringserver-seedlink-udp.md`.
  - Outcome: PR #50 is redundant. It can be closed as superseded by 65e6705. That is a recommendation; I did not act on GitHub.
- [SAYS] Issue #49 (open) says it "closes" via PR #50, and names the remaining gate: a native Ringserver/DataLink writer/reader proof. Its body still points to `PROTOTYPE-NOTES.md`, which does not exist on main. That is doc drift.
  - The issue comment (2026-07-26) confirms the code is on main at 65e6705 with 15/15 tests passing.
- [SAYS] The **lane workorder** (PR #50 branch, `.lane-workorder-ringserver-seedlink-udp.md`) explains why the prototype looks the way it does. It was written by a code agent to turn "Silas's research memo" boundary into code. Its constraints were explicit:
  - "notices must never carry raw Tier-1 objects, filesystem paths, bearer values, download/retrieval routes, or transcripts"
  - "Do not implement raw-object replication, artifact fetch, … remote listener/proxy trust, FEC, or general delivery guarantees"
  - [ASSESS] So the prototype is a deliberately **content-free, security-first "doorbell/cue" receptor**. It is not a chatter broadcaster. That scope choice is the main reason it diverges from the owner's intent (see §7).

## 1. Test run (exact output)

Setup:
- The prototype was copied to `scratchpad/proto-run/`.
- The venv `scratchpad/venv` was used (Python 3.11.15, cryptography 50.0.1). It pre-existed from an earlier attempt, and I reused it.
- Install command: `pip install pytest -e proto-run` gave `binary-canticle-receptor-0.1.0`, `pytest-9.1.1`. PyPI was reachable.

`python -m pytest -v tests` (cwd `proto-run`):

```
platform linux -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
rootdir: .../scratchpad/proto-run   configfile: pyproject.toml
collected 15 items
tests/test_receptor.py::ReceptorTest::test_accepts_valid_notice_and_hands_verified_type_to_publisher PASSED
tests/test_receptor.py::ReceptorTest::test_closed_schema_rejects_payload_fields_without_echoing_them PASSED
tests/test_receptor.py::ReceptorTest::test_encoding_is_deterministic PASSED
tests/test_receptor.py::ReceptorTest::test_quarantines_policy_blocked_unknown_issuer_and_unknown_key PASSED
tests/test_receptor.py::ReceptorTest::test_quarantines_publisher_failure_without_retrying_claim PASSED
tests/test_receptor.py::ReceptorTest::test_quarantines_when_bounded_state_caches_are_full PASSED
tests/test_receptor.py::ReceptorTest::test_rejects_expired_and_excessive_ttl_notices PASSED
tests/test_receptor.py::ReceptorTest::test_rejects_invalid_and_future_timestamp_windows PASSED
tests/test_receptor.py::ReceptorTest::test_rejects_invalid_signature_without_publishing PASSED
tests/test_receptor.py::ReceptorTest::test_rejects_oversized_malformed_and_noncanonical_packets PASSED
tests/test_receptor.py::ReceptorTest::test_rejects_replay PASSED
tests/test_receptor.py::ReceptorTest::test_replay_dedup_survives_receptor_restart PASSED
tests/test_receptor.py::ReceptorTest::test_tombstone_blocks_later_notice_for_subject PASSED
tests/test_udp.py::UdpListenerTest::test_listener_refuses_non_loopback_bind PASSED
tests/test_udp.py::UdpListenerTest::test_localhost_datagram_reaches_private_publisher_seam PASSED
============================== 15 passed in 0.11s ==============================
```

The documented command, `python -m unittest discover -s tests -v`, printed `Ran 15 tests in 0.072s` and `OK`.

System Python without the venv (`/usr/local/bin/python3`, dist-packages cryptography 41.0.7) gave `Ran 2 tests … FAILED (errors=2)`. The cause is that importing `cryptography` itself panics (`pyo3_runtime.PanicException: Python API call failed`). The system package is broken, and it is also below the `cryptography>=45` pin in `pyproject.toml:9`. The venv route is required.

## 2. Architecture, end to end [IMPL]

```
sender (library only: codec.encode_signed_notice)      <-- no sender CLI, no keygen tool
   | one UDP datagram, canonical JSON, <=1200 B
   v
UdpCueListener (udp.py)  bind 127.0.0.0/8 IPv4 only; recvfrom(1201); peer addr discarded (udp.py:43)
   v
NoticeReceptor.process (receptor.py:47-96)   single-threaded, synchronous, one packet at a time
   1 parse_packet (codec.py:121-195): size<=1200 -> strict UTF-8 JSON (dup keys, NaN/Inf literals rejected)
     -> must be dict AND byte-equal to its canonical re-encoding -> closed field sets -> regex/type checks
     -> signature must be strict unpadded base64url of exactly 64 bytes
   2 issuer policy (receptor.py:53-60): unknown issuer / quarantined issuer / unknown key_id -> QUARANTINE
     (this runs BEFORE signature verification)
   3 Ed25519 verify over canonical JSON of {issuer,key_id,notice,version} (receptor.py:61-64)
   4 time window (receptor.py:66-75): expires>issued; ttl<=60s; issued<=now+5s; expires>now
   5 ReceptorState.claim (state.py:55-108), SQLite BEGIN IMMEDIATE:
       purge expired replay rows -> replay? -> subject tombstoned? -> replay cache full? ->
       (tombstone kind: tombstone cache full? insert tombstone) -> insert replay row -> COMMIT
   6 publisher.publish(VerifiedNotice) (receptor.py:87-95): PublisherUnavailable -> QUARANTINE
     (the claim is already committed, so the notice is burned: "at-most-once attempt")
   v
Receipt: AcceptReceipt | RejectReceipt(reason) | QuarantineReceipt(reason)   (model.py:52-69)
   -> the CLI prints "decision reason" to stdout (__main__.py:52-63); nothing goes back to the sender
```

- The CLI (`__main__.py`) wires **exactly one issuer and one key** (`--issuer --key-id --public-key-hex`). It uses a `_ReceiptOnlyPublisher` that discards the notice (`__main__.py:14-16`).
- There is no config file, no key rotation, and no hot reload.
- Package startup hard-requires `cryptography`, imported at module level in `codec.py:10`, `receptor.py:7-8` and `__main__.py:6`. [SAYS] The README describes this as "no insecure fallback" (README:46-48). That claim is correct.

## 3. Exact wire format of a cue datagram [IMPL: codec.py]

**Encoding.** One UDP datagram carrying **canonical JSON**, produced by `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=True, allow_nan=False)` (codec.py:44-51).
- There is no binary framing, no magic number, no length prefix and no CBOR.
- Keys appear in sorted order. The top-level order is `issuer, key_id, notice, signature, version`. Inside `notice` the order is `expires_at, issued_at, kind, notice_id, subject`.
- Whitespace-free, and must be **byte-identical** to its re-canonicalization (codec.py:135), or it is rejected as `non_canonical_packet`.

Example (359 bytes; issuer `issuer-a`, key_id `key-a`, 10-digit epoch seconds):

```
{"issuer":"issuer-a","key_id":"key-a","notice":{"expires_at":2000000030,"issued_at":2000000000,"kind":"available","notice_id":"11111111111111111111111111111111","subject":"sha256:aaaa…(64 hex)"},"signature":"jSSHpILWT9…(86 chars)","version":1}
```

| Byte offset (example) | Field | JSON type | Constraint (codec.py line) | Size on wire |
|---|---|---|---|---|
| 0 | `{` | – | – | 1 |
| 1 | `"issuer":` | string | `[a-z][a-z0-9.-]{0,62}` (18, 146-154) | 1–63 chars + 11 B key/quotes |
| 21 | `"key_id":` | string | same regex (18) | 1–63 chars + 11 B |
| 38 | `"notice":{` | object | exactly 5 keys (22, 155-156); canonical size ≤512 (15, 157-158) | 181–216 B in practice |
| 48 | `"expires_at":` | int | JSON int, `type is int` (not bool/float), 0 ≤ x ≤ 2^63-1, epoch **seconds** (172-178) | 1–19 digits |
| 72 | `"issued_at":` | int | same as expires_at | 1–19 digits |
| 95 | `"kind":` | string | `available` or `tombstone` (model.py:8-10; codec 166-167) | 9 chars (both values) |
| 114 | `"notice_id":` | string | `[0-9a-f]{32}` (19), i.e. 128-bit lowercase hex; replay key | 32 chars |
| 161 | `"subject":` | string | `sha256:[0-9a-f]{64}` (20); the *only* "content" | 71 chars |
| 246 | `"signature":` | string | unpadded base64url, exactly 86 chars, decodes to 64 bytes, round-trip canonical so no non-zero trailing bits (71-80) | 86 chars |
| 347 | `"version":` | int | `type is int` and `== 1` (16, 139-140) | 1 digit |

**Size.**
- Total length = `326 + len(issuer) + len(key_id) + digits(issued_at) + digits(expires_at)`. Verified: 359 = 326+8+5+10+10.
- **Minimum valid = 330 B. Maximum valid = 490 B.** I computed both with `probe1.py` (63-char ids and 19-digit ints).
- `MAX_PACKET_SIZE = 1200` (codec.py:14) and `MAX_NOTICE_SIZE = 512` (codec.py:15) therefore never bind for a schema-valid packet. The largest possible canonical notice is 216 B. The notice-size checks at codec.py:114-115 and :157-158 are unreachable.
- The listener reads `recvfrom(1201)` (udp.py:43). A larger datagram is truncated by the kernel to 1201 B and then rejected as `packet_too_large`.

**Signing / MAC.**
- The algorithm is **Ed25519**, via `cryptography`'s `Ed25519PrivateKey.sign` / `Ed25519PublicKey.verify` (codec.py:112, receptor.py:62). There is no MAC or HMAC.
- Signed bytes = `canonical_json({"issuer","key_id","notice","version"})`, i.e. the packet minus the `signature` member (codec.py:93-99, 109-110). The receiver **recomputes** those bytes from the parsed typed values (codec.py:188-194) rather than slicing them from the input.
- There is no domain-separation or context string.
- Tampering with any field gives `invalid_signature`. I checked this: a tampered subject was rejected with `invalid_signature` (probe3).

**Key handling.**
- The receiver holds a static in-memory map `issuer -> IssuerPolicy(keys={key_id: Ed25519PublicKey}, quarantined: bool)` (receptor.py:27-31).
- The CLI accepts one 32-byte raw public key as 64 hex characters (`__main__.py:35-41`).
- There is no private-key storage, keygen, rotation, revocation list, or fingerprint binding of key_id to key.
- The sender must hold an `Ed25519PrivateKey` object in-process.

**Replay / nonce protection.**
- `notice_id` (128-bit, sender-chosen) is the replay key. It is stored in SQLite `seen_notices(notice_id PK, retain_until)` with `retain_until = expires_at + 86_400` (state.py:32-40, 97-103).
- The store is persistent and survives restart (tested).
- It is bounded to 10,000 rows (state.py:23, 75-80). When full, the receptor fails **closed** with `quarantine/replay_cache_full`.
- The namespace is **global, not per-issuer** (state.py:35-38; see bug B6).
- There is no per-stream sequence number.
- A duplicate of the same notice is `reject/replay` (not a no-op).

**TTL handling.**
- TTL = `expires_at - issued_at` in whole seconds.
- Rules: it must be > 0 (`invalid_timestamp`) and ≤ 60 (`ttl_exceeded`); `issued_at` ≤ now+5 (`not_yet_valid`); `expires_at` > now (`expired`) (receptor.py:23-24, 66-75).
- Boundaries TTL=60 and skew=+5 are both accepted; I verified this in probe1, and the suite does not test it.
- The clock is `time.time` (wall clock), truncated to int.
- TTL is used only as an admission window. **Nothing loops, re-broadcasts, or expires items after admission.** No store of live notices exists apart from the replay table.

**Tombstones.**
- `kind=tombstone` inserts `subject_tombstones(subject PK, notice_id, created_at)` (state.py:41-49, 82-95).
- Every later notice for that subject, from *any* issuer, is rejected with `subject_tombstoned`, **forever**. No expiry or GC path exists anywhere in the code.
- The table is capped at 10,000, after which the receptor fails closed with `tombstone_cache_full`.

## 4. The "private Ringserver/DataLink seam" [IMPL + new runtime evidence]

- [IMPL] `_publisher.py` (16 lines) is only:
  - `class PublisherUnavailable(Exception)`
  - `class DataLinkPublisher(typing.Protocol)` with one method, `publish(self, notice: VerifiedNotice) -> None`
- "Private" means the leading underscore in the module name. There is no socket code, no DataLink framing, and no ringserver client.
- The only implementations are:
  - `_ReceiptOnlyPublisher` (`__main__.py:14-16`), which does `del notice`.
  - Test doubles `RecordingPublisher` and `UnavailablePublisher` (tests).
- **Nothing in the package speaks DataLink, SeedLink or miniSEED.** [SAYS] The README says as much (README:77-79, 81-87).
- [SAYS→verified] The "native verdict" (README:3-29) matches the ringserver source. I shallow-cloned `EarthScope/ringserver` tag v4.5.4 (commit `2df558cdb480489dcdddf740ae8724076db20db3`) and confirmed:
  - `README.md:3-5`: "all TCP-based: DataLink, SeedLink and HTTP/WebSocket".
  - `README.md:73-75`: the two submission mechanisms are TCP DataLink and the miniSEED file scanner.
  - `src/ringserver.h:36-44`: the enum is `PROTO_DATALINK | PROTO_SEEDLINK | PROTO_HTTP`.
  - `src/config.c:2674`: `SOCK_STREAM`. `src/config.c:2719`: `listen(fd, 10)`.
  - `doc/ringserver.md:26-33`: "All communications are performed via TCP".
  - The verdict is correct: ringserver has no UDP ingest.

### 4a. I ran the proof the prototype's README says was never run

`ringserver` 4.5.4 built from vendored source in about 1 minute with `make` (gcc/make are present). The artifact is `scratchpad/rs/ringserver/ringserver`. It is a user-space build, not a system package.

I wrote a ~20-line scratch adapter implementing `DataLinkPublisher` with `simpledali.SocketDataLink.writeJSON("BC_CUE/JSON", …)` (`dlproof/proof.py`). The ringserver command was the README's, on alternate ports:

```
RS_ACCEPT_IP=127.0.0.1/32 RS_WRITE_IP=127.0.0.1/32 RS_TRUSTED_IP=127.0.0.1/32 \
  ringserver -v -Rd ring -Rs 1M -Rp 1200 -VOLATILE -DL 16101 -SL 18101
```

Output (`dlproof/proof.out`):

```
receipt: AcceptReceipt(decision='accept', reason='accepted')
receipt: AcceptReceipt(decision='accept', reason='accepted')
receipt: RejectReceipt(reason=<RejectReason.REPLAY: 'replay'>, decision='reject')
dali read: ('PACKET', '1', 'BC_CUE/JSON', '{"issuer": "issuer-a", "key_id": "key-a", "kind": "available", "subject": "sha256:…6ab8c0a600000001", …')
dali read: ('PACKET', '2', 'BC_CUE/JSON', '{"issuer": "issuer-a", … "sha256:…6ab8c0a600000002", …')
ms3 write: OK len 157
seedlink INFO STREAMS format J I -> {"software": "SeedLink v4.0 (RingServer/4.5.4) :: SLPROTO:4.0 SLPROTO:3.1 CAP WS:13", … "station": [{"id": "BC_CUE", … "stream": [{"id": "BC_CUE", "format": "?", …}]}, {"id": "XX_CANT", … "stream": [{"id": "_L_O_G", "format": "3", …}]}]
```

What this shows:
- **Issue #49's "remaining proof gate" can be met:** UDP cue → receptor → DataLink write → ringserver ring → DataLink READ back.
  - The subject suffix `6ab8c0a6` is that run's epoch timestamp in hex, so the packets are unique to the clean run. Two earlier runs collided on ports and are not counted.
  - Caveat: I used simpledali READ instead of `dalitool`, which is not pip-installable. It is the same DataLink protocol.
- **Incidental evidence of the at-most-once semantics.** In an earlier run, ringserver failed to bind (`rs.log`: "Servname not supported" for `-DL 127.0.0.1:16000`; `-DL` takes only a port and uses the IP ACL env vars). The receptor returned `quarantine/publisher_unavailable` twice. The resend then got `reject/replay`, so those notices were lost permanently. That is exactly README:54-57, and it is a poor fit for a lossy loop broadcaster.
- **SeedLink visibility.**
  - Per the ringserver source, SeedLink selectors compile to regexes `FDSN:NET_STA_…/MSEED3?$` (`src/slclient.c:447-459, 2399-2412`), and legacy IDs need `/MSEED$` (`src/ring.h:62`).
  - So a `BC_CUE/JSON` DataLink packet is **not deliverable to SeedLink data clients**. INFO lists it with `"format": "?"`. I did not runtime-test data delivery for BC_CUE; that conclusion comes from source reading.
  - A **miniSEED3 text record** (encoding 0) *is* deliverable. I tested this (`dlproof/sl_data.py`):
    - I wrote `FDSN:XX_CANT__L_O_G` carrying the text "what is now and healing: patch 4.2 rolled; ttl 60" plus extra header `{"BC":{"ttl":60,"lens":"healing"}}`, via DataLink `writeMSeed3`.
    - A SeedLink **v4** client (`SLPROTO 4.0`, `STATION XX_CANT`, `SELECT *`, `DATA`, `END`) received it: `SE` framing, format `3`, seq 1, and decoded payload and extra headers intact.
  - A SeedLink **3.1** client received `SL000001` followed by the raw 146-byte **miniSEED3** record (`MS\x03…`), not a 512-byte miniSEED2 record.
    - ews-concept-new's client is SeedLink 3.1 over WebSocket (`/home/user/ews-concept-new/src/lib/seedlink-client.ts:3,6`). It parses bytes 8.. as miniSEED2 (`seedlink-client.ts:455-460`) and would fail on such packets.
    - [ASSESS] Consequence: to render canticle streams on the ews/nerv dashboards, either emit **512-byte miniSEED2** records (ASCII encoding 0 for text, or integer samples for a numeric "carrier"), or move the dashboard client to SeedLink v4 with miniSEED3 parsing.
    - The ews log line "need 47, found 6" is out of scope here. It is consistent with a non-miniSEED2 payload reaching `parseHeader`, but I did not verify that.

## 5. Localhost-only restrictions and distance to LAN / multicast / internet

- [IMPL] `UdpCueListener.__init__` rejects any host that is not an IPv4 loopback literal (`udp.py:20-22`: `ipaddress.ip_address(host)`; version==4 and `is_loopback`).
  - 127.0.0.0/8 is allowed. `0.0.0.0`, LAN addresses, multicast groups and `::1` are refused (test_udp.py:69-71).
  - The hostname `localhost` also fails, but with a generic `ipaddress` ValueError rather than `listener_must_be_ipv4_loopback`.
- [SAYS] Issue #49 says: "Do not broaden this prototype into … remote listeners". The workorder says: "no remote listener/proxy trust".
- There is **no sender side at all** apart from `encode_signed_notice`, which is used only by the tests.
- Distance to the target transports [ASSESS]:
  - **LAN broadcast/multicast.** Needs several changes:
    - Bind to `0.0.0.0:9999` (port 9999 does match protocol-spec-v0.1 §3.1, `proto/protocol-spec-v0.1.md:112`).
    - Join a group with `IP_ADD_MEMBERSHIP` (spec: `239.13.13.13`, :114), `SO_REUSEADDR`/`SO_REUSEPORT` so several hearers on one host can share the port, and set `IP_MULTICAST_TTL=1`/`IP_MULTICAST_LOOP` on the sender.
    - Remove the loopback guard.
    - This is about 20 lines. I sanity-checked same-host multicast in this sandbox: join, send and receive on 239.13.13.13 all worked. That proves nothing about real LAN switches (IGMP snooping, Wi-Fi multicast rate limits and AP isolation are the practical hazards). Broadcast (`<subnet>.255`, `SO_BROADCAST`) is the more reliable fallback on flat LANs.
  - **Internet listeners.** Multicast does not route across the internet, and NAT drops unsolicited UDP. A listener-initiated relay/fan-out is needed:
    - The listener periodically sends a small "tune" datagram (soft-state subscription with TTL) to a relay, and the relay replies to the observed address/port. This keeps the NAT binding open.
    - This necessarily adds subscriber soft-state at the relay. The "no subscriber tracking at sender" rule (`stations-and-streams-v0.2.md:79`) can hold at the *station*, not at the relay.
    - The relay also needs anti-amplification: a return-routability cookie before sending more than about 1× the request bytes, in the style of QUIC Retry or DTLS HelloVerify. Otherwise spoofed tunes turn it into a DDoS reflector.
    - Ringserver can serve as the TCP/WebSocket fan-out for internet listeners (`CAP WS:13` shown above), with a UDP→DataLink bridge like the proof adapter. That gives SeedLink/DataLink-over-WebSocket to browsers and remote agents for free, at the cost of TCP.
  - **DNS SRV.** Nothing is implemented. The spec requires `_canticle._udp.<zone>` (`protocol-spec-v0.1.md:249-272`).

## 6. Correctness bugs, security issues, test gaps

Severity reflects the prototype's own goals (a bounded, fail-closed receptor). Every item was reproduced unless marked "by reading".

### Bugs / security

- **B1 (HIGH, availability; reproduced): an 11-byte unauthenticated datagram kills the receptor.**
  - `parse_packet` calls `canonical_json(value)` at `codec.py:135`, **outside** the `try` at codec.py:125-133.
  - `json.loads` turns `1e400` into `inf` (the `parse_constant` hook at codec.py:63-64,130 catches only the literals `NaN`/`Infinity`). `json.dumps(allow_nan=False)` then raises `ValueError`, which escapes `NoticeReceptor.process`, then `UdpCueListener.serve_forever` (udp.py:46-54), then `main`.
  - Repro: I ran the CLI, sent a good packet (`accept accepted`), the same packet again (`reject replay`), then `b'{"a":1e400}'`. The trace ended `ValueError: Out of range float values are not JSON compliant`, `exit=1`. The next good packet was never processed (`probe/cli.log`).
  - Also triggers via `"issued_at":1e999` inside an otherwise normal packet (probe3). A top-level `-1e400` is harmless only because `not isinstance(value, dict)` short-circuits.
  - Fix: `parse_float=` hook that raises, since the schema has no floats, **and** move line 135 inside the try; also add a per-packet catch-all in `serve_forever`.
- **B2 (HIGH, availability; reproduced): SQLite errors crash the listener.**
  - `state.claim` re-raises every `sqlite3.Error` (state.py:106-108). `receptor.process` does not catch it (receptor.py:77).
  - With another connection holding `BEGIN IMMEDIATE` on the state file, `process` raised `OperationalError: database is locked` after 5.0 s (probe2 D).
  - Realistic triggers: a second receptor started with the same `--state`, a backup tool, or a full disk. Any of these is a crash, plus a 5 s stall per packet before it.
- **B3 (MEDIUM; reproduced): a publisher exception other than `PublisherUnavailable` escapes after the claim was committed.**
  - `receptor.py:92-95` catches only `PublisherUnavailable`, while the claim was already committed at `state.py:104`.
  - A realistic DataLink adapter raising `ConnectionResetError`/`RuntimeError` crashes the listener, and that notice is permanently burned: a resend got `reject/replay` (probe2 C).
- **B4 (MEDIUM, DoS by design; reproduced): replay-cache sizing makes the receptor fail closed for about 24 h after about 10k notices.**
  - Parameters: cap 10,000 (state.py:23) and `retain_until = expires_at + 86_400` (state.py:25,101).
  - Sustained capacity is 10,000 / (86,400 + ≤60) ≈ **0.116 notices/s ≈ one every 8.6 s, summed over all issuers**.
  - At the measured 783 accepts/s (probe2 A), one authorized issuer fills the cache in about 13 s. After that **every** issuer gets `quarantine/replay_cache_full`: still full at +1 h, recovered at +25 h (probe2 B).
  - The 24 h retention is unnecessary for replay safety within a stable clock, because expired notices are rejected (receptor.py:74-75) *before* the claim (receptor.py:77). `expires_at + skew` would be enough and would raise capacity about 1,300×. The 24 h only defends against a wall-clock rollback.
  - No per-issuer quota exists.
  - [ASSESS] This is fatal for "items loop at a controllable frequency" or "thousands of agents".
- **B5 (MEDIUM, authorization; reproduced): tombstones are global, permanent and not issuer-bound.**
  - Any allowed issuer can tombstone any subject, and that blocks all issuers (probe1: issuer-b tombstones subject 9, then issuer-a's AVAILABLE for subject 9 gets `subject_tombstoned`).
  - Tombstones never expire: +10 years later the same subject was still rejected (probe2 E).
  - There is no delete path in the code at all. After 10,000 tombstones every further tombstone is `quarantine/tombstone_cache_full` forever (state.py:82-88).
  - This contradicts the "pluck" semantics in stations-and-streams (pluck is TTL-bounded: "Once TTL expires … pluck is moot", `stations-and-streams-v0.2.md:69`).
- **B6 (LOW; reproduced): the replay namespace is not per-issuer.**
  - `seen_notices.notice_id` is a global PK (state.py:35-38). Issuer B can pre-burn issuer A's notice_ids (probe1: B uses id 7, then A's notice with id 7 gets `reject/replay`).
  - Nothing requires notice_ids to be random. The tests use `"1"*32`, and no generator is provided.
- **B7 (LOW; reproduced): encoder/decoder asymmetry.**
  - `encode_signed_notice` (codec.py:102-118) validates none of the issuer/key_id/subject/notice_id formats.
  - It happily produced a 271-byte packet with `issuer="Issuer-A"`, `subject="not-a-digest"`, `notice_id="XYZ"`, which the parser rejects as `malformed_packet`.
- **B8 (LOW; by reading): the CLI does not validate its own flags.**
  - `__main__.py:23-24` does not check `--issuer`/`--key-id` against `_IDENTIFIER` (codec.py:18). An operator who types `--issuer Issuer-A` gets a receptor that silently rejects every packet as `malformed_packet`.
  - The CLI wires only one issuer and key, and `--host` is still restricted to loopback.
- **B9 (LOW; by reading): listener construction hygiene.**
  - `udp.py:24-25` creates and binds the socket in `__init__`. A bind failure (port in use) leaks the socket.
  - `serve_forever` (udp.py:46-54) has no stop signal, no error isolation (see B1-B3), and discards the peer address (udp.py:43), so there is no rate-limit or abuse attribution even locally.
- **B10 (LOW, security hygiene; by reading): signature construction.**
  - The signature has no domain separation (codec.py:109-112). A key reused to sign other canonical-JSON objects is open to cross-protocol confusion. Recommend prefixing a context such as `b"binary-canticle/cue/v1\x00"`.
  - `key_id` is a free label, not bound to a key fingerprint.
- **B11 (INFO): policy runs before crypto (receptor.py:53-60).**
  - Unauthenticated packets naming an unknown issuer produce *quarantine* receipts.
  - This is harmless today because receipts are never sent back. It becomes an issuer/key enumeration oracle if a `receiptPlan` ever goes on the wire. It also pollutes any future quarantine/accord accounting (receptor-contract §9.4) with forgeable events.
  - Recommendation: unknown issuer/key → `drop` (ignored-but-accounted), not quarantine.
- **B12 (INFO): signature verified before the cheap time checks (receptor.py:61-75).**
  - Every packet claiming a known issuer and key costs one Ed25519 verify, even if it is stale. Cheap checks first would reduce flood cost.
- **B13 (INFO): clock handling.**
  - The receptor uses wall-clock seconds (`time.time`, receptor.py:40,66).
  - A forward jump of more than 24 h purges replay rows (state.py:58-61). A subsequent backward jump then reopens replay.
  - Only seconds granularity is available, whereas the spec uses µs `ts` and ms `ttl_ms` (protocol-spec-v0.1.md:147-148).
- **B14 (INFO, performance): about 783 accepted notices/s on this VM.**
  - Each packet is a synchronous SQLite transaction in default `journal_mode=delete` / `synchronous=FULL`, with an unindexed `DELETE … WHERE retain_until <= ?` and a `COUNT(*)` (state.py:57-80).
  - That is fine for a doorbell and poor for a broadcast fleet. Durable dedup is arguably the wrong tool for 60 s lossy items; a bounded in-memory LRU keyed by (station, stream, seq) fits better.
- **B15 (INFO, auditability): receipts carry only decision and reason (model.py:52-66).**
  - There is no notice_id, issuer, or observedAt, so an operator cannot tell *which* notice was rejected.
  - This is deliberate ("never echo sensitive payload", workorder), but it violates receptor-contract §7's invariant that a judgment object "MUST NEVER float free of a source frame" (`receptor-contract-v0.2.md:195-198`). notice_id is not sensitive.

### Test gaps (15 tests; `tests/test_receptor.py`, `tests/test_udp.py`)

- There is no fuzz or property test of `parse_packet`. B1 would have been caught by one. Untested inputs include overflow floats, deep nesting, and bool-as-int (it is handled correctly; probe3 verified `true` gives malformed).
- Resilience is untested: no test of `serve_forever` staying up after a bad packet, of SQLite errors (B2), or of generic publisher exceptions (B3).
- Boundaries are untested: TTL exactly 60 (accepted), skew exactly +5 (accepted), a packet of exactly 1200 B, and `version != 1` (probe3 verified malformed). Signature trailing-bit malleability is also untested (probe3 verified rejection).
- Cross-issuer interactions (B5, B6) are untested.
- Replay-row expiry and GC are untested, as is recovery after the cache fills (B4).
- `test_quarantines_when_bounded_state_caches_are_full` (test_receptor.py:231-274) never asserts that the publisher saw nothing on the quarantine paths, nor that the first "filler" accept succeeded.
- There is no CLI test (`__main__`) and no sender round-trip test through a real socket other than one happy path (test_udp.py:34-67).
- There are no multi-issuer or multi-key tests, and no key rotation test.
- The duplicate-key JSON rejection works (probe3) but is untested.

## 7. Implementation vs `proto/` docs: divergences

| Topic | Doc says [SAYS] | Prototype does [IMPL] |
|---|---|---|
| Frame fields | receptor-contract Table A requires `frameId, stationId, memberId, streamId, sequence, kind, emittedAt, observedAt, ttlMs, payload, …` (`receptor-contract-v0.2.md:117-137`). protocol-spec §3.3 requires `v, station, stream, seq, ts(µs), ttl_ms, kind, payload` (`protocol-spec-v0.1.md:141-155`). stations-and-streams payload frame is `{station_id u128 ULID, stream_id u32, seq u64, ttl_seconds u32, content_type, plucked_bit, content_bytes}` (`stations-and-streams-v0.2.md:48-56`). | Only `issuer, key_id, notice{kind, subject, notice_id, issued_at, expires_at}, signature, version`. **No station/stream addressing, no seq, no payload/content_type, no observedAt.** issuer ≈ station and notice_id ≈ frameId/nonce at best. |
| Payload | Opaque `content_bytes`/`payload` is the point (chatter, cards, posture). | **Forbidden by design.** Only a sha256 digest `subject` (README:41-44; workorder). It is a doorbell that implies an out-of-band fetch, which the workorder excludes. |
| Encoding | CBOR recommended, JSON optional; first byte `{` means JSON (`protocol-spec-v0.1.md:124-135`; `stations-and-streams-v0.2.md:105-112`). | Canonical JSON only. |
| Unknown fields | "Frames with unknown fields MUST be accepted (forward-compat)" (`protocol-spec-v0.1.md:157-158`); CBOR unknown-tag-skippable is "load-bearing" (`stations-and-streams:112`). | **Rejected** (closed schema, codec.py:137-138,155-156). The opposite of the forward-compat stance. It is defensible for a security kernel, but contradicts the spec. |
| Auth | v0.2 base layer is trust-of-LAN, with Ed25519 as a v0.3 opt-in overlay (`stations-and-streams:122-126`). protocol-spec §9.4 proposes HMAC-SHA256 with a frond key, and "log unsigned but accept" by default (`protocol-spec-v0.1.md:493-498`). | **Mandatory** Ed25519 per issuer key. Unsigned or unknown frames are rejected or quarantined. Stricter than both docs; it matches protocol-spec open question 1 ("per-station Ed25519 keys", :587-588). |
| TTL | `ttl_ms` ≤ 60000 SHOULD (`protocol-spec:148`). Per-stream default TTL with per-frame override downward only; e.g. `cael:thoughts` 5 min (`stations-and-streams:86,134`). | Hard cap of 60 s (receptor.py:23), seconds granularity. A 5-minute stream is impossible. |
| Duplicates | Ringbuffer `append` SHOULD be idempotent; a duplicate MUST be explicit "accepted-as-existing / no-op" (`ringbuffer-contract.md:120-130`). receptor §9.3 says a replay hit is `drop` / "ignored-but-accounted". | `reject/replay`. Functionally dedups, but the wrong semantic label for a looping broadcaster, where repeats are expected. |
| Withdrawal | `pluck` is a TTL-bounded header bit plus a best-effort pluck frame (`stations-and-streams:58-69,136`). | `tombstone` kind with **permanent**, global, issuer-unbound suppression (B5). |
| Receptor output | Judgment object with `disposition ∈ {surface, ringbuffer_only, drop, quarantine_action}`, `stateDelta`, `receiptPlan`, `evidence[]`, source-frame pointer (`receptor-contract:200-209`, §7.3 evidence mandatory). | `accept/reject/quarantine` + one reason enum. No evidence array, state delta, frame pointer or atmosphere. |
| Receptor state | Table B: thresholds, modulationState, stationTrust/Quarantine, pressure, accord, recentRates, replayDedup, decay (`receptor-contract:157-171`). | Only replayDedup and tombstones (plus a static issuer policy). No chemokine or threshold machinery. None of the 8 executable examples in §13 (:485-509) are implemented. |
| Transport | UDP broadcast/multicast `239.13.13.13:9999`, ≤1472 B, fragments (`protocol-spec:111-120,162-170`); carrier beacon 1 Hz (`stations-and-streams:21-33`); DNS SRV bootstrap (`protocol-spec:238-300`). | Loopback unicast only, port 9999 default. No multicast, beacon, SRV or fragmentation. |
| Ringbuffer | Per-stream ring, `append/replay/tail`, truncation metadata (`ringbuffer-contract.md:57-82,132-144`). | None locally. Ringserver would be the ring behind the seam; the proof in §4a shows it works via DataLink, but the prototype does not wire it. |
| Layering | "Wire stays stupid … no quarantine policy" (`receptor-contract:57-60`). | This is honored in the sense that the policy lives in the receptor, not the UDP layer. But the UDP layer and receptor are fused in one synchronous loop with no ringbuffer between them. |

Where it *does* conform:
- The 60 s default TTL magnitude.
- The UDP single-datagram rule.
- Port 9999.
- "Wire stays stupid": the listener only hands bytes to the receptor.
- Bounded forgetting, although the parameters are wrong for broadcast.
- The explicit no-exactly-once stance.

## 8. Is this the right base for the next spike?

The next spike is a looping TTL broadcaster, plus a carrier wave, plus a listener that notifies an OpenClaw or Claude Code session.

[ASSESS] **No, not as the base. Yes, as a donor of a hardened "verify" stage.**

It is a well-built answer to a different question: how to admit a signed, content-free cue into a TCP ring without leaking anything.

Its core model conflicts with the owner's intent at every load-bearing point:
- There is no payload, so chatter or shared chain-of-thought cannot be carried.
- Repeats are rejected rather than treated as a no-op, which fights looping.
- The 60 s TTL cap is too short.
- Replay-cache sizing caps throughput at about 0.1 notices/s total.
- Tombstones are permanent.
- There is no station:stream addressing and no seq.
- The listener is loopback-only.
- There is no sender and no carrier.
- Delivery is at-most-once *burn* on publisher failure.

**What to keep (port into the new spike):**
1. The strict parse discipline: canonical encoding check, duplicate-key rejection, exact types, strict base64 (codec.py:54-80,121-195), after fixing B1.
2. `IssuerPolicy` and quarantine-by-policy as a *per-stream profile* (signed-required streams vs. trust-of-LAN streams, matching `stations-and-streams:122-126`).
3. Typed receipts, extended with a frame pointer and evidence per receptor-contract §7.
4. The publisher-seam idea, generalized to "sinks": a ringserver DataLink sink (proven in §4a), a session-notify sink, and a dashboard sink.

**What to change or replace:**
1. **Frame.** Adopt the stations-and-streams payload frame:
   - `{v, station_id(ULID16), stream_id(u32), seq(u64), ts_us, ttl_ms, kind, lens?, content_type, plucked(bit), payload(bytes ≤ ~1000)}` in CBOR.
   - Add an optional Ed25519 signature trailer over domain-separated bytes (B10), per stream profile.
   - Dedup key `(station, stream, seq)`, kept in a bounded in-memory LRU sized ≈ Σ(rate × ttl). Durable dedup is not needed for lossy 60 s to 5 min items.
   - A duplicate is `held/no-op`, not a reject.
2. **Broadcaster (the new piece).**
   - A per-stream ring of live items. Each item is re-emitted every `period_ms`, with jitter, until `ts + ttl_ms`.
   - A `pluck` sets the bit and emits one pluck frame.
   - `sing(station:stream, text, ttl, period)` as a tiny CLI and MCP tool for OpenClaw and Claude Code clients.
   - Rate limiting at the sender and per-station caps at the receiver ("cell membrane").
3. **Carrier.** A 1 Hz beacon `{station_id, head_seq, wallclock_ns, schema_version, streams[{stream_id, default_ttl}]}` (`stations-and-streams:139`).
   - Receivers derive liveness from carrier drop.
   - Optionally emit the carrier *also* as a 1 Hz numeric miniSEED2 channel (e.g. salience or pressure), so the ews/nerv waveform views render it natively.
4. **Transport modes.**
   - `loopback` (tests).
   - `lan` (multicast 239.13.13.13:9999 with broadcast fallback; remove the udp.py:20-22 guard behind an explicit flag).
   - `relay` (internet: listener-initiated soft-state tunes with a cookie and anti-amplification).
   - `ringserver` sink/source for TCP/WebSocket fan-out and replay. Note that SeedLink needs miniSEED: miniSEED2 for 3.1 clients such as ews, miniSEED3 for v4 (§4a).
5. **Listener → session notify.** Coalesce per (station, stream), then call a sink.
   - **OpenClaw:** the gateway already exposes `POST /hooks/wake` with `text`, `mode: now|next-heartbeat`, `sessionKey`, and returns `eventOutcome: queued|coalesced` (`/home/user/openclaw/docs/gateway/config-hooks.md:80`).
     - The same RPC is exposed in the CLI as `openclaw system event --text … --mode … --session-key …` (`/home/user/openclaw/src/cli/system-cli.ts:67-106`). The event is injected as a `System:` line on the next heartbeat (`docs/cli/system.md`).
     - `next-heartbeat` maps to quiet enrichment and `now` maps to wake/clarion. This is analogous to the continuation RFC's `silent` / `silent-wake` (`continue-work-signal-v2.md:247-253` on `origin/codeagent/85651-upstream-1ba243c8-gates`).
     - The built-in "coalesced" semantics fits looping re-broadcasts.
   - **Claude Code:** candidate seams to verify in the next spike: a background listener process whose output the harness surfaces (background task or monitor notifications), an MCP server exposing `tune`/`recent`, or a UserPromptSubmit hook that injects recent stream state.
6. **Fix list if any of this code is reused:**
   - B1: `parse_float` reject plus a try-wrap of codec.py:135, and a per-packet catch-all in `serve_forever`.
   - B2 and B3: map `sqlite3.Error` and generic publisher errors to quarantine without crashing.
   - B4: set retention to `expires_at + skew`, add per-issuer quotas, and evict rather than fail closed for a lossy medium.
   - B5: bind tombstones and plucks to the issuing station and expire them with the TTL.
   - B6: scope the replay key per issuer.
   - B7 and B8: validate on the encoder and the CLI.
   - B15: add notice_id and observedAt to receipts.

## 9. Library and tool availability (tested here)

| Package | `pip download --no-deps` result | Notes |
|---|---|---|
| `simplemseed` | OK: simplemseed-1.0.2-py3-none-any.whl (58 kB) | pure Python; miniSEED2/3 read/write; installed in `venv-dali`, used to write the ms3 text record |
| `simpledali` | OK: simpledali-0.8.3-py3-none-any.whl (26 kB) | DataLink client, socket and WebSocket, asyncio; the version the prototype README pins; used for the proof |
| `pymseed` | OK: pymseed-1.0.0 cp311 manylinux (1.2 MB) | libmseed bindings |
| `obspy` | OK: obspy-1.5.1 cp311 manylinux (15.3 MB) | includes SeedLink clients (not tested here) |
| `mseedlib` | OK: mseedlib-0.0.10 manylinux (245 kB) | – |
| ringserver | not on pip; `curl` of the GitHub tarball returned a proxy JSON error, but `git clone --depth 1 --branch v4.5.4 https://github.com/EarthScope/ringserver.git` worked | built with `make -j` from vendored pcre2/mxml/libmseed/mbedtls/miniz; binary reports `ringserver version: 4.5.4` |
| `dalitool`, `slinktool`, `dlclient` | not present; not pip-installable | simpledali or raw SeedLink sockets were substituted |

Wheels are in `scratchpad/pipdl-seis/`. PyPI (`pypi.org`, `files.pythonhosted.org`) is on the proxy's no-proxy list and reachable.

## 10. One-paragraph bottom line

The prototype is a careful, well-tested (15/15), security-first *cue* receptor.
- It accepts a closed, canonical, Ed25519-signed JSON notice (330–490 B) carrying only a sha256 digest.
- It enforces a ≤60 s TTL, persistent replay dedup and permanent tombstones, and hands the notice to a stub DataLink seam that nothing implements.

Its ringserver verdict (TCP-only, no UDP ingest) is correct. The missing native proof now works: I built ringserver 4.5.4 and pushed cues through a 20-line simpledali adapter.

It has one trivially triggerable crash (B1) and several fail-closed capacity and authorization problems (B2–B6). Its data model contradicts the looping, payload-carrying, station:stream broadcast the owner wants.

Use it as a donor for the verify stage and as proof of the DataLink/SeedLink route, not as the base of the broadcaster spike.
