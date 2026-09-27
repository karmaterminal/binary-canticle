# Decision spine (orchestrator-authored, 2026-09-27)

Shared positions that BOTH the report and RFC-0001 must follow, so they agree. A writer may deviate only when a challenge note (notes/challenge-*.md) gives strong evidence, and must then say so explicitly in the text ("Deviation from spine: ...").

## Owner intent (restated)
binary-canticle = station:stream lossy broadcast for agents. Trusted clients (OpenClaw sessions, Claude Code TUI sessions, sub-agents) put TTL items on a station:stream. The station LOOPS (re-broadcasts) each live item at a controllable frequency until TTL. Every station carries a small carrier wave. Transport is UDP; LAN multicast is optional; internet UDP listeners are REQUIRED. Discovery is DNS SRV. A listener (e.g. a Claude Code sub-agent or an OpenClaw session) hears streams and notifies/enriches other sessions in its harness. Use cases: chatter, shared chain of thought, attuning a fleet to a purpose, MAGI-style aspected streams ("what is now and threat", "what is now and healing", each kept by an aspect-keeper sub-agent), and fleet-wide response to a security threat. Regulation is membrane-like (chemokine, immune metaphors). HAProxy was a conjecture for the control layer. SeedLink is the inspiration, and SeedLink dashboards (ews-concept-new, nerv-ui) should be able to show stations.

## Positions
P1 Carousel semantics. A station holds a ring of live items. It re-emits each item BYTE-IDENTICALLY every loop_ms (per-stream default; per-item override clamped by station policy; ±jitter) until the item's ABSOLUTE expires_at. Remaining life never resets (#51 invariant). Late joiners catch up passively within one loop period. There is no back-channel to the station: no since-token, no request/response. Receivers dedup on (station key-id, epoch, stream_id, seq); a repeat is a benign no-op, not a replay attack. Pluck (revoke) = a pluck frame that itself loops until the original expires_at; receivers keep a sticky-pluck set (carried over from the #32 review).

P2 Frame classes (from the decoherence-axis spike):
- live-state: keyed; supersede-by-key; short TTL (aspect streams live here).
- ambient/chatter/weather: lossy, TTL-bounded.
- finding: promoted to the ledger only by an explicit act, linked by digest.

P3 Carrier wave. A signed carrier-beacon at 1 Hz (configurable), content-free presence. Fields: station key-id, epoch, wallclock, and per-stream heads (stream_id, head seq, live count, loop_ms, default/max TTL). Optional capsid under a disclosure policy (scratch/notes_on_carrier_wave.md). 4-state presence machine; explicit UNEQUIP. Relays may aggregate or slow beacons. Beacon overflow (>~180 streams) → rotate streams across beacons.

P4 Wire. Canonical frame v2: magic + version byte; deterministic CBOR with integer keys; Ed25519 signature trailer (64 B) plus 8-byte key-id. Total UDP payload ≤1200 B; canonical frame target ≤1100 B so it fits relay envelopes and WebTransport datagrams. Never fragment. Large bodies travel by reference (digest + out-of-band URL); multi-part carousel with FEC is future work. Supersedes the v0.1 frame, the v0.2 frame (which lacks timestamp and version) and the prototype JSON notice. v0.1's "1472 including headers" is wrong. Multicast group 239.255.x.y (not 239.13.13.13).

P5 Identity & trust. Station identity = its Ed25519 public key (key-id = hash prefix). Human names bind via DNS-SD TXT plus the signed beacon. Receptors hold allowlists. Unsigned frames only at scope ≤1 (loopback), recorded sigState=absent, never counted toward accord. Drop shared-HMAC. Cohort accord counts DISTINCT KEYS, as a quorum or fraction. This closes #48 with key lifecycle and test vectors.

P6 Transport bindings: (a) host-local/loopback; (b) optional LAN multicast fast path (239.255/16, IP TTL 1, ff02::/ff05::) with a `canticle doctor` self-test that includes the >260 s IGMP querier check; (c) unicast relay lease for internet and Wi-Fi — the DEFAULT outside a known wired VLAN; (d) TCP replay/dashboard tier = EarthScope ringserver fed over DataLink by a relay bridge, serving SeedLink v3/v4, DataLink and WebSocket; (e) later, WebTransport datagrams from the relay for browsers. "No subscription at the sender" stays true: the lease lives in the relay, never the station. Relay lease: HELLO (padded) → stateless COOKIE (HMAC of src ip/port/epoch) → LISTEN(cookie, filters) → stream; RENEW every 20-25 s ±20%; lapse ~75 s; pre-validation replies ≤ request size.

P7 Membrane. A purpose-built relay: verify, allowlist, TTL cap, per-station byte budget, attenuation (lower loop rate first, then drop classes), dedup, fan-out (sendmmsg), relay-to-relay chaining; nftables meters and a tc cap underneath. Community HAProxy CANNOT proxy generic UDP (udp@ binds only in log-forward sections, 3.0-3.5-dev), so #30's premise is false. HAProxy belongs on the TCP tier: TLS, ACLs, stick-table rate limits, PROXYv2 into ringserver, plus the HTTPS control API.

P8 Discovery = real DNS-SD. PTR _canticle._udp.<zone> → instance; SRV + TXT on the instance (txtvers, sid, k=ed25519 fingerprint, streams, carrier, relay, grp, mtu). mDNS on the LAN; DNSSEC-signed unicast zone on the WAN (not .local; SRP/SIG(0) registration). Also _seedlink._tcp / _datalink._tcp for the replay tier. The beacon, not DNS, is liveness. Check IANA before public use.

P9 Receive side. One receptor daemon per host (one listener → many sessions). The hearer ring appends raw frames BEFORE judgment; the receptor is deterministic; the ledger is written only by promotion. The listener chooses the landing mode (from Ronan/Emeric's orphan branch): silent (default) / silent-wake / post-compaction, mapped to OpenClaw continue_delegate modes. Wake requires ALL of: valid signature + allowlisted station + wake-eligible class + session opt-in + per-session token bucket + canticle hop count (because OpenClaw chain budgets reset on external events). Never sender-forced. [OWNER DECISION D1]

P10 Publish side. Tools are verbs, per OpenClaw RFC §4.6 substrate-adoption: canticle_sing{stream, payload, mode broadcast|addressed, keepOnAir{forSeconds, loop}, purpose}, canticle_hush (pluck), canticle_tune / canticle_listen (receiver config). The tool clamps TTL/loop, signs, and assigns seq/epoch. Two-gate emission (Ronan): a hook decides WHEN, the agent decides WHAT or nothing. Choosing when an item goes on air is separate from how often the station repeats it.

P11 OpenClaw binding. Tier A (no core change): plugin registerService UDP/relay listener → runtime.system.enqueueSystemEvent(wrapExternalContent(banner+payload), {contextKey:'canticle:<station>:<stream>', replace:true}), plus requestHeartbeatNow only for wake-eligible items; alternative: an out-of-process receptor → POST /hooks/wake (it must wrap content itself). Tier B (upstream PR): a durable addressed bridge modeled on enqueueContinuationReturnDeliveries (idempotencyKey canticle:<sid>:<epoch>:<seq>:<sessionKey>). Arrival banner modeled on RFC A.6.3. Config gates default-off, mirroring crossSessionTargeting. NOTE: continuation (silent/silent-wake/targeting) exists only on the karmaterminal gates branch, not openclaw main.

P12 Claude Code binding. One MCP server: publish tools; a channel capability for wake-eligible alarms (research preview); a receptor digest file injected via UserPromptSubmit/SessionStart hooks as additionalContext. A background listener sub-agent (Monitor tool / run_in_background) notifies other same-machine sessions via SendMessage/messaging socket. No durable push in Claude Code; accept lossy.

P13 Aspected streams (MAGI). Lens/aspect is a stream-level attribute. Each aspect stream has one aspect-keeper sub-agent that re-sings its current synthesis as a keyed live-state item (supersede-by-key). Receivers weight lenses locally. A dashboard MAGI panel shows the three lenses.

P14 Dashboards. ringserver is the replay tier. Carrier → miniSEED2 1-sps int32 channel with a VARYING value (e.g. live-item count), so ews renders a live trace. Items → miniSEED3 text (encoding 0) with {"BC":{...}} extra headers, record span = TTL, so SeedLink v4 `DATA ALL <now>` returns the on-air set. Fix ews: use ringserver's /seedlink WebSocket plus ews's unused src/lib/seedlink-client.ts, and drop bagusindrayana/seedlink-websocket (it forwards raw TCP chunks, causing 'need 47, found 6'; it also has input-handling issues, detailed privately). nerv-ui (React, MIT) fits a React console; it has no real waveform (pair it with seisplotjs). Network code XX is test-only.

P15 Scale. Thousands of listeners → relay tree (ForestColl/Edmonds-style tree packing applies here, not on the LAN); per-station budgets; beacon aggregation. The design centre moves from a 4-6 prince cohort to a fleet; test at cohort scale first.

## Repo actions (consensus of readers)
- PR #50: CLOSE — landed as 65e6705 (byte-identical). Keep issue #49 open or retitle it for the native ringserver proof (now reproduced in scratch: ringserver 4.5.4 + simpledali).
- PR #32: CLOSE — landed via #42 (07e4e58). Carry sticky-pluck and beacon-overflow into the RFC.
- PR #29: CLOSE — superseded by proto/ringbuffer-contract.md (0a49371).
- PR #34: MERGE after light edits (INDEX row; note the v0.1 JSON example shape). Main already links it: spike/two-planes:5 has a dangling link.
- PR #44: REQUEST CHANGES (layout overlaps; _bc._udp.local → _canticle._udp.<zone>; add carrier-beacon, loop, signing; ringserver is TCP behind a UDP sidecar). Then reuse it as the RFC figure.
- Orphan branch ronan/20260614/send-receive-threshold-landing: open a PR or fold it into the RFC (two-gate emission, seven lifecycle seams, listener-chosen landing modes). Replace its spoofable ingress gate (packet.provenance.trusted) with signature admission.
- Issues: close-as-done #22 #25 #26 (#23 after cross-refs); close-as-obsolete #3 #9 #15 #31; merge #13 #18 → #11 (#18's registry decision superseded); #19 → #26; relabel/move #20 (control plane → openclaw); reopen or re-scope #37 #39 #40 (closed without their fixtures); refresh #21; README #35. New issues: carousel/loop semantics; relay lease; membrane; frame v2; conformance vectors (#27).
- Prototype: do not build the broadcaster on it. Reuse strict-parse / IssuerPolicy / Ed25519 as the verify stage after fixing B1 (an 11-byte {"a":1e400} crash), B2/B3 (sqlite/publisher crash), B4 (replay cache fills in ~13 s → 24 h lockout), B5/B6 (global permanent tombstones / global notice_id namespace).

## Owner decisions to surface (with recommended defaults)
D1 Receive posture: never sender-forced wake; receiver-local policy may escalate to silent-wake (recommended) vs. strict no-wake (v0.1 §9.2).
D2 Content lane: payload-carrying ≤1100 B frames plus digest refs (recommended), with "doorbell" digest-only as one stream class, vs. digest-only everywhere (prototype workorder).
D3 TTL ceilings: per-stream max_ttl (default 300 s; station hard cap, e.g. 24 h); the root mark persists by re-announce until UNEQUIP.
D4 Trust: Ed25519 mandatory beyond loopback (recommended).
D5 Scale target: design for fleet (relay tree), validate at cohort.
D6 Internet in scope: accept relay-held leases; the station still tracks nobody.
D7 SeedLink naming: private namespace vs. requesting an FDSN temporary network code; station → NET.STA mapping table.
D8 Console stack: ews (Svelte, fastest demo) vs. nerv-ui (React) vs. OpenClaw Control UI (Lit).
D9 Implementation language: Python spike (continuity with the prototype) → Go/Rust relay once the semantics settle.
D10 Relationship to brokers: see notes/challenge-broker.md.

## Work plan skeleton (refine)
S0 Housekeeping (PRs, issues, README, INDEX regen, dangling links, duplicate PDFs).
S1 Frame v2 codec + conformance vectors (#27) + prototype fixes.
S2 canticle_station: carousel + carrier-beacon + loopback/multicast binding + `canticle sing/hush` CLI.
S3 Receptor daemon + OpenClaw plugin Tier A + Claude Code MCP/hook binding + blind-enrichment acceptance test (RFC §9.3 method).
S4 Relay/membrane: lease + cookie + budgets + attenuation + ringserver DataLink bridge; ews fix; carrier on a live trace.
S5 MAGI aspect keepers (threat/healing) demo + red-team test suite + scale test.
