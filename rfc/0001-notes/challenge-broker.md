# challenge-broker: "canticle should be a profile over an existing broker, not a new protocol"

Reader: broker (adversarial lens). Date: 2026-09-27. Repo baseline: `karmaterminal/binary-canticle` main `b46a45a`. Spine: `scratchpad/spine.md` (P1-P15, D1-D10). Read-only on every repo and on GitHub.

Legend: **[SAYS]** = a source states it. **[RAN]** = I measured it here (scripts and raw output in `scratchpad/brokerx/`). **[ASSESS]** = my judgement, with confidence HIGH, MED or LOW.

---

## 0. Bottom line

1. **The steelman mostly wins below the receptor, and mostly loses at and above it.** The relay tree, fan-out, NAT traversal for TCP listeners, connection auth, discovery and replay are solved problems. Canticle should borrow them. Nothing on the market lands a heard item into an agent's context under listener-chosen wake policy. Nothing does chemokine-style regulation either. Those two things, plus the carousel/carrier *profile*, are canticle. (HIGH)
2. **At the wire, canticle is a profile, not a new protocol.** Every mechanism in P1-P4 has a standards-track precedent:
   - loop until expiry: SAP RFC 2974 §3.1; FLUTE RFC 6726 §3.2-3.4.2; NOAA SAME ×3 headers;
   - absolute expiry: DDS LIFESPAN from the source timestamp; SAME origination + TTTT; FLUTE NTP `Expires`; MQTT 5, where the broker decrements the Message Expiry Interval;
   - carrier with "next beacon in N": MQTT-SN ADVERTISE `Duration`; RTPS SPDP announcement period plus lease;
   - deletion: SAP deletion packet; mDNS goodbye (TTL 0);
   - end-to-end signatures that survive relays: SAP auth header §8; CAP enveloped XML-DSig.

   What is new is the *bundle*: byte-identical signed loop + absolute expiry + keyed supersession + content-free carrier, tuned for agent context. The RFC should say so plainly and cite the precedents. (HIGH)
3. **No broker satisfies canticle's hardest wire invariants without payload-level help.** [RAN] The experiments show:
   - NATS JetStream `Nats-TTL` **restarts at a relay hop**: TTL 6 s, sourced into a second stream at t≈3.3 s, gone from the copy at **9.3 s** vs 6.0 s at the origin.
   - Sub-second TTLs are rejected (`err 10165`), and so are schedules under 1 s (`err 10189`).
   - NATS NKeys authenticate *connections*, not messages.

   So even over a broker, canticle must carry an absolute `expires_at` and an Ed25519 signature *inside* the frame, exactly as P4/P5 say. The broker becomes an opaque byte pipe plus garbage collector. (HIGH)
4. **The strongest pro-broker datum is late-joiner catch-up.** [RAN] A JetStream consumer with `DeliverLastPerSubject` delivered all 20 live items in **3.7 ms**. The loop-driven carousel, over raw UDP or NATS core, needed **≈1.0 s** (one `loop_ms`). With 30% loss the carousel needed up to **7.2 s**. For relays, P1's "catch up passively within one loop period" is strictly worse than a validated snapshot, which is SAP's proxy-cache pattern (RFC 2974 §9). See Deviation S1. (HIGH)
5. **Surprise: NATS 2.14 can run a server-side carousel.** [RAN] A message schedule (`Nats-Schedule: @every 1s`, `Nats-Schedule-Source`, `Nats-TTL` on the schedule):
   - re-emitted the **byte-identical** 712 B signed frame at 1.08/2.08/3.08/4.08 s;
   - stopped when the schedule's own TTL lapsed.

   Costs:
   - each firing is a *stored* stream message (seq 3→6);
   - core subscribers hear nothing unless the stream has RePublish configured (0 heard without it; 3 with it);
   - 1 s is the floor.

   So "loop" is borrowable in principle. It is not a good fit for per-item `loop_ms` with jitter at fleet scale. (HIGH that it works; MED on fit)
6. **Recommendation, per layer:**
   - **Build:** the frame profile (or borrow COSE_Sign1, +11 B), the edge membrane relay (the UDP lease is owner-required), the receptor, and the harness bindings.
   - **Borrow:** discovery (DNS-SD; already in the spine), the replay tier (ringserver; already in the spine), and — when there is more than one relay — the **relay-to-relay backbone (NATS)**.
   - Keep the edge raw UDP. (MED-HIGH)
7. **Relays among themselves: yes, borrow. NATS first, Zenoh second.** Loop at the edge relay, not across the backbone, so the backbone carries each item once, plus plucks and aggregated beacons. NATS gives:
   - Ed25519 JWT accounts that match P5's identity model;
   - leaf nodes that need no inbound reachability;
   - interest-only gateways;
   - WebSocket;
   - a 16.8 MB static binary.

   Zenoh is the better semantic fit (unreliable UDP links, per-key downsampling) but carries more integration risk. Do not build custom relay-to-relay chaining (P7) beyond a cohort. (MED)
8. **The repo's own comparator table is out of date.** "Pub/Sub (MQTT, NATS, Kafka) … Stateful broker; we're broker-less; we expire" (`proto/scope-framing-and-noosphere-mapping.md:244`):
   - MQTT 5 (2019) and NATS 2.11 both expire messages.
   - Canticle's own membrane relay (P6/P7) *is* a broker in all but name: it holds leases (= subscriptions), fans out and applies ACLs.

   Restate the differentiator as **"station-stateless; relays hold only soft state; items expire absolutely"**. (HIGH)

---

## 1. Method and access limits

- **Web.** WebFetch was egress-blocked for docs.oasis-open.org, www.oasis-open.org, www.ecfr.gov, govinfo.gov, www.omg.org, community.rti.com and steves-internet-guide.com (proxy 403). I did not route around these. WebSearch worked; facts sourced only from search excerpts are marked **(search)** and rated MED.
- **Primary sources, cloned from GitHub** (sparse, blobless) into `scratchpad/src/`, pinned:

  | Clone | Repository | Commit | Date |
  |---|---|---|---|
  | `nats.docs` | nats-io/nats.docs | `f115becf6563e3bbe16bb94cbf87bfceb84199c1` | |
  | `nats-adr` | nats-io/nats-architecture-and-design | `685743395fb8e2c912f1cbf2405db1ed5802c7ac` | |
  | `oasis-mqtt` | oasis-tcs/mqtt (MQTT-SN 2.0 CSD01 source) | `0eaa28ba66f296a3a59b0f827935ee3868497cd4` | 2026-09-17 |
  | `mosquitto` | eclipse-mosquitto/mosquitto | `6aaba32614eb1160ddbfeafd616f9f67e7914a41` | |
  | `paho-mqttsn` | eclipse-paho/paho.mqtt-sn.embedded-c | `e1e1b733e0fecef6bed92798d7f6d6440d9026f2` | |
  | `kafka` | apache/kafka (`docs/`) | `2a3d4a6b80507edefb1f969b3de6378235a5c34f` | |
  | `redisdocs` | redis/docs | `e9856ec64b12c23e492b63b2b341d8f83a4e09e8` | |
  | `libzmq` | zeromq/libzmq | `46493370217ac135246617fa2f6ac819d8b61bfc` | |
  | `fastdds-docs` | eProsima/Fast-DDS-docs | `b2af9caf0411a407a40d80622b1e6e43c9a41577` | |
  | `fastdds` | eProsima/Fast-DDS (PDP sources) | `1eb667d95f6fb6d9bc043794e0d276ad88060e8d` | |
  | `zenoh` | eclipse-zenoh/zenoh (v1.10.1) | `9fcd9cb5d364192c3e8a27e66de76f4bc750d1d5` | |
  | `zenoh-pico` | eclipse-zenoh/zenoh-pico | `d9b4eea486ea90bbeb61dd59cace7bac54a18562` | |

- **RFC text** comes from `tex2e/rfc-translater` @ `55f03a2295911c81b67875b793b3744417302f63`. It is extracted into `scratchpad/src/rfc2/` (RFCs 2974, 3208, 3926, 5382, 5740, 5775, 6726, 6762, 8866, 9052). The canonical source is `https://www.rfc-editor.org/rfc/rfcNNNN`.
- **Could not verify from primary text** (these are rated MED, from search or memory):
  - the MQTT 5.0 spec (OASIS host blocked). The expiry-decrement rule is confirmed by search *and* by the Mosquitto implementation.
  - 47 CFR 11.31 (SAME) and OASIS CAP 1.2 (search only).
  - the OMG DDS/RTPS specs (Fast DDS docs and source used instead).
  - zenoh.io performance claims (search only).
- **[RAN]** I built `nats-server v2.14.7` from source with Go 1.24.7 (`go install github.com/nats-io/nats-server/v2@v2.14.7`). Clients: `nats-py 2.16.0`, `eclipse-zenoh 1.10.1`, `PyNaCl 1.6.2`, `cbor2 6.1.4`. Everything ran on loopback on a 4-vCPU sandbox. No `tc`/netem was available, and I did not touch host nftables, so loss is emulated in the application (Bernoulli drop at receive).

---

## 2. The steelman, stated as strongly as I can

Every hard part of canticle outside the agent is already a mature product:

- **Topic addressing.** NATS subjects with `*`/`>` wildcards (`nats.docs/nats-concepts/subjects.md:107-124`) map `station.stream` 1:1.
- **At-most-once fire-and-forget.** Core NATS is "at most once" (`nats.docs/reference/faq.md:139`); so is Redis Pub/Sub (`redisdocs/content/develop/pubsub/_index.md:58-61`).
- **Fan-out to thousands, across regions, including through NAT.**
  - Clusters, and gateways "into a full mesh … superclusters" (`nats.docs/running-a-nats-service/configuration/gateways/README.md:5`).
  - Interest-only forwarding (`:67-69`).
  - Leaf nodes that "do not need to be reachable themselves" (`…/leafnodes/README.md:12`).
  - WebSocket for browsers (`…/websocket/README.md:3`).
- **Ed25519 identity.** NKeys are "based on Ed25519" (`…/securing_nats/auth_intro/nkey_auth.md:3`). JWTs are "signed … only using Ed25519" (`…/jwt/README.md:17`).
- **TTL and last-value.**
  - Stream `MaxAge` (`nats.docs/nats-concepts/jetstream/streams.md:31`).
  - Per-message `Nats-TTL` (2.11; `streams.md:58`, ADR-43).
  - `MaxMsgsPerSubject` = keep-last-N (`streams.md:43`).
  - Late-joiner snapshot via `DeliverLastPerSubject` (`consumers.md:96`).
  - KV with per-key TTL (ADR-48).
  - A server-side loop via schedules (ADR-51; 2.12/2.14).
- **MQTT 5.**
  - Its broker rewrites the Message Expiry Interval to the *remaining* life on every forward. This is the #51 invariant, implemented by the broker (Mosquitto `src/database.c:1370-1381`).
  - Retained messages give a last value to late joiners (`src/retain.c:218-223` deletes expired ones).
- **MQTT-SN.**
  - Connectionless UDP publish ("PUBWOS … without establishing a Virtual Connection or Session"; `oasis-mqtt/mqtt-sn-2.0/prose/edit/src/impl-guidance-06-publish-with-qos-minus-one.md:9-11`).
  - A periodic ADVERTISE beacon whose `Duration` tells listeners when to expect the next one (`impl-guidance-07-gw-advert-and-discovery.md:21`). That is a carrier beacon.
- **DDS/RTPS.** BEST_EFFORT, LIFESPAN anchored at the source timestamp, KEEP_LAST, TRANSIENT_LOCAL, SPDP multicast discovery with announcement period and lease, and DDS-Security.
- **Zenoh.**
  - Unreliable UDP links (`zenoh/io/zenoh-links/zenoh-link-udp/src/lib.rs:70`).
  - Multicast scouting on `224.0.0.224:7446` (`zenoh/DEFAULT_CONFIG.json5:145-173`).
  - Liveliness tokens (`zenoh/zenoh/src/api/liveliness.rs:34-43`).
  - A heartbeat carrying the last sequence number (`zenoh-ext/src/advanced_publisher.rs:77-103`).
  - Per-key-expression **downsampling in Hz** at routers (`DEFAULT_CONFIG.json5:364-393`), which is literally attenuation.

A canticle that ships its own lease protocol, cookie handshake, relay tree, relay-to-relay chaining, WebSocket egress and discovery re-implements all of this. It also inherits the security debt of doing so: the transport notes (§4) show a naive LISTEN relay is a perfect UDP reflector.

The owner's own OpenClaw RFC sets the bar. §4.6's **substrate-adoption rule** says: "prefer [an existing substrate] over bespoke transport. Bespoke pathing is acceptable only where a concrete direct or transitive functional reason is named … Seam-ugliness alone does not clear this bar" (RFC:879, via `notes/openclaw-rfc.md:62`).

The rest of this note applies that bar layer by layer.

---

## 3. Per-system evidence

### 3.1 NATS core

- **Subjects and wildcards.** [SAYS] `*` matches one token and `>` matches one or more trailing tokens (`subjects.md:107-124`). "Messages with no subscribers to their subject are automatically discarded" (`subjects.md:19`). The canticle mapping is `cnt.<keyid>.<stream>` for items and `cnt.<keyid>.beacon` for the carrier; `cnt.*.beacon` is a presence tap.
- **Fire-and-forget, but over TCP.** [SAYS] Core NATS is "at most once", "relying on reliable network transport protocol (i.e. TCP)". Loss shows up as disconnection, or as slow-consumer resets where the server is "'resetting' the connection with that client and purging the buffer" (`nats.docs/using-nats/jetstream/concepts/README.md:29-33`). The client protocol is text over "a regular TCP/IP socket" (`reference/nats-protocol/nats-protocol/README.md:5`). **There is no UDP transport.**
  - [ASSESS HIGH] This is the wrong loss model for the edge. Canticle wants each frame dropped independently under congestion. NATS either delivers everything late (TCP retransmit, head-of-line blocking) or drops a whole connection's buffer.
- **Leaf nodes, gateways, superclusters.** [SAYS]
  - Leaf nodes "transparently route messages … to one or more remote NATS system(s)" and "do not need to be reachable themselves" (`leafnodes/README.md:3,12`).
  - Gateways form a full mesh with interest-only forwarding (`gateways/README.md:5,67-69`).
  - [ASSESS HIGH] This *is* P6's "the lease lives in the relay, never the station", productised, with NAT traversal by outbound TCP. RFC 5382 REQ-5 makes established TCP NAT mappings last ≥ 2 h 4 min, versus UDP mappings of ≥ 2 min (RFC 4787 REQ-5) and Linux conntrack's 30 s default (transport notes §3.1).
- **WebSocket.** [SAYS] Supported since 2.2, binary frames only (`websocket/README.md:3-9`). This is an earlier browser path than P6(e)'s WebTransport.
- **NKeys/JWT.** [SAYS] NKeys authenticate by having the client "digitally sign a challenge" per connection (`nkey_auth.md:3-5`). All JWTs are Ed25519-signed (`jwt/README.md:17,53`).
  - [ASSESS HIGH] This is **connection authentication**. A frame that passes through a leaf node and a gateway arrives with no proof of which station key produced it; receivers trust the server mesh. P5's per-frame Ed25519 must stay.
  - Subject publish permissions can enforce "only key K may publish `cnt.K.>`" at the relay. That is useful defence in depth and cheap to borrow.
- **Footprint.** [SAYS] "binary is very compact (less than 20 MB)" (`running-a-nats-service/introduction.md:1`). [RAN] The v2.14.7 binary is 23,972,540 B unstripped and **16,813,984 B stripped**. RSS was **15.8 MB idle** and **21.7 MB** with 51 connections carrying a 20-item, 1 Hz, 712 B carousel (`brokerx/results/b_rss.txt`).
  - [RAN] Protocol overhead is a 26 B `PUB` line and a 28 B `MSG` line per 712 B frame, about 4% (`brokerx/results/b_varz.txt`: 496 in, 355,136 B).

### 3.2 NATS JetStream

- **Guarantees.** [SAYS] JetStream exists to add "at least once" and "exactly once" (`concepts/README.md:37`). That is the opposite of lossy. Use it only as a relay-side state store, never on the edge path.
- **`max_age` and per-message TTL.** [SAYS]
  - `MaxAge` is per stream (`streams.md:31`). `AllowMsgTTL` is 2.11 and can only be enabled, never disabled (`streams.md:58`).
  - The `Nats-TTL` "duration will be used by the server to calculate the deadline for removing the message **based on its Stream timestamp**" (`nats-adr/adr/ADR-43.md:28`). The minimum is 1 s (`:32-35`, `:105`). `never` is allowed (`:30`).
  - `SubjectDeleteMarkerTTL` leaves a tombstone marker (`Nats-Marker-Reason: MaxAge`) when the last value of a subject ages out (`:38-51`).
  - Sources and mirrors "always accept and store messages with `Nats-TTL`" (`:80`).
  - [RAN] **The TTL restarts at a Sources hop.** SRC got `Nats-TTL: 6s` at t=0. DST (sourcing SRC) was created at t=3 and first held the copy at 3.26 s. SRC dropped it at **6.03 s**; DST dropped it at **9.30 s**. The copy's header still reads `Nats-TTL: 6s` (`brokerx/results/j_out.txt`, J2).
  - ⇒ A broker TTL does not preserve remaining life across relays. It is a garbage-collection upper bound, and it must be set to `ceil(expires_at − now)` at each hop. Receivers must enforce the frame's own `expires_at`.
- **KV with TTL.** [SAYS] History is `max_msgs_per_subject` (`ADR-8.md:240`). Per-key TTL has existed since 2.11 (`ADR-8.md:436-440`), but only on `Create()` and `Purge()`, "do not accept a TTL for other API … a TTL on `Put()` might mean older revisions could come back from the dead" (`ADR-48.md:58-70`).
  - [ASSESS MED] For supersede-by-key live-state (P2), publish to the stream subject directly with `Nats-TTL` rather than going through the KV `Put` API.
- **`DeliverLastPerSubject` as a carousel equivalent.** [SAYS] "Start with the latest message for each filtered subject" (`consumers.md:96`). KV watch uses `last_per_subject` by default (`ADR-8.md:375,434`).
  - [RAN] A stream with `max_msgs_per_subject=1`, `allow_msg_ttl`, and 20 items published once: an ordered consumer received all 20 in **3.7 ms** (J1). The loop-driven arms needed about 1 s.
  - [ASSESS HIGH] The functional equivalent of a carousel for *attached* relays is a snapshot plus a live tail. Loop bandwidth is paid only where there is no back-channel: LAN multicast, and leased UDP listeners.
- **Schedules as a server-side loop.** [SAYS]
  - `Nats-Schedule` (cron, `@every`), `Nats-Schedule-Source` ("read the last message on the given subject and publish it"), `Nats-Schedule-TTL`, `Nats-Schedule-Target` (`nats.docs/nats-concepts/jetstream/headers.md:83-96`; `ADR-51.md:118-160`).
  - "The minimum supported interval is `1s`" (`ADR-51.md:124`).
  - "`MaxAge` shorter than the firing interval deletes the schedule … prefer `Nats-TTL` on the schedule itself" (`ADR-51.md:277`).
  - [RAN] (J3/J3b/J4)
    - Byte-identical re-emission: yes.
    - Loop stops at the schedule's TTL: yes.
    - Each fire is a new stored message: stream seq 3→6.
    - Core subscribers heard **0** fires without RePublish and **3** with `republish {src: ronair.>, dest: live.>}`.
    - `@every 500ms` was rejected (err 10189), and `Nats-TTL: 500ms` was rejected (err 10165).
  - [ASSESS MED] One schedule subject per item, a 1 s floor, no jitter, and storage per fire make this a poor carousel engine at fleet scale. It is a clever proof that "loop until TTL" is not exotic.

### 3.3 MQTT 5

- **QoS 0.** At-most-once, but over TCP or WebSocket to a broker (spec text unverifiable here; OASIS host blocked).
- **Message Expiry Interval.** [SAYS (search)] "The PUBLISH packet sent to a Client by the Server MUST contain a Message Expiry Interval set to the received value minus the time that the Application Message has been waiting in the Server" (MQTT 5.0 §3.3.2.3.3; EMQ, HiveMQ and RabbitMQ pages in search results).
  - [SAYS, code] Mosquitto stores the absolute `expiry_time = now + interval` (`mosquitto/src/database.c:1014-1016`). On send it computes `expiry_interval = expiry_time − now`, and drops the message if it has expired (`:1370-1381`).
  - [ASSESS HIGH] MQTT 5 preserves remaining life across broker hops (bridges included). On this invariant it is **better than NATS**.
- **Retained messages.** [SAYS, code] One retained message per topic. It is delivered at subscribe time and deleted once expired (`mosquitto/src/retain.c:218-223`; `man/mosquitto.conf.5.xml:1234-1243` `retain_expiry_interval`).
  - [ASSESS] This is a last-value snapshot per topic, i.e. P2 live-state keyed by topic. It is not a loop, and every item needs its own topic.
- **Topic aliases.** [SAYS (search)] Aliases are per network connection and are not session state.
  - [ASSESS HIGH] They save bytes only on a long-lived connection. They are irrelevant to connectionless frames. Canticle's u32 `stream_id` plus 8 B key-id already does this job.
- **Auth.** Connection-level (username/password, enhanced AUTH). There are no per-message signatures (MED, spec not read).

### 3.4 MQTT-SN over UDP (v1.2 and 2.0 CSD01)

- **Status.** [SAYS] MQTT-SN 2.0 is "Committee Specification Draft 01", 01 May 2025 (`oasis-mqtt/mqtt-sn-2.0/prose/edit/src/frontmatter.md:7,71`).
- **Connectionless publish.**
  - [SAYS] PUBWOS "does not need to have an active Session". If forwarded to MQTT it MUST be QoS 0 (MQTT-SN-3.6-1). "can be optionally discarded by the Server". "can be sent using a multicast address" (`ctrl-pack-catalog-06-publish.md:5,18,28-38`).
  - [SAYS] v1.2's QoS −1 is the equivalent: "publish data to a topic without establishing a Virtual Connection or Session" (`impl-guidance-06-publish-with-qos-minus-one.md:9-11`).
  - [SAYS, code] Paho's gateway implements it as a *QoS-1 proxy*, keyed by pre-registered sender address in a clients file (`paho-mqttsn/MQTTSNGateway/src/MQTTSNGWClientList.cpp:109-161`; `gateway.conf:43` `QoS-1=NO` by default).
- **ADVERTISE, SEARCHGW, GWINFO.** [SAYS] (`impl-guidance-07-gw-advert-and-discovery.md:7-29`):
  - "The Gateway can periodically transmit, or broadcast, an ADVERTISE packet".
  - "The time until the Gateway sends the next ADVERTISE packet is indicated in the *Duration* field … if it does not receive ADVERTISE packets … several times (*[Advertise Count]*) consecutively, it may assume that the Gateway is down".
  - Stand-by gateways "can become active … if they fail to observe successive advertisements".
  - SEARCHGW uses a random delay and cancels if another client sends the same one. GWINFO has a random delay, with gateway priority and suppression.
  - [SAYS, code] Paho re-arms ADVERTISE every `KeepAlive` seconds and puts `keepAlive` in the Duration field (`MQTTSNGWPacketHandleTask.cpp:125-129`; `MQTTSNGWConnectionHandler.cpp:42-49`). Multicast defaults to `225.1.1.1`, TTL 1 (`gateway.conf:57-60`).
  - [ASSESS HIGH] This is the closest existing thing to P3's carrier-beacon. **Borrow the `Duration` idea** (see Deviation S3). The difference: ADVERTISE announces a *gateway*, not stream heads, and it is unsigned.
- **Security.** [SAYS] 2.0's Protection Encapsulation identifies the sender, and "This responsibility MUST NOT be delegated to … a Forwarder" (MQTT-SN-3.17-1). But every scheme is symmetric: HMAC-SHA256/SHA3, CMAC, AES-CCM/GCM, ChaCha20-Poly1305, plus provider-defined values (`ctrl-pack-catalog-17-protection-encapsulation.md:7-9,111,119-141`).
  - [ASSESS HIGH] Symmetric per-packet tags let any key holder forge. That is exactly why the spine drops shared HMAC (P5).

### 3.5 Kafka compacted topics

- [SAYS] Log compaction "retain[s] at least the last known value for each message key" (`kafka/docs/design/design.md:368`). A null payload is a tombstone, kept for `delete.retention.ms` (default 24 h) (`:411,424`). Consumers pull (`:139-147`).
- [ASSESS HIGH] Kafka is the canonical keyed last-value log (compare P2 live-state), and a fine *ledger* backend. It has no per-record TTL (retention is per topic), no loss model, a pull protocol and a JVM broker. Nothing at the edge fits.

### 3.6 Redis Pub/Sub and Streams

- [SAYS] Pub/Sub is "at-most-once … If the subscriber is unable to handle the message … the message is forever lost" (`redisdocs/content/develop/pubsub/_index.md:58-61`).
- [SAYS] Streams trim with `MAXLEN`/`MINID` (`content/commands/xadd.md:49-54,118`). There is no per-entry TTL.
- [SAYS] Hash fields support an **absolute** expiry, `HEXPIREAT` (7.4.0; `content/commands/hexpireat.md:79-80`).
- [ASSESS MED] A hash of live items with `HEXPIREAT = expires_at` is a clean relay-side live-set store that never resets remaining life. It is still TCP, still a server, and has no loop and no signatures.

### 3.7 ZeroMQ: PUB/SUB, RADIO/DISH, PGM/NORM

- **RADIO/DISH over UDP.** [SAYS] "UDP transport can only be used with the 'ZMQ_RADIO' and 'ZMQ_DISH' socket types" (`libzmq/doc/zmq_udp.adoc`). Groups are ≤ 16 characters with exact match. "Radio-dish is still in draft phase" (`doc/zmq_socket.adoc:149-164`).
  - [ASSESS] Lossy and brokerless, but draft. It has no relay, no NAT story (the DISH must be reachable) and no loop.
- **Security.** CURVE is a client/server "mechanism for secure authentication and confidentiality" (`doc/zmq_curve.adoc:9-16`). It is connection-oriented, and `zmq_udp.adoc` defines no security for UDP.
- **PGM and NORM.** [SAYS]
  - PGM receivers "unicast selective negative acknowledgments (NAKs)" and network elements forward them hop by hop (RFC 3208 §1.1). ZeroMQ's `pgm` "requires access to raw IP sockets" (`doc/zmq_pgm.adoc`).
  - NORM is "centered around the use of selective NACKs" (RFC 5740 §1.3). ZeroMQ NORM options exist (`include/zmq.h:657-661`).
  - [ASSESS HIGH] Both are reliable multicast *with a back-channel*. That violates P1's "no back-channel to the station". The carousel is canticle's feedback-free alternative.

### 3.8 DDS / RTPS

- **BEST_EFFORT.** [SAYS] BEST_EFFORT means it "is acceptable not to retransmit the missing samples" (`fastdds-docs/docs/fastdds/dds_layer/core/policy/standardQosPolicies.rst:1083`).
- **LIFESPAN.** [SAYS] "The expiration time is computed by adding the `duration` to the source timestamp … The DataReader is allowed to use the reception timestamp instead" (`:535-548`). This is absolute expiry, with a reader escape hatch.
- **KEEP_LAST** keeps the most recent values per instance (`:437-441`). This is keyed supersession, as in P2.
- **TRANSIENT_LOCAL.** [SAYS] With TRANSIENT_LOCAL, "When a new DataReader joins, its History is filled with past samples" (`:200`). **But** "Setting [reliability] to BEST_EFFORT … affects … Durability, making the endpoints behave as VOLATILE" (`:1068-1070`).
  - [ASSESS HIGH] DDS's late-joiner mechanism requires RELIABLE: ACKNACK/HEARTBEAT and per-reader state at the writer. That is the exact opposite of P1. The DDS feature that *is* a carousel is SPDP.
- **SPDP.** [SAYS] Participants re-announce every "Announcement Period" (default 3 s) inside a "Lease Duration" (default 20 s) (`docs/fastdds/discovery/general_disc_settings.rst:26-34,134-170`).
  - [SAYS, code] Fast DDS arms a `resend_participant_info_event_` timer for it (`fastdds/src/cpp/rtps/builtin/discovery/participant/PDP.cpp:549,1498-1502`).
  - The default metatraffic port is `7400 + 250·domain` (`include/fastdds/rtps/common/PortParameters.hpp:38-41,75`).
  - SPDP is the RTPS carrier. The repo rightly rejects the rest of DDS discovery (SEDP endpoint matching): "No participant-table / DDS-style discovery" (`proto/explicit-non-goals.md:87`).
- **DDS-Security.** [SAYS] PKI-DH uses a CA, ECDSA and an ECDH-established shared secret. The crypto is AES-GCM/GMAC (`docs/fastdds/security/auth_plugin/auth_plugin.rst:25-29`; `crypto_plugin/crypto_plugin.rst:23-35`).
  - [ASSESS HIGH] Keys are pairwise and symmetric, set up by per-pair handshakes. There is no per-sample signature that survives a routing service.
- **TIME_BASED_FILTER.** [SAYS] This is a reader-side attenuation QoS, but in Fast DDS it "will be implemented in future releases" (`standardQosPolicies.rst:1225-1231`).

### 3.9 Zenoh

- **Pub/sub/query and routers.** [SAYS] The default mode is `peer`; routers listen on `tcp/[::]:7447` (`zenoh/DEFAULT_CONFIG.json5:11-12,104`). Multicast scouting uses `224.0.0.224:7446` with autoconnect and gossip scouting (`:139-179`). The multicast transport sends a JOIN every 2.5 s (`:583-586`), which is another carrier precedent.
- **UDP links.** [SAYS, code] Unreliable by default (`IS_RELIABLE = false`, `io/zenoh-links/zenoh-link-udp/src/lib.rs:70`). But the default Linux UDP MTU is `u16::MAX − 8 − 40` = 65,487 B (`:46-61`).
  - [ASSESS HIGH] Out of the box it relies on IP fragmentation. `batch_size` must be ≤ 1200 to honour P4's "never fragment".
- **Overhead.** [SAYS (search)] zenoh.io claims "a minimal wire overhead of 5 bytes". zenoh-pico claims "less than 50KB footprint … reduced to ~15KB" (zenoh.io blog). Not verified here.
- **Regulation.** [SAYS] Router-side `downsampling` rules take a key expression and a maximum frequency in Hz (`DEFAULT_CONFIG.json5:364-393`). There is also a `low_pass_filter` payload size limit (`:505-531`), `access_control` (`:397`) and per-key QoS overwrite (`:275-336`).
  - [ASSESS HIGH] This is the closest off-the-shelf thing to P7's membrane. It limits frequency per key, not per-station byte budget, TTL cap or signature verification.
- **Presence and late joiners.** [SAYS] `LivelinessToken` "is tied to the Zenoh Session and can be monitored by remote applications" (`zenoh/src/api/liveliness.rs:34-43`). AdvancedPublisher offers a `cache` for history, `sample_miss_detection`, and a periodic `heartbeat` that sends "the last published sample's sequence number" (`zenoh-ext/src/advanced_publisher.rs:77-103,197-221`). That is P3's `head_seq`. But history is fetched by *querying* the publisher's cache, which is a back-channel to the station.
- **Auth.** [SAYS] `usrpwd` and `pubkey` operate at the transport level (`DEFAULT_CONFIG.json5:775-795`). There is no per-message signature.
- **Measured.** [RAN] Python peers over a `udp/127.0.0.1:7449` unreliable link: a late subscriber heard all 20 looped items in 0.996 s. RSS was 31.5 MB per Python peer, interpreter included (`brokerx/results/z_*.txt`).

### 3.10 SAP, RFC 2974: the closest precedent to the carousel

- **The loop.** [SAYS] "The time period between repetitions of an announcement is chosen such that the total bandwidth used by all announcements on a single SAP group remains below a preconfigured limit … 4000 bits per second" (§3.1). The rule is `interval = max(300; (8·no_of_ads·ad_size)/limit)` with `offset = rand(interval·2/3) − interval/3`, and "At time tn the announcer SHOULD recalculate … This reconsideration prevents transient packet bursts on startup and when a network partition heals" (§3.1).
- **Deletion.** [SAYS] (§4):
  - explicit timeout from the payload's end time, i.e. absolute;
  - implicit timeout at "ten times the announcement period, or one hour, whichever is the greater";
  - an explicit deletion packet, which "SHOULD have a valid authentication header, matching" the announcements.
- **Authentication.** [SAYS] A modification must be "signed by the same key", or the listener treats it as a new, different announcement (§5). The signature is "calculated over the entire packet" (§8). The authentication header supports PGP or CMS (§8.1-8.2).
- **Proxy caches.** [SAYS] "When a new SAP listener starts, it should contact its local proxy to download this information … as if it has been continually listening" (§9).
- [ASSESS HIGH] SAP is P1 (loop), P1-pluck (deletion), P5 (same-key rule, "Changes must be signed by the original key") and P7 (bandwidth-scaled attenuation) in one experimental RFC from 2000. Canticle should cite it as the direct ancestor and adopt three of its rules (Deviation S2).

### 3.11 FLUTE/ALC data carousels

- [SAYS] ALC gives "No feedback packets are required from receivers to the sender" and "no difference in load … if one receiver or a million" (RFC 5775 §1.2). FLUTE "does not require connectivity from receivers to a sender" (RFC 6726 §1.1.3).
- [SAYS] Every FDT Instance "MUST contain the 'Expires' attribute" (§3.4.2). Its value is the top 32 bits of an NTP timestamp (§3.3), so it is absolute. "A certain FDT Instance may be repeated multiple times during a session" (§3.2). The sender should "repeatedly transmit … FDT Instances" because receivers will miss packets (§3.3).
- [SAYS] ALC "RECOMMENDED … some packet authentication scheme", naming RFC 5776 (TESLA) and RMT-SIMPLE (published as RFC 6584, which is from memory) (RFC 5775 §2.5).
- [ASSESS] This is the precedent for P4's future "multi-part carousel with FEC". Reuse RaptorQ (RFC 6330) and the FDT idea there; do not invent.

### 3.12 NOAA Weather Radio SAME and CAP

- **SAME.** [SAYS (search), 47 CFR 11.31]
  - The header `ZCZC-ORG-EEE-PSSCCC+TTTT-JJJHHMM-LLLLLLLL-` is sent three times.
  - A header is valid only if "two of the three headers match exactly".
  - `+TTTT` is the valid period "in 15 minute segments up to one hour and then in 30 minute segments".
  - Expiration is "Origination Date/Time plus Valid Time TTTT".
- **CAP 1.2.** [SAYS (search)]
  - `msgType` Update "supersedes the earlier message(s) identified in `<references>`"; Cancel "cancels".
  - `<info><expires>`.
  - "The `<alert>` element … MAY have an Enveloped Signature, as described by XML-Signature".
- [ASSESS HIGH] Between them they give:
  - absolute expiry that relays cannot extend (SAME);
  - repetition as a code (2-of-3);
  - supersession by reference (CAP Update/Cancel);
  - an end-to-end signature that survives any relay (CAP XML-DSig).

  The repo already calls the NOAA model "The exact interaction model; we adopt this directly" (`proto/scope-framing-and-noosphere-mapping.md:249`). The spikes reader flagged the "Network Weather Service" misnaming (`notes/spikes.md` §2.3).

### 3.13 mDNS announcements and goodbyes

- [SAYS] A responder "MUST send at least two unsolicited responses, one second apart … MAY send up to eight … interval … increases by at least a factor of two" (RFC 6762 §8.3).
- [SAYS] Goodbye: "RR TTL of zero … causing that cache entry to be promptly deleted". Receivers "record a TTL of 1 and then delete the record one second later" (§10.1).
- [SAYS] Cache refresh: queries at 80/85/90/95% of lifetime, and "If an answer is received, then the remaining TTL is **reset**" (§5.2).
- [ASSESS HIGH]
  - The goodbye is the precedent for UNEQUIP and for a station's last-gasp beacon.
  - mDNS TTLs are relative and refreshable, which is the *opposite* of the #51 invariant. Keep DNS for "where", not for liveness or item life (transport notes R5.2 already say this).

---

## 4. Fit matrix

Legend: Y = native fit. P = partial, or only with a canticle-side convention. N = no.

| Requirement → / System ↓ | Lossy by design | Loop to TTL, life not reset | Carrier/presence | No subscriber state at sender | Internet listeners behind NAT | Per-message Ed25519 surviving relays | Relay fan-out to 1000s | Membrane/attenuation | SeedLink dashboards | Tiny footprint on agent host | Harness-native landing |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NATS core | P (TCP; slow-consumer resets) | N | N (convention on a subject) | Y (server holds interest) | **Y** (outbound TCP, leaf nodes, WS) | N (conn-level NKeys) | **Y** | P (permissions, no downsampling) | N (bridge) | P (16.8 MB binary, 16-22 MB RSS) | N |
| NATS JetStream | N (at-least-once) | P (Nats-TTL ≥ 1 s, **resets per hop** [RAN]; schedules loop ≥ 1 s, stored per fire [RAN]) | P (delete markers) | Y at station | Y | N | Y | P (limits, per-subject max) | N (it is a *replay tier*, like ringserver) | N (storage) | N |
| MQTT 5 | P (QoS 0 over TCP) | P (**expiry decremented per hop**; retained = last value; no loop) | P (Will/retained convention) | Y | Y | N | Y | P (broker-specific) | N | P | N |
| MQTT-SN | **Y** (UDP, PUBWOS/QoS −1) | N | **Y** (ADVERTISE + Duration) | Y (PUBWOS) | P (needs gateway session to receive) | N (symmetric tags only) | P (via gateway→broker) | N | N | **Y** | N |
| Kafka (compacted) | N | N (last-value, no per-record TTL) | N | Y | P (heavy clients) | N | Y (pull) | P (quotas) | N | N | N |
| Redis Pub/Sub + Streams | P (at-most-once, TCP) | N (P: HEXPIREAT absolute on hashes) | N | Y | Y | N | P | N | N | P | N |
| ZeroMQ RADIO/DISH, PGM/NORM | Y (UDP, draft) / N (PGM/NORM NAK back-channel) | N | N | Y | N | N (CURVE is conn-level; none on UDP) | N | N | N | Y (library) | N |
| DDS/RTPS | Y (BEST_EFFORT) | P (LIFESPAN absolute; TRANSIENT_LOCAL needs RELIABLE) | **Y** (SPDP period + lease) | N (per-reader state when reliable; SEDP) | N/P (needs discovery server/routing service) | N (pairwise symmetric) | P | P (TIME_BASED_FILTER, unimplemented in Fast DDS) | N | N | N |
| Zenoh | Y (unreliable UDP link; fragments by default) | N (history by query) | Y (liveliness, JOIN, heartbeat seq) | P | Y (routers, outbound links) | N (transport auth) | Y | **P+** (per-key Hz downsampling, size filter, ACL) | N | P (pico tiny; full stack not) | N |
| SAP RFC 2974 | Y | **Y** (loop; absolute end time; deletion) | P | Y | N (multicast; proxies) | **Y** (PGP/CMS over packet; same-key rule) | N | **Y** (bandwidth-scaled interval) | N | Y | N |
| FLUTE/ALC | Y (no feedback) | Y (FDT repeat; absolute NTP Expires) | N | Y | N | P (TESLA / RFC 6584) | Y on multicast | P (layered CC) | N | P | N |
| SAME / CAP | Y | **Y** (×3; origination+TTTT; Update/Cancel) | P | Y | P (radio; CAP feeds) | P (CAP XML-DSig; SAME none) | Y (broadcast relay chain) | N | N | Y | N |
| mDNS | Y | N (refresh **resets** TTL) | Y (announce + goodbye) | P (query/response) | N (link-local) | N | N | N | N | Y | N |
| **Canticle (spine)** | Y | Y (P1) | Y (P3) | Y (P1/P6) | Y (P6c lease) | Y (P4/P5) | Y (P15) | Y (P7) | Y (P14 via ringserver) | Y (receptor daemon) | **Y (P9-P12)** |

**Reading the matrix.** No row covers even the eight wire and relay columns. The last column is empty for every system; it is canticle's own contribution. The columns where brokers beat canticle's current plan are "internet listeners behind NAT" and "relay fan-out to 1000s", which are NATS's strongest cells, and late-joiner catch-up (JetStream, measured). The columns canticle must keep regardless are per-message signatures that survive relays (only SAP and CAP have them, and neither is a live transport) and absolute remaining life across hops (MQTT 5 comes closest).

SeedLink compatibility is neutral. No broker speaks SeedLink, so every design needs a bridge into ringserver: a DataLink writer (P14). A NATS subscriber that writes DataLink is as simple as a UDP one.

---

## 5. Control experiment

### 5.1 What I ran (loopback, scripts in `scratchpad/brokerx/`)

**Common setup.** `frame.py` (42 LOC) produces one signed 712 B frame per item: magic + det-CBOR int-keys + key-id + Ed25519. It carries a 600 B body, so the overhead is 112 B. Twenty items loop at `loop_ms` = 1000 with ±10% jitter. Fifty listeners join late (5 s after start) and record the time to first hear each item. They check that a repeat never changes `expires_at`. They verify every signature, and none failed.

| Arm | What | LOC (Python) | Late joiner, all 20 items | Loss behaviour | RSS | Notes |
|---|---|---|---|---|---|---|
| A. Raw UDP station → minimal relay (verify + lease fan-out) → 50 leased listeners | `station.py` (54) + `relay_udp.py` (43) + `listener.py` (74) | 171 incl. listener | p50 0.30 s, p95 0.95 s, max **0.97 s** | 30% emulated loss: p50 0.54 s, p95 2.43 s, max **7.21 s** (tail ≈ 0.3^k per loop); frames drop independently | relay 18.3 MB, station 23.7 MB (Python + PyNaCl + cbor2) | Relay: 801 in → 53,000 out to 100 leases, 0 bad. No cookie, so a reflector (see transport notes §4). |
| B. Same station loop over NATS core → nats-server → 50 subscriber connections | same station with the `nats` backend | +2 lines | p50 0.59 s, p95 0.94 s, max **1.02 s** | not emulated. TCP turns loss into delay/HOL; overload means slow-consumer disconnect (docs) | nats-server 15.8 MB idle → 21.7 MB loaded | ~4% protocol overhead; NAT, auth, TLS, WS all come free |
| C. JetStream: publish once, `Nats-TTL`, `max_msgs_per_subject=1`, `DeliverLastPerSubject` | `exp_js.py` J1 | ~15 lines | **3.7 ms** | none on the wire (storage) | server as above | zero loop bandwidth to attached consumers |
| C'. JetStream schedules as carousel | `exp_js.py` J3/J3b/J4 | ~10 lines | ≤ 1 s (1 s floor) | n/a | | byte-identical, stops at the schedule TTL, stored per fire, needs RePublish for core subscribers |
| C''. TTL across a relay hop (Sources) | `exp_js.py` J2 | | | | | **TTL restarts: gone at 9.3 s instead of 6.0 s** |
| D. Zenoh 1.10.1 peers over an unreliable UDP link | `zenoh_probe.py` (39) | ~20 lines | max **0.996 s** | not emulated; best-effort link | 31.5 MB per Python peer | default UDP batch MTU 65,487 B must be lowered |
| Envelope alternative | COSE_Sign1 (RFC 9052) with `kid` vs the custom trailer | | | | | 723 B vs 712 B (+11 B) |

**What the numbers say** [ASSESS]:

1. **Late-join latency is set by the carousel, not by the transport.** A, B and D all land at about one loop period. Only a stateful snapshot (C) beats it, and it beats it by two orders of magnitude. (HIGH)
2. **Footprint is a wash in Python, and a real cost only if you add a server per host.** nats-server is 16-22 MB. That is small for a relay and too heavy to mandate on every agent host just for loopback and LAN, where a UDP socket inside the receptor daemon costs nothing extra. (HIGH)
3. **Complexity.** The UDP arm's relay is 43 lines *without* the cookie, pacing, budgets, attenuation, relay chaining, TLS and browser egress. The transport notes (§4-5) and P6/P7 show those are where the effort and the security risk live. NATS gives the relay-tree half of that list for free and none of the membrane half. (MED-HIGH)
4. **Loss semantics differ in kind.** UDP arms degrade gracefully: each loop is an independent chance (30% loss → p95 2.4 s). TCP arms preserve every byte but add latency. Under sustained overload NATS cuts the whole connection (`concepts/README.md:33`), a correlated loss burst that is worse for "hear what is current" than independent drops. For *relay↔relay* links (few, fat, low-loss) that trade is acceptable. For Wi-Fi and internet *edges* it is not. (MED-HIGH)

### 5.2 Spike to run before RFC-0001 freezes P6/P7

Name it S4a, "broker control". Run it under D10.

- **Topology.** Docker network namespaces: 1 station, 2 relays (a "region" and an "edge"), 200 listeners in 4 containers.
- **Impairment.** netem, in a namespace we own, not the host: 0/2/10/30% Bernoulli loss, Gilbert-Elliott bursts, 20-150 ms RTT.
- **NAT.** One listener container behind MASQUERADE with `nf_conntrack_udp_timeout=30`.
- **Arms.**
  - A (spine): UDP lease with cookie at the edge; custom relay↔relay.
  - B: edge UDP lease; relay↔relay over NATS core leafnode + gateway; edge relay re-loops locally.
  - B+: B plus a JetStream `last_per_subject` live-set cache at each relay, for relay restart and validated-LISTEN snapshot.
  - C: Zenoh routers with UDP links and `batch_size` ≤ 1200 for relay↔relay; downsampling as attenuation.
  - E (optional): MQTT-SN PUBWOS to a Paho gateway, then Mosquitto (MQTT 5 expiry across a bridge).
- **Measure.**
  - p50/p95/p99 time-to-hear for late joiners;
  - staleness (age at arrival vs `expires_at`);
  - fraction of items that are *never* heard before expiry;
  - backbone bytes per item;
  - relay CPU, RSS and pps;
  - NAT survival after 10 min idle;
  - remaining-life correctness after 2 hops: a receiver must never accept after `expires_at`, and the broker TTL must be ≤ remaining life;
  - pluck propagation time;
  - tamper test: a relay flips a bit, and receivers must reject it;
  - LOC and dependency count;
  - lines of hardening code needed to pass an amplification test (spoofed LISTEN floods).
- **Decision rule for D10.** Adopt B/B+ for relay↔relay if all of these hold: p95 time-to-hear within 1.2× of A at ≤ 10% loss; remaining-life and signature invariants hold with payload-level enforcement; relay RSS ≤ 64 MB at 10k leases. Otherwise keep A.

  Adopt NATS WebSocket as an *additional* listener binding (browsers, UDP-hostile networks) in any case. It costs one config block.

---

## 6. Verdict: what is genuinely novel, and what is reinvention

**Genuinely canticle** (keep, specify, own):

1. **Receptor and landing semantics into agent context** (P9-P12):
   - listener-chosen landing modes: silent / silent-wake / post-compaction;
   - the wake gate's conjunction: signature + allowlist + class + opt-in + token bucket + hop count;
   - `contextKey` replace-on-loop, to prevent context occlusion;
   - a raw ring before judgement, and a deterministic receptor.

   No broker, DDS vendor or alerting system models "the consumer is an LLM session with a context window and a wake budget".
2. **Chemokine / membrane regulation as protocol semantics**: receiver-side threshold modulation, accord counting over *distinct keys*, antibody memory that outlives TTL, attenuation that lowers the loop rate before dropping a class. Mechanical pieces exist (SAP's bandwidth scaling, Zenoh downsampling, DDS TIME_BASED_FILTER). The immune model does not.
3. **Harness bindings.**
   - OpenClaw: Tier A plugin (`enqueueSystemEvent` + `wrapExternalContent` + `requestHeartbeatNow`) and Tier B durable bridge.
   - Claude Code: MCP tools, channel, and hook `additionalContext`.
4. **The profile itself.** The bundle is: byte-identical signed carousel + absolute expiry + supersede-by-key live-state + looping pluck with sticky-pluck + content-free carrier with per-stream heads + the "decoherence axis" class rule (live-state vs finding). Each element has a precedent. The combination, *for agent context*, does not. This is novelty of profile, not of mechanism, and the RFC should say exactly that.

**Reinvention** (borrow, or at least cite and copy):

| Canticle piece | Existing answer |
|---|---|
| Relay tree, relay↔relay chaining, interest routing | NATS leafnodes/gateways; Zenoh routers; AMT (RFC 7450) for the shape |
| TCP/WS listener access, TLS, connection auth | NATS (NKeys/JWT, WebSocket), MQTT brokers |
| Cookie/lease anti-amplification | DTLS 1.3 cookie, QUIC Retry, AMT relay MAC (transport notes §4). Copy the construction; do not design a new one |
| Carrier beacon | MQTT-SN ADVERTISE + Duration; RTPS SPDP period + lease; Zenoh JOIN; mDNS announce/goodbye |
| Loop scheduling and bandwidth cap | SAP RFC 2974 §3.1 (formula, randomization, reconsideration) |
| Absolute expiry | SAME, FLUTE `Expires`, DDS LIFESPAN, MQTT 5 decrement |
| Supersession / pluck | CAP Update/Cancel with references; SAP deletion; Kafka tombstones; DDS keyed instances; NATS `Nats-Rollup: sub` |
| Late-joiner snapshot | SAP proxy cache (§9); JetStream `DeliverLastPerSubject`; MQTT retained |
| Signed envelope | COSE_Sign1 (RFC 9052), SAP auth header, CAP XML-DSig |
| Replay tier | ringserver (already chosen, P14); JetStream as an agent-side alternative |
| Discovery | DNS-SD/mDNS (already chosen, P8) |
| Multi-part large items | FLUTE/ALC + RaptorQ (RFC 6330) |

---

## 7. Build vs borrow, per layer

| Layer | Recommendation | Functional reason, as §4.6's rule demands | Confidence |
|---|---|---|---|
| **Wire (frame)** | **Build the profile, borrow the envelope where cheap.** Keep P4's det-CBOR int-keys and absolute `expires_at`. Consider **COSE_Sign1** (`kid` = 8 B key-id; alg EdDSA) instead of a bespoke trailer: +11 B [RAN], and every language has a verifier. | No broker frame carries a signature that survives relays or an absolute expiry that a broker cannot rewrite [RAN J2]. The frame must be self-sufficient over *any* carrier (UDP, NATS, WS, DataLink). | HIGH (build) / MED (COSE) |
| **Edge transport** (loopback, LAN multicast, internet UDP lease) | **Build (thin).** Loopback and multicast are sockets. The UDP lease is owner-required ("internet UDP listeners are REQUIRED"). Copy the cookie construction from DTLS/QUIC/AMT. | No broker offers lossy UDP fan-out to NATed listeners. MQTT-SN receivers need a gateway session. Zenoh UDP needs a Zenoh session. | HIGH |
| **Relay / membrane** (verify, allowlist, TTL cap, budgets, attenuation, dedup) | **Build.** Borrow parameters: SAP's bandwidth formula; Zenoh-style per-key Hz caps as a model. | No broker verifies per-frame Ed25519, enforces absolute expiry, or attenuates by loop rate. | HIGH |
| **Relay↔relay backbone / fan-out tree** | **Borrow NATS** (core subjects over leafnode/gateway; optional JetStream live-set cache) once there is more than one relay. Zenoh as the alternate. Until then, a single relay needs no backbone. | "Bespoke relay chaining" fails §4.6's bar: NATS carries it cleanly, and the frame is opaque to it. | MED |
| **Auth** | **Build per-frame Ed25519** (P5). **Borrow** NATS NKeys/JWT for relay↔relay and TCP-listener connections, and subject permissions (`cnt.<K>.>` publish only by K) as defence in depth. | Connection auth ≠ source auth (`nkey_auth.md:3-5`). | HIGH |
| **Discovery** | **Borrow** DNS-SD/mDNS (P8). **Borrow** MQTT-SN's Duration idea into the beacon (S3). | Already borrowed; no change. | HIGH |
| **Replay tier** | **Borrow ringserver** for SeedLink dashboards (P14). Optionally JetStream KV/stream as the *agent-facing* snapshot cache inside relays (S1). | Dashboards need SeedLink. Agents benefit from the 3.7 ms snapshot. | HIGH / MED |
| **Receptor** | **Build.** | Novel (§6). | HIGH |
| **Harness binding** | **Build on harness primitives** (OpenClaw `enqueueSystemEvent`/`requestHeartbeatNow`/`/hooks/wake`; Claude Code MCP/channels/hooks). | Novel; §4.6-compliant because it re-enters the host's own substrate. | HIGH |

---

## 8. Should relays speak NATS or Zenoh among themselves, with the edge raw UDP?

**Answer: yes to "borrow the backbone, keep the edge UDP". NATS first.** It becomes relevant only once there is more than one relay (fleet scale, P15/D5). Conditions:

1. **Loop at the edge, not across the backbone.** An edge relay is a *proxy-station*: it holds the verified live set and runs the carousel for its own leased listeners. The byte-identical frames and absolute `expires_at` from the origin station make that safe. It is also what `proto/scope-framing-and-noosphere-mapping.md:91-93` already calls "relay registers as a proxy-station". The backbone then carries each item once, plus plucks and (aggregated) beacons. Backbone bandwidth becomes Σ items, not Σ items × loops × relays.
2. **The subject map is opaque.** Use `cnt.<keyid16hex>.<stream_id>` for items, `cnt.<keyid>.pluck` for plucks and `cnt.<keyid>.beacon` for beacons. The payload is the canonical frame, unchanged. There are no NATS headers on the hot path, except `Nats-Msg-Id = <keyid>:<epoch>:<stream>:<seq>` if a JetStream cache is used; that gives JetStream dedup of looped copies for free.
3. **Broker TTL is garbage collection only.** When a relay stores into JetStream: `Nats-TTL = max(1 s, ceil(expires_at − now))`, re-computed at *every* hop, because the TTL restarts per hop [RAN J2]. Receivers and relays enforce `expires_at` from the signed frame.
4. **The snapshot requires validation.** A relay (re)starting, or an edge relay admitting a *validated* LISTEN, may pull `DeliverLastPerSubject` and push a paced burst of the live set to that one listener (Deviation S1). This is SAP §9's proxy cache.

**Why NATS over Zenoh for the backbone** [ASSESS MED]:

- NATS decentralized JWT auth is Ed25519 end to end (`jwt/README.md:17,53`). It lines up with P5's key-id identity; Zenoh auth is user/password or `pubkey`.
- Leaf nodes need no inbound reachability (`leafnodes/README.md:12`). Interest-only gateways do not ship streams nobody hears (`gateways/README.md:67-69`).
- WebSocket gives dashboards an earlier browser path.
- It is a single static binary (16.8 MB [RAN]) with mature monitoring (`/varz`).

**Why Zenoh remains the alternate:**

- UDP best-effort links keep backbone loss semantics lossy.
- Per-key downsampling is attenuation, built in.
- It has pico-sized edges.
- But: the default UDP batch MTU fragments (§3.9), history is fetched by query, and the operations story is younger. The repo's own posture — "Zenoh as transport kin, not theology" (`proto/receptor-contract-v0.2.md:552-555`) and "Evaluate Zenoh as routed signal-plane candidate" (`proto/openclaw-surfaces-vs-missing-surfaces.md:131,196`) — supports keeping it as a *candidate*, decided by S4a.

**Why not TCP at the edge:** listeners on Wi-Fi or the internet are exactly where independent per-frame loss beats TCP head-of-line blocking and slow-consumer disconnects (§5.1 point 4). The owner also requires UDP there. NATS/WS stays an *additional* opt-in listener binding, never the default.

---

## 9. Corrections to the repo's current comparator text

- `proto/scope-framing-and-noosphere-mapping.md:244`: "Pub/Sub (MQTT, NATS, Kafka) | Topic-routed messaging | Stateful broker; we're broker-less; we expire." Every clause needs fixing:
  - MQTT 5 expires messages and decrements expiry per hop (§3.3).
  - NATS 2.11+ has per-message TTL (§3.2).
  - Core NATS keeps no message state.
  - Canticle's own membrane relay holds leases and fans out, which makes it a (soft-state) broker.

  Suggested replacement: "Closest mainstream shape. Differs in: station-stateless UDP edge; per-frame signatures that survive relays; absolute expiry enforced by receivers; carousel instead of retransmission or query; receptor landing into agent context."
- `proto/receptor-contract-v0.2.md:443` "no kafka/nats/redis cosplay". This is fine *for the receptor store* (append-only segments + SQLite). It should not be read as a ban on a borrowed relay backbone.
- `proto/explicit-non-goals.md:87` "No participant-table / DDS-style discovery". This is correct, and §3.8 supports it: DDS late-joiner durability needs RELIABLE plus per-reader writer state.
- `spike/silas-prior-art.md:17-20` says pub/sub "replays or buffers missed messages". That is wrong for core NATS and Redis Pub/Sub, which are at-most-once (§3.1, §3.6). The spikes reader already flagged it.

---

## 10. Spine deviations proposed (evidence above)

- **S1 (P1, P6). Relay-side validated snapshot.** Keep "no back-channel to the station". But permit an *edge relay*, after the cookie round-trip, to send the current live set to a newly leased listener as a paced burst within the listener's byte budget, instead of waiting a full loop.
  - Evidence: [RAN] 3.7 ms vs ≈1 s (7.2 s at 30% loss); SAP RFC 2974 §9 proxy caches.
  - Amplification guard: only post-cookie, and total bytes ≤ the per-lease budget.
- **S2 (P1, P7). Adopt SAP's loop rules at the station, not only at the membrane.**
  - Effective period = `max(loop_ms_requested, 8·Σ live_bytes / station_budget_bps)`.
  - Randomize over ±1/3 of the interval (the spine says "±jitter").
  - Recompute the next send time when the live set changes ("reconsideration").
  - Evidence: RFC 2974 §3.1. This makes P7's "lower loop rate first" a station-local invariant as well.
- **S3 (P3). Add `next_beacon_ms` to the carrier beacon.** This is the MQTT-SN ADVERTISE `Duration` field (`impl-guidance-07…md:21`). Absence is declared after *k* missed beacons (Advertise Count), with a SAP-style floor.
  - Relays that "aggregate or slow beacons" (P3) then stay honest, because listeners know the slowed period.
  - A final beacon with `next_beacon_ms = 0` serves as a goodbye/UNEQUIP (mDNS §10.1).
- **S4 (P7, P15). Borrow relay↔relay chaining (NATS core; Zenoh as alternate) instead of building it.** Loop at the edge relay (proxy-station). The custom relay remains the edge membrane only. Decision via spike S4a (§5.2). D10 is answered: **profile over UDP at the edge; borrowed broker between relays; the station never depends on a broker.**
- **S5 (P6). Add a NATS WebSocket/TCP listener binding** (opt-in) as an earlier browser and UDP-hostile path, beside P6(e)'s WebTransport. The frames are identical, and receivers verify them the same way.
- **S6 (P4), optional. Evaluate COSE_Sign1 (RFC 9052)** as the signed envelope (+11 B at 712 B [RAN]) before freezing the bespoke trailer. Byte identity and one-shot signing are unaffected.
- **Not a deviation (confirms the spine).** P4/P5 absolute `expires_at` and per-frame Ed25519 are *required even over brokers*: NATS TTL restarts per hop [RAN], and broker auth is per connection. P14 ringserver stays; no broker speaks SeedLink.

---

## 11. Draft RFC-0001 section: "Relationship to message brokers (why not X)"

> ### N. Relationship to existing brokers and broadcast protocols
>
> **N.1 Position.** Binary Canticle is a *profile*, not a new transport paradigm. Its wire behaviour composes mechanisms with long precedent:
>
> - periodic re-announcement until expiry under a bandwidth cap (SAP, RFC 2974 §3.1);
> - data carousels with absolute expiry (FLUTE/ALC, RFC 6726 §3.2-3.4, RFC 5775);
> - repeated alert headers with an absolute valid-until time, and supersession by reference (NOAA SAME, 47 CFR 11.31; OASIS CAP 1.2);
> - presence beacons that announce their own period (MQTT-SN ADVERTISE; RTPS SPDP);
> - goodbye records (mDNS, RFC 6762 §10.1).
>
> What this document standardises is a specific bundle of these for agent context: a byte-identical signed carousel, absolute expiry, keyed supersession and looping plucks, a content-free carrier with per-stream heads, and — above the wire — receptor and landing semantics for LLM sessions.
>
> **N.2 Invariants a carrier MUST NOT be trusted to provide.** Whatever carries canticle frames (raw UDP, a relay, or a broker), receivers MUST:
>
> - (a) verify the frame's Ed25519 signature against an allowlisted key-id;
> - (b) reject any frame at or after its signed `expires_at`;
> - (c) deduplicate on (key-id, epoch, stream_id, seq);
> - (d) apply sticky plucks.
>
> Broker features (connection authentication, per-message TTL, retained or last-value delivery) MAY be used as optimisations. They MUST NOT substitute for (a)-(d). Rationale:
>
> - NATS NKeys authenticate connections, not messages.
> - NATS `Nats-TTL` is computed from each stream's own timestamp and restarts when a message is sourced into another stream.
> - MQTT-SN 2.0 protection uses symmetric tags that any key holder can forge.
>
> **N.3 Why not NATS (core/JetStream).** Core NATS is at-most-once but runs over TCP. Loss becomes delay, or slow-consumer disconnection, rather than independent per-frame loss, and there is no UDP transport. JetStream adds storage and at-least-once delivery, which this profile does not want on the edge path. Per-message TTLs have a 1 s floor and restart per hop. NATS is nonetheless RECOMMENDED as the **relay-to-relay backbone** (§N.8).
>
> **N.4 Why not MQTT 5 / MQTT-SN.**
>
> - MQTT 5 is TCP- and broker-centred. It correctly decrements the Message Expiry Interval per hop, and a canticle-over-MQTT binding SHOULD set it to the frame's remaining life. Retained messages give last-value per topic, but no carousel.
> - MQTT-SN's PUBWOS/QoS −1 is a near match for a connectionless station. Its ADVERTISE `Duration` is adopted by this profile's carrier (`next_beacon_ms`). Its protection schemes are symmetric only, so it cannot provide per-station source authentication.
>
> **N.5 Why not Kafka or Redis.** Kafka compaction is the reference design for keyed last-value logs and is a suitable *ledger* backend for promoted findings. It has no per-record TTL and no lossy delivery. Redis Pub/Sub is at-most-once over TCP; Streams have no per-entry TTL. Neither fits the edge.
>
> **N.6 Why not ZeroMQ or DDS.**
>
> - ZeroMQ RADIO/DISH over UDP is lossy and brokerless, but draft, with no relay, NAT or security story. PGM and NORM require receiver NAK back-channels, which this profile forbids.
> - DDS offers BEST_EFFORT, LIFESPAN (anchored at the source timestamp) and KEEP_LAST. But its late-joiner durability requires RELIABLE delivery with per-reader writer state, its discovery builds participant tables (see Non-goals), and DDS-Security keys are pairwise and symmetric.
>
> **N.7 Why not Zenoh (yet).** Zenoh is the closest routed pub/sub. It has unreliable UDP links, multicast scouting, liveliness tokens, sequence heartbeats and per-key-expression downsampling. It lacks per-message source signatures, serves history by query rather than by carousel, and by default batches UDP up to ~64 KB (fragmenting). It remains a candidate relay backbone.
>
> **N.8 Bindings.**
>
> - The **edge** (station ↔ host receptor; LAN multicast; relay ↔ listener lease) is raw UDP as specified in §§P6 and MUST NOT require a broker.
> - A deployment with more than one relay SHOULD interconnect relays over a broker, NATS RECOMMENDED:
>   - subject `cnt.<keyid>.<stream_id>` for items, `cnt.<keyid>.pluck` for plucks, `cnt.<keyid>.beacon` for beacons;
>   - payload = the canonical frame, unchanged;
>   - if a stream store is used, `Nats-TTL` = max(1 s, ⌈expires_at − now⌉), recomputed at each hop, and `Nats-Msg-Id` = key-id:epoch:stream:seq.
> - Edge relays act as proxy-stations: they loop the verified live set locally, so the backbone carries each item once.
> - A NATS WebSocket listener binding MAY be offered for browsers and UDP-hostile networks.
> - The SeedLink replay tier remains ringserver fed over DataLink (§P14); brokers do not replace it.
>
> **N.9 What is not borrowed, and why.** No existing system delivers heard items into an agent's context under listener-chosen landing modes, wake budgets and hop limits (§§P9-P12). No existing system regulates reception by chemokine-style threshold modulation with accord over distinct keys (§P7, receptor contract). These are this document's normative contribution.

---

## 12. Open items and unverified claims

- **MQTT 5 primary text not read** (OASIS host blocked). The expiry-decrement rule rests on search excerpts plus Mosquitto source (`database.c:1370-1381`). Topic-alias scope rests on search only. MED.
- **SAME/CAP from search only** (eCFR, govinfo and OASIS blocked). MED.
- **RTPS spec not read.** SPDP behaviour is taken from Fast DDS docs and source. The `239.255.0.1` default SPDP multicast group is from memory and not verified here. MED.
- **zenoh.io claims** (5 B overhead, ~15-50 KB pico) come from search only.
- **Loss emulation.** It was application-level (Bernoulli) and TCP arms were not impaired, so the loss comparison in §5.1 is analytical for NATS. S4a must use netem inside owned namespaces.
- **No measurement at 1k-10k listeners.** Fan-out claims for NATS and Zenoh are vendor/doc claims. The spine's cost model (transport notes §3.3) still applies.
- **IANA.** I did not check `_canticle` or any NATS/Zenoh port registrations.

## 13. Artifacts

- `scratchpad/brokerx/`: the scripts and raw results.
  - Scripts: `frame.py`, `station.py`, `relay_udp.py`, `listener.py`, `run_compare.sh`, `exp_js.py`, `zenoh_probe.py`.
  - Raw results: `results/{a_*,b_*,j_out,z_*}.txt`.
  - `bin/nats-server` (v2.14.7) and `bin/nats-server.stripped`.
- `scratchpad/src/`: the pinned source clones listed in §1, plus `rfc2/` RFC JSON.
