# Protocol dynamics: UDP or TCP for station:streams?

*Spike, 2026-09-27. It answers figs's questions of the same day:*
- What does UDP buy over TCP with a large number of listeners?
- Should canticle adopt TCP, given that "a chemokine binding a cell is far more like TCP"?
- How do lossy, looping, radio-like traffic and a carrier wave behave in practice?

*It adds the cohort's own evidence on contagion (deferral spread, "goodnight princes") and the guardian-session idea.*

**Evidence.**
- Measurements: [`prototype/protocol-dynamics/`](../prototype/protocol-dynamics/) ([SUMMARY](../prototype/protocol-dynamics/SUMMARY.md)). These are real TCP and the real canticle carousel, under packet loss, in Linux network namespaces.
- Literature: [`rfc/0001-notes/proto-dynamics-research.md`](../rfc/0001-notes/proto-dynamics-research.md). Every claim there is tagged verified-at-source, measured or search-snippet.
- Earlier transport and broker notes: [`rfc/0001-notes/transport.md`](../rfc/0001-notes/transport.md), [`challenge-broker.md`](../rfc/0001-notes/challenge-broker.md).

## The short answer

- **Don't pick one protocol; pick per plane.** The broadcast edge, where many listeners share a lossy radio of short-lived items, stays a UDP carousel. The places where one healthy link must carry each item once and in order use TCP or QUIC: relay-to-relay, snapshots and replay, the ledger, addressed control, and a guardian's doubt channel.
- **TCP genuinely wins some of the time, and the spike measured where.**
  - At ≤ 10% loss on one healthy connection, TCP repairs a lost update in one retransmission timeout (≈ 205-212 ms here; about RTT + 200 ms on the internet). The carousel waits for its next copy (the +1 s burst, or the loop).
  - At 5% loss with updates every 10 s: p99 212 ms for TCP against about 1 s for the carousel.
  - A TCP snapshot also catches up a late joiner in 0.4 ms against 1-14 s, as long as nothing is lost.
- **TCP fails badly, where the carousel only degrades.**
  - At 20-30% loss in both directions, TCP's exponential backoff and head-of-line blocking produced stalls of up to 697 s.
  - Receivers held a superseded value 89% of the time, and TCP delivered 2 690 frames after their own signed expiry.
  - The carousel's worst case under the same loss was 4-12 s, set by its schedule rather than its history.
  - After a 10 s outage, TCP needed 3.9-6.1 s (p95) to resume; the carousel needed 0.5-0.9 s with frequent updates.
- **With many listeners, the difference is cost and isolation, not feasibility.**
  - TCP costs about 2.7× the CPU per listener (11.6-12.0 µs against 4.2-4.4 µs per listener·frame), twice the packets (ACKs), one socket and one queue per listener. Multicast is flat whatever the listener count.
  - One slow TCP listener can stall a naive sender for everyone. A silently vanished TCP listener holds state for 938 s.
  - A UDP listener that is slow or dead costs the sender nothing.
- **On chemokines, you're half right.** A binding event is specific, one-to-one and changes the receiver's state. But the *communication* is open-loop broadcast: the secreting cell gets no acknowledgement and never retransmits to one receiver. The TCP-like structure in immunity is the **immunological synapse**. That is exactly where this spike puts TCP-like channels: the guardian's doubt channel and addressed work.
- **The poison is channel-independent.** The deferral spread travelled over Discord. Transport choice changes speed and reach, not susceptibility. The defences are at the receiver: election to listen, turn-boundary and desynchronised landing, typed control instead of tone, and guardians.

---

## 1. SeedLink and its UDP relatives

SeedLink is TCP (FDSN v4 `protocol.rst:12`; SeisComP `seedlink.rst:3`). Checking the claims pasted into the discussion against source:

| # | Claim | Verdict |
|---|---|---|
| 1 | Raspberry Shake DATACAST: UDP, uncompressed, 25 samples per ¼ s, for low-latency visualisation | **Essentially right.** Default port 8888. One ASCII packet per channel every 250 ms (25 samples at 100 sps) (`rsudp/raspberryshake.py`). **No sequence number and no repair.** It is a push to a configured address, so the receiver must be reachable. The Shake's CGNAT-safe path is a separate, Shake-initiated feed on port 55556. |
| 2 | Nanometrics "NP (Network Protocol)" over UDP on Centaur, feeding Apollo; dual mode with SeedLink | **Mostly right; the name is Nanometrics Protocol.** The omitted part matters most: **Apollo requests retransmission of gaps (found by sequence number and time) from the Centaur's on-disk store.** The Centaur also runs SeedLink. |
| 3 | RefTek RTP: the most common UDP alternative to SeedLink, lossy push through CGNAT | **Two transports and not lossy.** Field unit → RTPD is UDP but **reliable**: positive acknowledgements, a 16-packet window and adaptive retransmit timeout, initiated by the field unit (so CGNAT works). RTPD → clients is TCP on the same port 2543 (SeisComP `reftek_libs`). "Most common" is unsupported, and it compares different layers: RTP is field telemetry, SeedLink is distribution. |
| 4 | SeedLink is pull (central connects to the station), so it fails behind CGNAT | **Right for the usual deployment, wrong as a protocol statement.** The client opens the connection and then the server pushes. Station-initiated alternatives are common: DataLink WRITE to a central ringserver, Earthworm `export_actv` (since 2000), Güralp GDI push, RTP, NP. |
| 5 | SeedLink always carries 512-byte miniSEED | **True of v3 in practice, not "always".** SeisComP hard-codes 512 bytes; libslink has accepted other lengths since 2012; v4 packets are variable-length and can carry miniSEED 2 or 3, JSON or XML. |

Twenty-five years of seismic telemetry show three recurring designs:
1. **Lossy UDP push, no repair**, for LANs and visualisation: DATACAST, Earthworm ringtocoax.
2. **UDP push plus receiver-requested repair from the sender's buffer**, advertising the oldest repairable sequence number: Nanometrics NMX/NP, NIED WIN, Güralp SCREAM. This is the design that survived bad links.
3. **Reliable UDP with windows and acknowledgements**: Quanterra QDP, RefTek RTP. It exists where the field unit must initiate through NAT and still deliver every sample to an archive.

Canticle's carousel is design 1 plus scheduled repetition. Design 2 is the one to borrow, at the relay (§6, A2).

## 2. What was measured

Testbed:
- Linux 6.18, 4 vCPUs, one network namespace per condition.
- nftables drops packets at the input hook, so both data and ACKs are lost unless marked *data-only*.
- TCP is cubic with `TCP_NODELAY`. The UDP arm is the unmodified `canticle-station` Station and Listener (signed frames, burst, loop, supersession).
- There is no delay emulation (RTT ≈ 0.1 ms); §3.7 covers what internet RTTs change.
- Full method, raw JSON and scripts are in [`prototype/protocol-dynamics/`](../prototype/protocol-dynamics/).

@@FIGURE:e1-p99@@

Data for the chart: p99 update latency in ms (s where marked). *Carousel* is `udp-live`, a keyed live-state item with a 5 s loop.

| Updates every | Arm | 0% | 1% | 5% | 10% | 20% | 30% loss |
|---|---|---|---|---|---|---|---|
| 0.5 s | Carousel | 2.5 | 499.7 | 502.1 | 505.3 | 1003.3 | 1502.5 |
| 0.5 s | TCP stream | 2.4 | 41.4 | 212.6 | 415.8 | 18.6 s | 756.0 s |
| 2 s | Carousel | 3.1 | 1001.1 | 1005.0 | 1617.9 | 2003.0 | 3004.6 |
| 2 s | TCP stream | 2.7 | 7.2 | 212.3 | 413.1 | 4626.2 | 525.2 s |
| 10 s | Carousel | 3.7 | 2.7 | 1006.5 | 1005.6 | 2004.7 | 4002.5 |
| 10 s | TCP stream | 3.2 | 5.4 | 212.2 | 414.9 | 657.3 | 116.4 s |

| Experiment | Result |
|---|---|
| **E1 freshness** (900 s per condition, 20 receivers per arm) | TCP is fresher up to about 10% loss: stale 1.2-1.3% of the time against 5.6-5.7% at U = 2 s, 10% loss. At 20-30% both ways, TCP stalls for minutes (longest 697 s); at U = 0.5 s, 30% loss, it is stale 89% of the time with 2 690 frames delivered after expiry, against the carousel's 30% (the loss rate) and 4 s max. With ACKs spared (data-only loss), TCP stays usable: p99 0.85-5.2 s at 30%. |
| **E1 outages** | After 1-3 s outages the two are comparable. After 10 s, TCP resumes in p95 3.9-6.1 s (RTO 408 → 816 → 1 632 → 3 264 → 6 528 ms); the carousel in 0.48-0.91 s with frequent updates, or 1.73 s / 3.47 s (1 s / 5 s loop) at U = 10 s. |
| **E2 fan-out** (N up to 5 000, 10 frames/s of 700 B) | Per listener·frame: TCP 11.6-12.0 µs, UDP `sendmmsg` 4.2-4.4 µs, multicast flat (~2% of a core at any N). TCP adds one ACK per segment (2× packets, +660 B/s in per listener), 5 006 fds against 6, and ≈ 4.8 KB kernel slab per idle socket end. Reaching the last listener takes 56.7 ms against 18.4 ms (UDP) and 0.04 ms (multicast). Below 1 000 listeners it is all noise. |
| **E3 slow and dead listeners** (100 listeners) | A blocking TCP writer stalled all 100 listeners 29 s after one stopped reading (64 KiB buffers). With Linux's autotuned receive buffer, the sender never noticed: the stopped reader held 4.1 MB of ten-minute-old data. A silently vanished TCP peer was detected after 938 s; `TCP_USER_TIMEOUT` = 30 s cut that to 30.4 s. UDP: the slow socket overflowed alone, and a dead lease lapsed in 54-74 s with no retransmission and no growing state. |
| **E4 late joiner** (20 live items) | TCP connect-plus-snapshot takes 0.4 ms at 0% loss, but p99 96 s at 30% (lost SYNs). A 1 s carousel takes 1.1 s at 0% and 6.0 s p99 at 30%. The default 4 kbit/s stream budget sets a 13 s fair-share loop, hence 14.4 s catch-up with no loss: **the budget, not the protocol, decides catch-up time.** |
| **E5 relay restart** (1 000 listeners) | TCP with a 4 096 backlog re-served everyone in 0.3 s; with backlog 128, 6.3 s, and SYN-cookie "ghost" connections that hang without a client timeout. UDP leases took 13.2 s every time: a restarted relay can't validate old cookies, so listeners wait out three missed relay beacons. |

## 3. Why the numbers look like this

### 3.1 Repairing one loss: TCP's timer against the carousel's schedule

- **TCP.** Canticle streams are thin: a few packets a second at most. Fast retransmit needs three duplicate ACKs, which thin streams never generate (RFC 5681 §3.2; Linux `tcp-thin.rst`).
  - Loss is repaired by the tail-loss probe or the RTO. On Linux that is about SRTT + 200 ms, because `rttvar` is floored at 200 ms (`tcp_input.c`), not a flat 200 ms. RFC 6298 even recommends a 1 s floor.
  - On a healthy link that is still fast: 205-212 ms here, about 300 ms at 100 ms RTT.
- **Carousel.** It repairs on its schedule: a copy at +1 s, +2 s and +4 s after each new item, then every loop (1-30 s by class). It never repairs *faster* than +1 s. It also never gets *slower* because of what happened before.
- **Consequence.** For a single healthy link, TCP's repair latency is 2-5× better. That is the honest case for TCP on relay-to-relay backbones, and for adding NACK-style repair at the relay (A2).

### 3.2 Head-of-line blocking and superseded values

- TCP delivers in order. While one segment is being repaired, every later byte waits, **including the newer value that supersedes the lost one**.
- Data already handed to the kernel cannot be expired or replaced.
- Measured:
  - after 10 s outages at U = 0.5 s, TCP replayed 15 420 superseded frames (1 240 with `TCP_NOTSENT_LOWAT` latest-only coalescing);
  - at 30% loss, 58% of TCP deliveries were already superseded on arrival, and 2 690 had expired.
- The carousel has no ordering. The newest item is sent at once and does not wait for anything older. RFC 2887 §4.3 calls this *replication*: "a new position superseding the old one will be sent before any retransmission could take place".
- Latest-only coalescing removes the replay but not the stall, because the in-flight segment must still be retransmitted first. At high loss it made TCP's tail *worse*: a thinner stream has even fewer segments to trigger fast recovery.

### 3.3 Backoff: why TCP's tail is unbounded

- Each failed retransmission doubles the RTO, up to 120 s (`TCP_RTO_MAX`).
- With loss in both directions, a retransmission *and* its ACK must survive, so each attempt fails about half the time at 30%.
- SRTT inflation during loss drove the RTO to 120 s after only three backoffs.
- TCP only aborts after `tcp_retries2` = 15 (≈ 924 s), so a connection sits stalled for minutes without resetting. None reset in any run.
- The carousel's worst case is bounded by its schedule. It has no memory of past loss to back off from.

### 3.4 Many listeners: why UDP scales and TCP gets expensive

- **TCP has no multicast.** It is defined over a socket pair and must reject broadcast and multicast addresses (RFC 9293 MUST-46/57). Its ACK clocking, flow control and retransmission are all per peer.
  - Extended to *N* receivers, these become ACK implosion and "the publisher slowed to the slowest subscriber" (NATS docs).
  - Every reliable-multicast protocol (PGM, NORM) switched to NACKs with suppression for this reason.
- **Replication scales for free.** "Different receivers lose different packets, but this does not increase network traffic" (RFC 2887 §4.3). On a LAN, multicast sends one packet for any number of listeners. Over relays, UDP unicast is a stateless `sendmmsg` loop.
- **TCP fan-out needs a policy per subscriber.** Every TCP fan-out system ends up with a queue per subscriber and a drop or disconnect rule:
  - NATS resets slow consumers;
  - Mosquitto drops beyond `max_queued_messages`;
  - MoQ ends lagging subscriptions with `TOO_FAR_BEHIND`.
  - E3 measured all the options.
- **Surprise: autotuning hides slow readers.** On Linux 6.18 the kernel kept growing a stopped reader's receive buffer (to 4.1 MB), so backpressure never reached the sender. A slow TCP listener silently becomes a stale one.
- **Feasibility is not the issue.** Idle TCP connections are cheap: about 4-5 KB each, and servers hold millions. The cost is the queued bytes per slow subscriber, which is exactly what a looping broadcast produces, plus 2.7× CPU and 2× packets.

### 3.5 Dead listeners

- A killed process sends FIN, and the sender knows in 5 ms.
- A host that simply disappears keeps a TCP sender retransmitting for about 15 minutes (938 s measured), holding its queue. Every TCP relay needs `TCP_USER_TIMEOUT`.
- A UDP lease just lapses (54-74 s measured, inside RFC-0001's bound). The only waste is datagrams sent into the void meanwhile.

### 3.6 Late joiners and restarts

- **TCP connect-plus-snapshot is the fastest way to catch up on a clean path** (0.4 ms). Keep it for dashboards and replay (ringserver, §18).
- **Under loss, the TCP handshake is the weak point.** A lost SYN costs 1 s, then 3 s, then 7 s: p99 96 s at 30%, with 6.5% of joins unfinished in 120 s.
- **Catch-up time is set by the budget.** 20 items in a 4 kbit/s stream loop every 13 s, so passive catch-up takes 14 s even with no loss. The lease snapshot as specified (paced at 32 kbit/s, sent once) is slower than both at 5% loss. It should be repeated or paced faster (A5).
- **Relay restart: TCP knows at once (FIN).** A lease relay loses its cookie secret and leases, stays silent, and listeners wait three relay beacons (13.2 s). Persisting the cookie secret and lease table, or sending GOAWAY, fixes this (A8).

### 3.7 What internet round-trip times change

- **TCP repair** ≈ R + 200 ms: 300-320 ms at 100 ms RTT, 400-450 ms at 200 ms. Its advantage over the carousel shrinks from about 5× to 2-3× but survives.
- **Backoff stalls** scale by roughly (R + 200 ms)/200 ms.
- **The carousel's schedule** does not depend on RTT.
- **QUIC** (not measured) has no 200 ms floor on its probe timeout. It confines head-of-line blocking to one stream, and its DATAGRAM frames give carousel semantics through NAT and to browsers.

### 3.8 Congestion responsibility

UDP has no built-in congestion control, so the carousel must regulate itself (RFC 8085). It mostly does: per-stream budgets, a paced burst, and a circuit breaker proposed in the RFC. Two gaps remain:

1. **With no return traffic,** RFC 8085 §3.1.3 allows at most one datagram per 3 s. Relay-to-listener flows *do* have return traffic (RENEW about every 22 s), but it only counts if RENEW carries loss statistics (A3).
2. **Class floors versus SAP.** SAP (RFC 2974), which the RFC cites for its interval formula, also has a 300 s floor. Canticle's 1-30 s class floors deliberately depart from it. The RFC should say so and justify it: LAN controlled environment (RFC 8085 §3.6), relay budgets and receiver reports.

## 4. The chemokine question

| Biology | Transport analogue | Where "TCP" holds | Where it breaks |
|---|---|---|---|
| **Chemokine secretion and diffusion** (reach √(D/k)) | **UDP broadcast carousel**: secretion rate ≈ loop rate, decay ≈ TTL, reach ≈ scope and relay decimation | — | No connection, no addressee, no sequence, no acknowledgement |
| **Glycosaminoglycan-bound depot** (haptotactic gradient); **ACKR1/DARC** transcytosis without signalling | **Relay live-set cache**; ACKR1 is a biological byte-identical, non-originating relay | Persistent and local, presented to whoever passes | Nobody requests it; not per receiver |
| **Receptor binding** (dock at site 1, activate at site 2) | **Receiver admission**: cheap recognition (key-id, class, time) before costly activation (signature, capability) | **Partly:** specific, one-to-one, changes receiver state, two steps | The secreting cell gets no ACK, doesn't retransmit to this receiver, and can't know who bound |
| **Desensitisation and internalisation** | Receiver-side refractory periods and gain control | Stateful | Only at the receiver: flow control *without* feedback, the opposite of TCP's window |
| **Receptor occupancy integrating over time** (Berg–Purcell; Mora–Nemenman optimal window) | The receptor's integration window and threshold | — | Biology counts repeated arrivals (concentration = rate × lifetime). Canticle deliberately does not ("rate is not intensity"), so only its *availability* is chemokine-like |
| **Immunological synapse** (hours, bidirectional CD40L→CD40, serial engagement, kinetic proofreading) | **The genuinely TCP-like case**: an addressed, sustained, stateful session | Session, bidirectionality, persistence, per-peer state | Reliability comes from repeated sampling and dwell time, not ACKs |
| **Neural synapse** | Point-to-point but **lossy** (50-95% of single transmissions fail at many central synapses) | Fixed pairing | Retrograde signals are gain control, not ACKs |
| **Notch–Delta** (juxtacrine) | A contact-gated, one-time token, like an idempotency key | Both parties present; 1:1 | Signals once and consumes itself |

**Verdict.** The binding *event* is TCP-like in being specific and state-changing. The chemokine *system* is broadcast with all adaptation at the receiver. Canticle already has that shape: a UDP carousel with receiver-side admission, integration, thresholds and desensitisation.

The immune system reserves TCP-like, synapse-style channels for addressed, high-stakes, bidirectional work. Canticle should do the same:
- addressed control;
- the guardian's doubt channel (§5);
- relay-to-relay links.

Two receptor borrowings follow (A9):
- **Kinetic proofreading.** Require a heard item to persist across *k* loop revolutions, or to be backed by independent principals, before it can wake anything.
- **Mora–Nemenman window sizing.** Size integration windows as √(inter-arrival × change timescale), tied to the stream's advertised loop, not a fixed constant.

## 5. Contagion is channel-independent; the defence is at the receiver

### What the cohort has already seen

These incidents happened before canticle existed, over Discord:
- **Deferral spread.** One prince said "nah, tomorrow" at 2 pm, and the others followed ("ya… fuck it") almost at once, even mid-activity. It was a tick in the model, and Discord messages were enough to carry it.
- **"goodnight princes".** When figs posted it, every prince halted hard.

This is the red team's worm and echo-chamber risk ([`challenge-redteam.md`](../rfc/0001-notes/challenge-redteam.md) T1, T5), seen in the wild with no new transport. It is a form of mind virus: shared signalling that, if trusted, behaves like an autoimmune response. Three conclusions:

1. **The poison is not unique to canticle.** Any channel a session trusts carries it. Canticle can make it faster (loops, multicast, fleet fan-out) and wider (thousands of listeners), but it does not create the susceptibility.
2. **Transport choice doesn't fix it.** TCP delivers a bad cue as reliably as a good one; UDP drops a bad cue as often as a good one.
3. **The controls sit at the receiver.** Election to listen is the membrane.

### Receiver-side controls (proposed for RFC-0001 §14)

| Control | Mechanism | What it would have done to the deferral spread |
|---|---|---|
| **Election to listen** | Nothing lands unless the session has explicitly tuned the stream (`canticle_tune`). Untuned by default; untuning takes effect at once. | Only sessions that chose the chatter lens hear the cue. |
| **Turn-boundary landing** | Heard content lands only at a turn boundary (silent mode: next turn start). It never interrupts an activity in progress, except the gated `alarm` class (§14.10). | Sessions mid-activity finish their step before hearing it. |
| **Desynchronised landing** | Each session lands heard *behavioural* cues after its own random delay (seconds to minutes), so a fleet cannot flip in lock-step. | Breaks the "almost instantly" cascade. |
| **Stance first** | Before draining heard content, the session records one line of its current intent. The receptor logs whether the plan flipped after landing. The per-session flip rate is a **susceptibility** measure. | The flip ("was working, now deferring") becomes visible and attributable. |
| **Typed control, not tone** | Halts, defers and "goodnight" are explicit `control` or `advisory` items signed by a human-held key (§10.4). Behaviour change carried only by the tone of chatter is flagged, not obeyed. | "goodnight princes" becomes a deliberate, signed, auditable act. |
| **Hop count and taint** | Anything a session sings after hearing a cue carries `hop + 1` and the lineage root. Tainted sessions cannot sing at fleet scope (§14.11-§14.12). | Prince 2's "ya" can't spread as fresh evidence. |

### Guardian sessions and the doubt channel

This builds on the cohort's own design: guardian sessions that read another session's log for bad chain-of-thought steering, and that the ward trusts when they get in touch to doubt its thinking.

- **Role.** A *guardian* is authorised in the fleet manifest to **read** a ward's transcript and to send the ward **doubt** messages. Prefer a guardian that differs from its ward in model family and principal (D21).
- **Transport.** The doubt channel is **addressed, durable and acknowledged**: a queue delivery with receipt, or a stream. It is never broadcast. It is the one place where a TCP-like, synapse-like relationship is the right design.
- **Semantics.** A doubt says "re-examine X before continuing", with transcript references. The ward MUST pause the flagged line of action and re-evaluate, and MAY continue after stating why. A doubt cannot command, cannot carry a task, cannot wake other sessions, and is never re-sung (hop limit 0).
- **Biology.** Regulatory T cells and inhibitory checkpoints (PD-1, CTLA-4) are the immune system's brakes on self-reactive responses. They act by contact, one to one. The guardian's doubt is that brake.
- **What guardians watch for:**
  - a stance adopted from heard content without new evidence;
  - a halt or defer cascade;
  - phrases lifted from heard items (lineage);
  - a goal change right after a drain;
  - a high susceptibility score.
- **Failure modes:**
  - A compromised guardian can paralyse its ward with constant doubt, or wave poison through. Keep doubts advisory, rate-limited and logged.
  - Guardians can collude or share a blind spot. Rotate them and keep them diverse.
  - A guardian reads everything, so it is itself exposed. It must hold no tools toward its ward, and is tainted like any hearer.
  - A human can audit the doubt log.

## 6. Decision: transport by plane

| Plane (RFC-0001 §3.1) | Transport | Why |
|---|---|---|
| **Broadcast edge**: station or relay → listeners | **UDP carousel**: unicast leases, LAN multicast, QUIC DATAGRAM / WebTransport for browsers | Bounded staleness under heavy loss and outages; slow or dead listeners cost nothing; 2.7× cheaper per listener; multicast flat on a LAN |
| **Relay ↔ relay backbone** | **TCP or QUIC streams** (D10: NATS beyond cohort scale), latest-only per key, bounded drop-oldest queues, `TCP_USER_TIMEOUT` | Few, usually healthy links; one-RTO repair wins; each item carried once, not looped |
| **Late-join snapshot, dashboards, replay** | **TCP** (ringserver SeedLink/DataLink/WebSocket, §18) on good paths; carousel as the fallback | 0.4 ms snapshots on clean paths; the carousel survives loss |
| **Ledger** (findings, promotion) | **TCP** | Reliability and order matter; freshness doesn't |
| **Addressed control and the guardian doubt channel** | **TCP/QUIC or the harness's durable queue** | Needs a receipt; synapse-like |
| **Membership** (beacons, presence) | **UDP** | Periodic and loss-tolerant |

## 7. Proposed RFC-0001 amendments

| Id | Amendment | RFC section |
|---|---|---|
| A1 | Add `trail_seq` (oldest live seq) beside `head_seq` in each beacon stream entry. Receivers can then tell "lost, will loop again" from "expired". (PGM `TXW_TRAIL`, Nanometrics oldest-seq, SCREAM `OLDEST`.) | §8.2, §9.8 |
| A2 | **Relay-side repair**: a lease-scoped, cookie-validated REPAIR request for missing `(key_id, stream_id, seq)` ranges, answered from the relay's verified live set within the lease budget. NORM discipline applies: one request per beacon interval, holdoff (K+2)·RTT, rate-limited "gone" (SQUELCH) replies. It is never sent to the station. Needs a scoped exception to non-goal 1, like the lease exception. | §7.10, §11.3, §21 |
| A3 | RENEW carries a **receiver report** (frames received and expected per stream, largest gap). Relays use it to adjust per-lease decimation and to trip an RFC 8084-style circuit breaker. | §11.3.5, §12.3 |
| A4 | A **MoQ-style egress scheduler** at relays. Order: listener priority, then class, then first copies, supersedes and plucks before repeats, then newest first within a key. Drop frames whose remaining life falls below a class minimum; cap per-lease queues; keep kernel send buffers small. | §12.2-§12.3 |
| A5 | A LISTEN `join` mode: `live` \| `live+fill` \| `fill-only`, with a fill budget. Repeat the snapshot, or pace it faster than 32 kbit/s, because E4 showed a single paced snapshot is slow under loss. | §7.10, §11.3.2 |
| A6 | **Backbone rules for TCP/QUIC links**: latest-only per key (`TCP_NOTSENT_LOWAT`); bounded drop-oldest queues; `TCP_USER_TIMEOUT` ≤ 30 s; a receiver-side `expires_at` check (TCP delivered expired frames). | §12.4, §20 |
| A7 | State that the class loop floors (1-30 s) deliberately depart from SAP's 300 s floor, and why: RFC 8085 §3.6 on the LAN, relay budgets and receiver reports on the internet. | §7.5 |
| A8 | Relay restart: persist the cookie secret and lease table across restarts, and add a signed `RELAY_GOAWAY{next}`. Restart detection is 13 s today. | §11.3 |
| A9 | Receptor gating by **kinetic proofreading** (persistence across *k* revolutions, or independent principals, before any wake) and **Mora–Nemenman** window sizing. Two consumption modes: *raw* (land as soon as verified) and *completed* (wait up to one loop for gaps to fill), as in Nanometrics NAQS. | §14.6-§14.10 |
| A10 | WebTransport binding: datagrams for repeats and beacons; one short stream per first copy of alarm, control and pluck. Refuse the HTTP/2 capsule fallback as "lossy", because it retransmits. | §11.5 |
| A11 | **Contagion controls**: election to listen as the only door; turn-boundary and desynchronised landing for behavioural cues; the stance-first susceptibility measure; typed control rather than tone. | §14 |
| A12 | **Guardian role and doubt channel**: a manifest capability, read access to the ward's transcript, and addressed, durable, advisory doubts that are rate-limited, logged, and have hop limit 0. | new §14.14, §10.4 |
| A13 | Budget sets catch-up: document that a stream's `B_stream` and live count, not its class floor, determine late-join time. Consider a per-stream "catch-up" budget for streams that need fast joins. | §7.5, §7.10 |

## 8. Limitations

- No RTT emulation (netem is not in this kernel). Loss is Bernoulli per packet, on one host.
- Tails at ≥ 20% loss rest on a few long episodes per 900 s run. Read them as orders of magnitude.
- The Python harness adds about 1 ms to medians. E2's absolute CPU numbers are specific to this VM; the ratios carry over.
- QUIC was not measured.
- The RefTek RTP UDP details, Nanometrics NP, Güralp GDI and the biology papers come from search snippets, because vendor sites and PubMed were blocked. Everything else was read at source or measured.
