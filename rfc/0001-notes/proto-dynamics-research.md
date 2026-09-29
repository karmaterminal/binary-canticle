# proto-dynamics: UDP vs TCP for a lossy, looping, radio-like broadcast to many listeners

Research spike for Binary Canticle RFC-0001. Date: 2026-09-27. Read-only. Written against
`rfc/0001-binary-canticle.md` (§3.4 invariants, §7 carousel, §8 beacon, §11 transport, §12 membrane,
§18 SeedLink, §20 brokers) and the earlier notes `rfc/0001-notes/transport.md` and
`challenge-broker.md`. It does not repeat them. Those notes already cover NAT timers, the stateless
cookie, anti-amplification, HAProxy, DNS-SD, SAP/FLUTE/SAME as precedents, PGM/NORM as contrast only,
and the NATS/Zenoh measurements.

**Labels.**

- **[VERIFIED at source]**: read in a primary source (spec text, RFC text or code), cited file:line or RFC §.
- **[MEASURED here]**: run in this sandbox.
- **[SEARCH-SNIPPET]**: from a web-search result excerpt of the cited URL. The page itself was not opened. Treat as MED confidence.
- **[UNVERIFIED]**: from memory or inference, not checked.
- **[ASSESS]**: my judgement.

---

## 0. Method, access limits, source pins

**Egress.** These hosts were blocked by the proxy: reftek.com, eri.u-tokyo.ac.jp, earthwormcentral.org,
nappe.wustl.edu, guralp.com, epos-france.fr, univ-brest.fr, ipgp.fr, manual.raspberryshake.org,
groups.google.com, pubmed/eutils/europepmc/crossref/openalex/semanticscholar. raspberryshake.info did
not resolve. I did not route around any denial. WebSearch worked. GitHub/GitLab clones worked, and so did
the alphaXiv arXiv reader.

**Clones.** All are shallow and live under `scratchpad/src/pd/`:

| Clone | Commit | Date | Used for |
|---|---|---|---|
| `moq-wg/moq-transport` | `fb2a6e4` | 2026-09-26 | editor's copy after draft-ietf-moq-transport-20 (`draft-ietf-moq-transport.md`) |
| `SeisComP/seedlink` (`sc-seedlink`) | `5abc328` | 2026-09-17 | SeedLink v3 doc and plugins: q330/lib330, reftek/rtp, naqs, nmxp, scream, scream2, win |
| `FDSN/seedlink` | `b57d317` | 2025-02-06 | SeedLink v4 spec |
| `EarthScope/libslink` | `ffd1367` | 2026-08-12 | |
| `raspishake/rsudp` | `467e8c0` | 2025-04-25 | |
| `morealaz/nmxptool` | `c698330` | 2021-02-04 | GitHub mirror of INGV nmxptool |
| `gitlab.com/seismic-software/earthworm` (sparse) | `6e57b31` | 2026-09-25 | ringtocoax, coaxtoring, import, export |
| `w3c/webtransport` | `26d79fe` | 2026-09-23 | |
| `ietf-wg-webtrans/draft-ietf-webtrans-http3` | `ed853aa` | 2026-07-07 | |
| `marcopovitch/centaur_tools` | HEAD | | |

Also used:

- Linux `torvalds/linux` @ `fd179f8` (2026-09-26), files extracted with `git show` into `pd/linux/`.
- RFC texts from `tex2e/rfc-translater` @ `55f03a2`, normalised into `pd/rfc/rfcNNNN.json`. Search them with `pd/rfc/q.py`.
- The existing `src/ringserver` @ `4f034c8`.

---

## 1. The owner's five claims: verdicts

| # | Claim | Verdict |
|---|---|---|
| 1 | Raspberry Shake DATACAST: UDP beside a local SeedLink server; uncompressed; one packet per ¼ s with 25 samples; for low-latency visualisation | **Essentially correct, with corrections** |
| 2 | Nanometrics "NP (Network Protocol)" UDP on Centaur: push, low overhead, for bandwidth-limited telemetry, feeding ApolloServer; dual mode with TCP SeedLink | **Mostly correct; the name is wrong** |
| 3 | Reftek RTP: "most common UDP alternative to SeedLink", outbound UDP push that traverses firewalls and CGNAT | **Transport is both (the owner's suspicion is right); it is not a lossy push; "most common" is unsupported** |
| 4 | "Standard SeedLink is a pull architecture (the central server initiates a TCP connection to the remote field station)", so it fails behind CGNAT | **Right about direction for the usual deployment; wrong as a protocol statement** |
| 5 | "Standard SeedLink always carries miniSEED records (512-byte blocks)"; v4 allows other formats | **True of v3 in practice; "always" is too strong; the v4 half is correct** |

### Claim 1: Raspberry Shake DATACAST

- **Port and socket.** The default datacast port is 8888 (`rsudp/raspberryshake.py:17`). A receiver binds UDP and calls `recvfrom(2048)` (`:226`). [VERIFIED at source]
- **Packet format.** One packet carries **one channel**, as ASCII text: `b"{'EHZ', 1582315130.292, 14168, 14927, …}"`. That is channel, epoch timestamp, then integer counts (`:243-250`). [VERIFIED at source]
  - So "uncompressed" is right, but the payload is text, not binary.
  - There is **no sequence number**. rsudp infers loss from timestamp gaps: a gap larger than 1.5 × the transmission interval counts as a missed packet (`rsudp/packetloss.py`, `TRE = (TR+TR*.5)/1000`).
  - There is no repair path at all.
- **Cadence.** `getTR()` measures 250 ms between consecutive packets of the same channel (`:344-383`; its example returns `250`). The documented example trace is "100.0 Hz, 25 samples" (`:559`). [VERIFIED at source]
  - Correction: "25 samples per ¼ s" holds for 100 sps channels.
  - rsudp **derives** both values from the stream rather than assuming them (`getSR`: `sps = (commas-1)*1000/TR`, `:411`).
  - A multi-channel Shake sends one packet per channel per interval.
- **Alongside SeedLink.** The manual says the data producer feeds a local SeedLink server (port 18000), the Raspberry Shake community server, and any configured DATACAST UDP targets. [SEARCH-SNIPPET: https://manual.raspberryshake.org/udp.html, …/traces.html]
  - The community-server feed runs on **port 55556, 4 packets/s, over a continuously open socket**.
  - "The Shake is responsible for initiating ALL communication with the … Server." [SEARCH-SNIPPET: https://manual.raspberryshake.org/firewallIssues.html]
  - That feed is the CGNAT-safe path. DATACAST itself is a one-way push to a configured IP:port. The sender may sit behind NAT, but the **receiver must be reachable**, so the NAT burden moves to the listener.
- **Purpose.** rsudp describes itself as tools "to actively monitor and plot UDP data cast output" (`docs/_sources/about.rst.txt:12-13`). "Low-latency visualisation" is a fair summary. [VERIFIED at source]

### Claim 2: Nanometrics NP on Centaur

- **Name.** "NP" is the **Nanometrics Protocol**, not "Network Protocol".
  - "Data is recorded to the Store in Nanometrics Protocol (NP) format, but digitized sensor data can be streamed in SEEDLink and NP formats." [SEARCH-SNIPPET: Centaur User Guide 17935, https://www.epos-france.fr/…/25-Centaur_UserGuide_17935R10.pdf]
  - NP is streamed "using a User Datagram Protocol (UDP) socket or Hypertext Transfer Protocol (HTTP)". The Apollo Server UDP receiver listens on the configured port. [SEARCH-SNIPPET: same guide]
- **Repair.** The repair mechanism is the important part, and the owner omitted it.
  - "Apollo Server uses an application error correction protocol that requests the re-transmission of any missing data, with data gaps identified using both time and packet sequence numbers."
  - It "utilizes the full duration of the data storage media at each remote site". The repair source is the Centaur's whole on-disk Store, not a small RAM ring.
  - [SEARCH-SNIPPET: Apollo Server data sheet, https://nanometrics.ca/hubfs/Downloads/Data%20Sheets/Apollo_Server_data_sheet.pdf]
- **Dual mode.** The Centaur runs a SeedLink server on `localhost:18000` [VERIFIED at source: `centaur_tools/Readme.md:18-19,89`]. Apollo Server also forwards downstream via SeedLink. [SEARCH-SNIPPET]
  - An Earthworm-forum snippet notes that "since seedlink is an in-order protocol, you will not have the data completion features of Nanometrics". [SEARCH-SNIPPET: groups.google.com earthworm_forum thread, blocked]
- **Unverified parts.** "Push" and "feeding ApolloServer" are right. "Low overhead, for bandwidth-limited telemetry" is plausible marketing that I did not verify. [UNVERIFIED]
- **The older generation (NMX/NAQS) is verifiable at source.** See §2.

### Claim 3: Reftek RTP

- **Two protocols share one name and one port number (2543).**
  - **DAS ↔ RTPD: UDP, and reliable.** "RTP … provide[s] a full-duplex, packet-oriented, reliable transport over UDP network connections." It uses positive acknowledgement from RTPD, "16 slot queues … (up to 16 packets may be sent before receiving acknowledgement)", "adaptive retransmission time-out", and reordering on the inbound side. "All network traffic is UDP datagram to/from … port 2543." [SEARCH-SNIPPET: https://reftek.com/ref-tek-protocol-daemon-rtpd/ and RTP-S-004-A, https://www.eri.u-tokyo.ac.jp/…/RTP.pdf, both blocked]
  - **RTPD ↔ client programs: TCP.** SeisComP's `reftek` source is "RefTek RTPD (TCP/IP)", default port 2543 (`sc-seedlink/plugins/reftek_plugin/descriptions/seedlink_reftek.xml:4,9`).
    - The RTP client library connects with `socket(AF_INET, SOCK_STREAM, 0)` (`reftek_libs/rtp/open.c:226`; server side `rtp/server.c:42`).
    - It defines `RTP_DEFAULT_PORT 2543`, `RTP_DASPAKLEN 1024`, NOP heartbeats, START/STOP/FLUSH messages, and TCP socket buffer attributes (`reftek_libs/include/rtp.h:21,36,45-56,91-92`).
    - [VERIFIED at source]
- **Direction and NAT.** The field digitizer initiates outbound UDP to RTPD, so it works behind CGNAT and firewalls without port forwarding. "RTP solves connectivity issues by inverting the traditional client-server model … field digitizers initiate outbound UDP connections to the central RTPD server." [SEARCH-SNIPPET: vendor case study, https://reftek.com/case-study/leveraging-refteks-rtp-reliable-seismic-data-transmission-through-firewalls; vendor marketing]
- **Corrections.**
  1. RTP is not a lossy radio-style push. It is a TCP-like sliding window with positive ACKs over UDP. It is closer to Q330 QDP than to DATACAST.
  2. "The most common UDP alternative to SeedLink" is unsupported, and it compares different layers. RTP is **digitizer-to-acquisition** telemetry; SeedLink is **server-to-client distribution**. RTPD then feeds SeedLink through a plugin. No census of deployments was found. [ASSESS]

### Claim 4: "SeedLink is a pull architecture"

- **Protocol facts.**
  - SeisComP: "The SeedLink protocol is based on TCP. All connections are initiated by the client." After the handshake, "a stream of SeedLink 'packets' … is sent to the client" (`sc-seedlink/apps/seedlink/descriptions/seedlink.rst:3-8`). [VERIFIED at source]
  - FDSN v4: "SeedLink communication takes place over TCP/IP connections"; "In handshaking phase, the client sends commands to the server … In data transfer phase, the client receives a stream of SeedLink packets" (`fdsn-seedlink/protocol.rst:12,29`). [VERIFIED at source]
  - So the client initiates and subscribes, then the server **pushes** on the open connection. It is "client-initiated server push", not polling.
- **Deployment fact.** When the SeedLink server runs **at the field station** (digitizer firmware, a Raspberry Shake, a Centaur, or a station PC), the central system is the client and must reach the station inbound. That fails behind CGNAT without port forwarding, a VPN or a reverse tunnel. [ASSESS, HIGH]
- **Correction.** The architecture follows from where the server sits; the protocol does not require it. Station-initiated alternatives are common:
  - DataLink `WRITE` from the station to a central ringserver (outbound TCP; `slink2dali`, ringserver `WriteIP`; `review/seedlink-dash A.4`);
  - Raspberry Shake's outbound feed (above);
  - Earthworm `export_actv`: "let the export module initiate communication", since 2000 (`earthworm/src/data_exchange/export/export_actv.c:17`) [VERIFIED at source];
  - Güralp GDI-link **push** mode, where the transmitter connects to receiver port 1566 [SEARCH-SNIPPET: https://www.guralp.com/documents/html/MAN-MIN-0001/s5.html];
  - RefTek RTP and Nanometrics NP (above).

### Claim 5: "SeedLink always carries 512-byte miniSEED"

- **v3.**
  - SeisComP: each packet is "an 8-byte SeedLink header followed by a 512-byte miniSEED record" (`seedlink.rst:7,189`). 512 is "hardcoded"; other sizes need a recompile with `MSEED-RECLEN` (`:29-32`).
  - ringserver: "The legacy SeedLink protocol (v3) only transmits 512-byte miniSEED data records. This server is able to transmit miniSEED records of any length via SeedLink" (`ringserver/doc/ringserver.md:178`).
  - libslink added non-512 v3 records in 2.4 (2012) "for particular situations (e.g. low latency data collection)", and has auto-detected record length since 2020.047 (`libslink/ChangeLog:164-165,205-209`).
  - v3 INFO responses are XML embedded in miniSEED **log** records (`seedlink.rst:257`), so they are still miniSEED.
  - ringserver 4.5.4 sent miniSEED 3 to v3 clients; from v4.5.5 it skips miniSEED 3 records for 3.x clients (`ringserver/ChangeLog:10,20`).
  - [VERIFIED at source] Verdict: "512-byte miniSEED 2" is the interoperable norm, not a guarantee.
- **v4.**
  - "The payload of a SeedLink packet is usually a miniSEED record, but other formats are possible, as long as they include time and stream identification" (`protocol.rst:39`).
  - Format codes are 2 (miniSEED 2), 3 (miniSEED 3), J (JSON INFO) and X (XML); other codes are assigned dynamically (`review/seedlink-dash A.1`).
  - Packets are variable-length.
  - ringserver serves only `/MSEED` and `/MSEED3` over SeedLink; JSON is DataLink-only (`doc/ringserver.md:190-196`; `review/seedlink-dash A.4`).
  - [VERIFIED at source]

---

## 2. Other seismic UDP designs (and the TCP ones they pair with)

| System | Transport | Reliability mechanism | Direction | NAT behaviour | Evidence |
|---|---|---|---|---|---|
| **Quanterra Q330 QDP** | UDP (TCP added 2008) | TCP-like sliding window over UDP (details below) | The data processor (DP) initiates: it sends `C1_RQSRV` to register with the Q330 (`lib330/libcmds.c:654,919-934`). SeisComP connects to Q330 port 5330 (`q330plugin/descriptions/seedlink_q330.xml:19,26`). **Pull-registration, then push.** | The Q330 must be reachable, or use a POC receiver or baler. `DT_OPEN` opens the DP-side firewall. | [VERIFIED at source] |
| **Güralp SCREAM!** | UDP by default, TCP optional | Push of 1024-byte GCF blocks with a 16-bit block sequence. The receiver detects gaps (`scream_plugin/scream.c:231-240`). Repair is **receiver-requested over TCP** (details below). | Server pushes UDP to a configured listener; the plugin just binds a port (`scream.c:51-55,108-120`). | Listener must be reachable for UDP. The TCP backfill is client-initiated. | [VERIFIED at source] |
| **Güralp GDI-link** | **TCP** (not UDP) | TCP. Metadata per stream; physical units. | Both modes: the transmitter listens on 1565 (receiver pulls), or connects out to a receiver on 1566 (push). | Push mode is NAT-safe. | [SEARCH-SNIPPET: guralp.com manuals] The owner's "GDI (UDP)" is wrong. |
| **Earthworm `ringtocoax`/`coaxtoring`** | UDP broadcast | None (details below) | Push, LAN-only | LAN broadcast; no NAT story | [VERIFIED at source] |
| **Earthworm `import`/`export`** | TCP | TCP, socket heartbeats (`SendAliveInt`/`RcvAliveInt`), optional **application-level ACK per message** (details below) | `export` listens, `import` connects (pull); `export_actv`/`import_pasv` invert it (`export_actv.c:17`). | Active export is NAT-safe. | [VERIFIED at source] |
| **NIED WIN** (`recvt`/`sendt`) | UDP, multicast since 2002 | **UDP push + per-packet NACK** (details below) | Push | The NACK goes back to the sender's source ip:port, which works through a NAT mapping the sender opened. The WIN network (JDXnet) is a wide-area layer-2 network. [SEARCH-SNIPPET: ERI tech report] | [VERIFIED at source] for the receiver side; sender-side buffering [UNVERIFIED] |
| **Nanometrics NMX / NAQS** (pre-Centaur) | UDP to NAQS (`[NetworkInterface] Port = 32000 // UDP port for incoming NMX data`, optional `MulticastGroup = 224.1.1.1`); TCP 28000 to clients | **UDP push + NACK retransmission requests** from the instrument or comms-controller ring buffer (details below) | Push from the field; clients pull from NAQS over TCP | Field side pushes outbound | [VERIFIED at source] nmxptool; [SEARCH-SNIPPET] Nanometrics manuals |
| **Nanometrics NP** (Centaur → Apollo) | UDP (or HTTP) | Apollo requests retransmission of gaps, found by sequence number and time, from the Centaur's disk Store | Push | Outbound from the station | [SEARCH-SNIPPET] |
| **RefTek RTP** | UDP DAS↔RTPD; TCP RTPD↔clients | Positive ACK, 16-slot window, adaptive RTO | DAS initiates | Works through CGNAT | [SEARCH-SNIPPET] plus [VERIFIED at source] for the TCP side |
| **Raspberry Shake DATACAST** | UDP | None (no sequence numbers) | Push to a configured target | Receiver must be reachable | [VERIFIED at source] |

**Q330 QDP reliability detail** [VERIFIED at source]:

- `DT_DACK` carries a cumulative ack (`lowseq`) plus a **128-bit selective-ack bitmap** over `WINBUFS=128` window buffers (`lib330/libslider.c:1259-1290`; `q330types.h:41`).
- Tunables include window size, min/max resend timeout, ack skip count (ack every N) and ack timeout (delayed ack) (`libtypes.h:345-352`).
- `DT_FILL` keeps sequence continuity when there is no data (`libslider.h:71`).
- `DT_OPEN` means "Open firewall and tell DP where to send data" (`:73`).
- Sockets are `SOCK_DGRAM`, or `SOCK_STREAM` when `tcp` is set (`q330io.c:244-248,357-360`).

**SCREAM backfill detail** [VERIFIED at source]:

- `SCREAM_CMD_OLDEST` (0xfe) returns the oldest block still held; `SCREAM_CMD_RESEND` (0xff + block number) requests one block (`scream2_plugin/scream.h:65-72`).
- The scream2 plugin sends RESEND over a TCP "gap retrieval channel" (`dispatch_ring.c:539-575`; `descriptions/seedlink_scream_ring.xml:28-29`, "TCP request port … for backfill requests").
- It keeps a per-stream ring "for short-term completeness" (`:39`).

**Earthworm ringtocoax detail** [VERIFIED at source]:

- Messages are split into ≤1472-byte packets carrying `fragNum`, `lastOfMsg` and an 8-bit per-logo message sequence (`ringtocoax.c:733-765`).
- Pacing is `BurstCount 3` per `BurstInterval 10` ms (`ringtocoax.d:33-34`).
- coaxtoring **discards the whole message if a fragment is lost** ("End of message lost", `coaxtoring.c:507-517`) and logs sequence gaps.

**Earthworm export_ack detail** [VERIFIED at source] (`export_scnl_ack.d:4-7`):

- "Export_scnl_ack expects to receive an acknowledgment packet for every packet that is writes to socket … will not re-use a slot in its SendQueue until … ACKed".
- The circular "MessageStacking" queue "(RingSize) controls the maximum latency of the data" (`:24-26`).
- An optional `MaxLatency` drops stale packets (`:93-95`).

**NIED WIN NACK detail** [VERIFIED at source for the receiver side]:

- `recvt` (the SeisComP `win_plugin`) keeps an 8-bit packet number per sender `host:port`.
- On a gap smaller than `N_PACKET=128` it `sendto()`s a **1-byte "request resend" datagram** for each missing number back to the sender's address (`win_plugin.c:96,732-827`, sendto at `:803`).
- Resent packets carry the original number `pn_f`; duplicates are discarded by bitmap (`:817-826`).
- `-r` disables requests (`:44,123`).
- Multicast was implemented in 2002 (`:30`).

**Nanometrics NMX/NAQS detail**:

- Every NMX packet begins with a **4-byte "oldest sequence number"**, then the header bundle carries the packet's own sequence number. The oldest number advertises the start of the retransmittable window (`nmxptool/lib/nmxp_base.c:594-627`; struct `include/nmxp_data.h:128-129`). [VERIFIED at source]
- `RetxRequest = Enabled` makes NaqsServer "send out retransmission requests for missed packets"; `MaxTolerableLatency` bounds the wait (`nmxptool/README.md:302-309`; `src/nmxptool_getoptlong.c:281-285`). [VERIFIED at source]
- A Janus comms controller has "a 12MB ringbuffer … to store packets for retransmission". [SEARCH-SNIPPET]
- NAQS offers clients two modes (INGV report `no_dist/rapporto_tecnico_ingv/rapporto_tecnico_ingv_nmxp.txt:147-165`, Italian) [VERIFIED at source]:
  - **Raw stream**: everything as received, "lost, duplicated, retransmitted, out of order, but with minimum delay".
  - **Short-term-complete**: chronological, waiting up to *N* s (≤ 300) for retransmissions.
- The SeisComP naqs plugin warns: "There is no re-requesting of data implemented … any data arriving out-of-order (at the NAQS) beyond this time delay will result in a data gap" (`naqsplugin/README:47-50`). [VERIFIED at source]

**Pattern across 25 years of seismic telemetry** [ASSESS, HIGH]. Three designs recur:

- (a) **Lossy UDP push, no repair**, for LAN or visualisation (DATACAST, ringtocoax).
- (b) **UDP push + receiver-requested repair from the sender's ring**, advertising the oldest repairable sequence (NMX, NP, WIN, SCREAM). This is the design that survived on bad links, satellite included.
- (c) **TCP-like reliable UDP** with a window and positive ACKs (Q330 QDP, RefTek RTP). It exists because the sender must be the NAT-side initiator on a lossy link while still delivering every sample to an archive.

Canticle's carousel is design (a) plus scheduled repetition. Design (b) is the one to borrow, **at the relay** (§7).

---

## 3. Reliable multicast and scaling literature

### 3.1 Why TCP has no multicast

- TCP is defined over a socket pair. "A connection is defined by a pair of sockets" (RFC 9293 §3.4.1).
- It forbids group addressing outright:
  - "A TCP implementation MUST reject as an error a local OPEN call for an invalid remote IP address (e.g., a broadcast or multicast address) (MUST-46)" (§3.9.1.1);
  - "MUST silently discard an incoming SYN segment that is addressed to a broadcast or multicast address (MUST-57)" (§3.9.2.3).
  - [VERIFIED at source]
- The structural reasons [ASSESS, HIGH]:
  - per-peer sequence and ACK space;
  - ACK clocking tied to one receiver;
  - flow control to one receive window;
  - retransmission to one peer.
- Extended to *N* receivers, these become ACK implosion and "lowest common denominator" flow control:
  - NATS: end-to-end flow control in 1-to-N pub/sub "would mean that the publisher(s) would be slowed down to not publish faster than the _slowest_ of all its subscribers" (`nats.docs/using-nats/jetstream/concepts/README.md:45-47`). [VERIFIED at source]

### 3.2 ACK implosion and NACK suppression

- RFC 2887 §2.3: "'flat ACK' schemes cause acknowledge implosions at the sender … Using negative acknowledgments (NACKs) instead of ACKs reduces this problem to one of NACK implosion (only from the receivers missing the packets)." §4.1: per-packet ACK schemes "are limited to very small receiver groups".
- §4.2.1 lists the suppression styles:
  - **SRM**: random timers weighted by the RTT to each receiver;
  - **NTE**: sender-triggered random keys;
  - **AAP**: exponentially distributed random timers;
  - **PGM/LMS**: router-assisted.
  - "The most general … is probably exponentially weighted random timers."
- [VERIFIED at source] (SRM itself is Floyd et al., SIGCOMM 1995 / ToN 1997 [UNVERIFIED, not fetched].)
- **PGM (RFC 3208)** [VERIFIED at source]:
  - Receivers "unicast selective negative acknowledgments (NAKs)". Network elements forward them hop by hop and multicast an **NCF** confirmation, which suppresses other receivers' NAKs and eliminates duplicates (§1.1, §1.2.3).
  - The source advertises a **transmit window** in SPMs: `TXW_TRAIL` is "the sequence number of the oldest data packet available for repair", `TXW_LEAD` the newest (§3.3, §3.5). Window advance is a purely local source policy: fixed bytes, packets or seconds, optionally delayed by NAK silence (§2.1).
  - Reliability is defined as "a receiver either receives all data packets … or is able to detect unrecoverable data packet loss" (§1.2).
- **NORM (RFC 5740) with the NACK building block (RFC 5401)** [VERIFIED at source]:
  - Receivers NACK only at block or object boundaries or after an inactivity timeout, `T_inactivity = NORM_ROBUST_FACTOR·2·GRTT`, with a minimum of 1 s (§5.3).
  - Each receiver draws `T_backoff = RandomBackoff(K·GRTT, GSIZE)` from a truncated exponential with λ = ln(groupSize)+1 (RFC 5401 §3.2.2). It sends only if accumulated `NORM_NACK`/`REPAIR_ADV` state does not already cover its needs, then holds off for `(K+2)·GRTT` (§5.3).
  - One NACK message per cycle, lowest repair needs first (§5.3).
  - For data no longer held, the sender multicasts **`NORM_CMD(SQUELCH)`**, advertising its repair window, rate-limited to once per 2·GRTT (§5.4.3).
  - With **unicast** NACKs it multicasts **`REPAIR_ADV`** so the group can still suppress (§5.4.4).
  - RFC 5401 §2.4: timer-based suppression works for "tens of thousands of receivers".

### 3.3 FLUTE/ALC carousels, FEC and replication

- **ALC** (RFC 5775 §1.2): "no difference in load … if one receiver or a million"; "No feedback packets are required".
- ALC congestion control is **receiver-driven**, by joining and leaving layered channels (§2).
- **FLUTE** requires an absolute `Expires` on each FDT Instance (§3.4.2), and instances "may be repeated multiple times" (§3.2).
- [VERIFIED at source] (The earlier note covered FLUTE/ALC as precedent; this is the congestion angle.)
- **RaptorQ** (RFC 6330 §1): a systematic fountain code. The decoder recovers from "almost any set of encoding symbols of cardinality only slightly larger than the number of source symbols". [VERIFIED at source]
- **The key text for canticle is RFC 2887 §4.3 "Replication"**:
  - A positional stream "does not require additional reliability because a new position superseding the old one will be sent before any retransmission could take place".
  - "Replicated streams do not suffer as the size of the receiver group increases — different receivers lose different packets, but this does not increase network traffic."
  - §4.4: FEC "requires that the data to be sent be grouped into rounds, which can add to end-to-end latency … this may be an issue for interactive applications where replication may be a better solution."
  - [VERIFIED at source] This is the literature's own name for canticle's carousel plus supersession.

### 3.4 SAP announcement interval (RFC 2974)

- `interval = max(300; (8·no_of_ads·ad_size)/limit)`, with limit = 4000 bit/s (§3.1).
- Offset is `rand(interval·2/3) − interval/3`, with reconsideration at each timer (§3.1, §4).
- Implicit deletion after "ten times the announcement period, or one hour, whichever is the greater" (§4).
- [VERIFIED at source]
- **The 300 s floor is a congestion-safety rule for a feedback-free multicast. Canticle's class floors (1-30 s, §6.2) are 10-300× faster.** RFC §7.5 cites SAP for the bandwidth-scaled interval but not for the floor. The RFC should say it keeps SAP's bandwidth cap and drops its 300 s floor, and justify that by the LAN "controlled environment" exemption (RFC 8085 §3.6), relay-side budgets and receiver reports (§7 below). [ASSESS, HIGH]

### 3.5 RFC 8085: UDP usage guidelines

All [VERIFIED at source]:

- **§3.1.3, low data-volume applications.**
  - Case 1 (can detect loss): an initial interval of 1 s, exponentially backed off on loss.
  - **Case 2 (no return traffic): "SHOULD NOT send more than one UDP datagram every 3 seconds and SHOULD use an even less aggressive rate when possible."**
  - §4.1.2 applies the same rules to low-volume multicast.
- **§3.1.6:** an application "that sends three copies of a packet to improve robustness to loss is RECOMMENDED to pace out those three packets over several RTTs". Canticle's +1/+2/+4 s burst complies.
- **§3.1.10:** general-Internet applications without congestion control "SHOULD implement a transport circuit breaker" (RFC 8084).
- **§3.5:**
  - keep-alives no more than every 15 s;
  - "NOT RECOMMENDED for general use";
  - "not a substitute for implementing a mechanism to recover from broken sessions";
  - keep-alives are themselves under congestion control.
- **§4.1:** multicast congestion control is either **feedback-based** (NORM, TFMCC) or **receiver-driven** (ALC, WEBRC, via join/leave).
  - "Applications that can detect a significant reduction in user quality SHOULD regard this as a congestion signal (e.g., to leave a group …); if not, they SHOULD use this signal to provide a circuit breaker."

---

## 4. TCP dynamics that matter for low-rate streams

### 4.1 Retransmission timers

- **RFC 6298** [VERIFIED at source]:
  - initial RTO 1 s (2.1);
  - "if it is less than 1 second, then the RTO SHOULD be rounded up to 1 second" (2.4);
  - a maximum of at least 60 s MAY be applied (2.5);
  - each expiry doubles the timer ("back off the timer", 5.5);
  - Karn's algorithm (§3).
- **Linux differs, and the owner's "Linux 200 ms" is incomplete** [VERIFIED at source]:
  - `TCP_RTO_MIN = HZ/5` (200 ms), `TCP_RTO_MAX = 120 s`, `TCP_TIMEOUT_INIT = 1 s` (`include/net/tcp.h:160-168`).
  - RTO = `srtt + rttvar` (`include/net/tcp.h:879-882`), and **`rttvar` is floored at `rto_min`** (`net/ipv4/tcp_input.c:1121,1129`). The effective minimum is therefore **SRTT + 200 ms**, not a flat 200 ms.
  - Sysctls: `tcp_rto_min_us` default 200000 and `tcp_rto_max_ms` default 120000 (`Documentation/networking/ip-sysctl.rst:1429-1451`).
  - `tcp_retries2 = 15` gives "a hypothetical timeout of 924.6 seconds" before an established connection dies (`:829-844`; `tcp.h:117-122`). A dead peer holds state for about 15 minutes.

### 4.2 Fast retransmit needs dupACKs that low-rate streams don't produce

- RFC 5681 §3.2: "The fast retransmit algorithm uses the arrival of 3 duplicate ACKs." RFC 5827 §1 lists small windows, including application-limited flows, as the case where this fails, and "the minimum RTO is conservatively chosen to be 1 second". [VERIFIED at source]
- Linux's own documentation of **thin streams** says: "If there are less than 4 packets in flight, fast retransmissions can not be triggered, and the stream is prone to experience high retransmission latencies." The mitigations (linear timeouts, first-dupACK retransmit) are **off by default** (`Documentation/networking/tcp-thin.rst:7-43` @ fd179f8; `ip-sysctl.rst:1269` `tcp_thin_linear_timeouts` default 0). [VERIFIED at source]
- `tcp_thin_dupack` is no longer in ip-sysctl.rst, although tcp-thin.rst still names it. RACK subsumed it (below). [VERIFIED at source; the reason is ASSESS]

### 4.3 Tail Loss Probe and RACK

- RFC 8985 [VERIFIED at source]:
  - DupThresh defaults to 3 (§1.1).
  - RACK uses per-segment send timestamps and a reordering window of `min(reo_wnd_mult·min_RTT/4, SRTT)` (§6.2).
  - TLP computes `PTO = 2·SRTT`, **plus `max_ack_delay` when FlightSize is one segment**, or 1 s without an RTT sample (§7.2).
- Linux [VERIFIED at source]:
  - TLP is on by default (`tcp_early_retrans` = 3, `ip-sysctl.rst:450`) and RACK is the only loss detector (`tcp_recovery`, `:761`).
  - `tcp_schedule_loss_probe`: "Probe timeout is 2*rtt. Add minimum RTO to account for delayed ack when there's one outstanding packet" (`net/ipv4/tcp_output.c:3099-3140`).
  - So **a lone lost segment on Linux is probed at about 2·SRTT + 200 ms**.
- Worked example [ASSESS]: a 900 B item every 5 s on a 100 ms RTT path.
  - One lost item is recovered by TLP at about 0.4 s.
  - Fast retransmit would need 3 later items, about 15 s, so it never fires first.
  - If the probe is also lost, RTO backoff takes over (Linux ≥ SRTT + 200 ms, doubling; RFC ≥ 1 s, doubling).
  - **For a single low-rate unicast flow, TCP repairs one loss faster than a canticle carousel does** (next copy after `loop_ms·U(2/3,4/3)`, with a 5 s floor for live-state). That is an honest point in TCP's favour, and the reason §7 proposes relay-side NACK repair.

### 4.4 Head-of-line blocking and stale data

- TCP delivers in order. While a lost segment is being repaired, every later byte waits, **including a newer item that supersedes the lost one**. That is the "stale present" the RFC exists to avoid (§1.2). [ASSESS, HIGH]
- QUIC confines head-of-line blocking to one stream ("an endpoint … might not make forward progress until data that is contiguous with the start of a stream is available", RFC 9308 §4.3). [VERIFIED at source]
- Data already written to a kernel send buffer **cannot be expired**. MoQ says implementations "SHOULD minimize the amount of data buffered at the underlying transport layer, as any data buffered at this layer can no longer be timed out" (moq-transport `draft-ietf-moq-transport.md:1413-1415`). [VERIFIED at source]
- Linux offers `TCP_NOTSENT_LOWAT` to bound the unsent queue. Its global default is unlimited (`ip-sysctl.rst:1243-1253`). [VERIFIED at source]

### 4.5 Restart after idle

- A TCP idle for more than one RTO SHOULD reset cwnd to `min(IW, cwnd)` (RFC 5681 §4.1). Linux does this by default (`tcp_slow_start_after_idle` = 1, `ip-sysctl.rst:932-943`). [VERIFIED at source]
- Harmless for small items, since IW is 10 segments (RFC 6928). [ASSESS]

### 4.6 Per-connection memory, and how many connections one host holds

- **[MEASURED here]** Linux 6.18.44, 4 vCPU, loopback, with `scratchpad/pdexp/tcpmem.py`, over 4000 connections (8000 sockets):
  - **Idle**: the `TCP` slab object is 2368 B and `sock_inode_cache` 832 B. The total `/proc/meminfo` Slab delta was **≈ 4.1 KB per socket** (32.9 MB for 8000 sockets). `sockstat` TCP mem pages did not move.
  - **Slow consumer**: after writing 16 KB to each connection that the peer never reads, TCP-accounted memory was **≈ 20.4 KB per connection** (19 900 pages = 81.5 MB).
  - The truesize overhead on loopback's 64 KB MTU differs from Ethernet, so treat that ratio as indicative.
  - Kernel defaults here: `tcp_mem` = 191742/255659/383484 pages; `tcp_rmem` = 4096/131072/33554432; `tcp_wmem` = 4096/16384/4194304.
- RFC 4987 §2.2: Linux 2.6.10's `sock` "takes over 1300 bytes". Linux says "A SYN_RECV request socket consumes about 304 bytes" (`ip-sysctl.rst:649`). `tcp_mem` pressure mode moderates all sockets once the global page count is crossed (`:659-672`). [VERIFIED at source]
- **Scale evidence** [SEARCH-SNIPPET]:
  - **C10k**: Kegel 1999, citing cdrom.com serving 10 000 clients (https://www.kegel.com/c10k.html).
  - **WhatsApp**: 2 million concurrent TCP connections per FreeBSD/Erlang server, 2012 (https://blog.whatsapp.com/1-million-is-so-2011).
  - **MigratoryData**: 10-12 million WebSocket connections on one server, with about 32-36 GB of kernel memory, i.e. about 3 KB per socket, pushing a 512-byte message per user per minute (https://mrotaru.wordpress.com/2013/10/10/…, https://migratorydata.com/blog/migratorydata-solved-the-c10m-problem/).
  - **C10M**: Graham, Shmoocon 2013, "the kernel is the problem", arguing for kernel bypass (http://c10m.robertgraham.com/p/manifesto.html).
  - [ASSESS] The MigratoryData figure agrees with my 4.1 KB measurement. **Idle connections are cheap; the cost is queued bytes per slow subscriber**, which is exactly what a looping broadcast generates.

### 4.7 Slow consumers and backpressure in pub/sub fan-out

- **NATS** resets the slow client's connection and purges its buffer. "It simply looks like the application experienced temporary server disconnection, and some messages may never be received" (`nats.docs/using-nats/jetstream/concepts/README.md:33-35`). The knob is `write_deadline` (`running-a-nats-service/nats_admin/slow_consumers.md:89-92`). [VERIFIED at source]
- **Mosquitto**: `max_queued_messages` defaults to 1000 per client. Beyond `max_queued_bytes`/`max_queued_messages`, QoS 1/2 messages "will be silently dropped" (`mosquitto/man/mosquitto.conf.5.xml:862-890`). [VERIFIED at source]
- **MoQ**: a publisher "MAY terminate the subscription using PUBLISH_DONE with error `TOO_FAR_BEHIND`" when a subscriber's queue exceeds its limits (`draft-ietf-moq-transport.md:1450-1453,5105-5107`). [VERIFIED at source]
- **Earthworm export**: a fixed circular queue; its depth "controls the maximum latency of the data" (above).
- [ASSESS, HIGH] Every TCP fan-out system ends up with a per-subscriber queue plus a drop or disconnect policy. **UDP fan-out has no sender-side queue per listener.** A slow or absent listener loses datagrams at its own bottleneck, and the relay's memory does not grow. The per-lease cost is lease state (tens of bytes) plus a byte budget.

### 4.8 SYN floods versus UDP reflection

- A **SYN flood** exhausts **listener state** (half-open TCBs). SYN cookies "allocate no state at all for connections in SYN-RECEIVED" by encoding it in the ISN (RFC 4987 §2.2, §3.6). Linux enables them as a fallback by default (`ip-sysctl.rst:964-986`). [VERIFIED at source]
- The TCP handshake also validates the source address before data flows. [ASSESS]
- **UDP reflection** abuses a **stateless responder** with spoofed sources. The fix is the same idea at the application layer: a stateless cookie before any stream, and responses no larger than requests before validation. That is already RFC §11.3.3, with the construction justified in `transport.md §4`. [ASSESS] Nothing new is needed here beyond noting that the canticle HELLO/COOKIE is the SYN-cookie analogue and that REPAIR (§7) must sit behind it.

---

## 5. QUIC, WebTransport and Media over QUIC

### 5.1 QUIC datagrams (RFC 9221) and loss recovery (RFC 9002)

- DATAGRAM frames:
  - are "not retransmitted upon loss detection" but "are ack-eliciting" (§5.2);
  - "cannot be fragmented" (§5);
  - have "no explicit flow control" and "MAY be dropped by the receiver if the receiver cannot process them" (§5.3);
  - under congestion control, the sender "MUST either delay … or drop the frame" (§5.4);
  - implementations "can optionally support … a sending expiration time beyond which a congestion-controlled DATAGRAM frame ought to be dropped" (§5.4).
  - [VERIFIED at source]
- **Consequence** [ASSESS, HIGH]: a WebTransport-datagram relay→listener binding gets per-listener congestion control, loss feedback, address validation and confidentiality for free, which RFC 8085 otherwise obliges canticle to build. The costs:
  - per-connection QUIC and TLS state;
  - a handshake per listener;
  - **per-copy encryption**, with no shared ciphertext across listeners.
- QUIC's PTO (`smoothed_rtt + max(4·rttvar, kGranularity) + max_ack_delay`) "replaces RTO and TLP". It does not collapse cwnd on PTO (RFC 9002 §4.7, §6.2.1). [VERIFIED at source]
- RFC 9308 [VERIFIED at source]:
  - §2: "between 3% … and 5% … of networks block all UDP traffic", so a TCP fallback is mandatory (canticle has one: NATS/WebSocket §11.6, ringserver WebSocket §18).
  - §3.2: "UDP applications can assume that any NAT binding … can expire after just thirty seconds of inactivity."

### 5.2 WebTransport

- **W3C API** (`w3c-webtransport/index.bs:501-509`) [VERIFIED at source]:
  - `WebTransportDatagramDuplexStream` has `incomingMaxAge`/`outgoingMaxAge` (expiry of queued datagrams, ms) and `incomingMaxBufferedDatagrams`/`outgoingMaxBufferedDatagrams`.
  - The incoming queue has a length "beyond which datagrams are dropped from the head of the queue", i.e. oldest first.
  - `createWritable({sendGroup, sendOrder})` gives datagram priorities (`:333-334,488-492`).
- **IETF draft** (`wt-http3/draft-ietf-webtrans-http3.md:179-183`): with the capsule (HTTP/2-style) fallback, "all WebTransport streams … share a single QUIC stream and are subject to head-of-line blocking. Datagrams sent using the capsule-based protocol are also retransmitted by QUIC, and therefore do not provide unreliable delivery." [VERIFIED at source]
  - A browser fallback silently turns the radio into TCP semantics.

### 5.3 Media over QUIC Transport (MoQT)

Source: editor's copy after draft-20, file `draft-ietf-moq-transport.md` @ `fb2a6e4`. All [VERIFIED at source].

**Data model.**

- Track → groups (join points) → subgroups (one QUIC stream each) or datagrams → objects (`:301-470`).
- An object "must be an identical sequence of bytes regardless of how or where it is retrieved. An Object can become unavailable, but its contents MUST NOT change" (`:326-330`).
- Object metadata is visible to relays. The payload "may be encrypted"; authentication is the original publisher's job (`:336-341`).
- Object states are "known not to exist" (permanent), "known to exist", and "unknown". "A gap in the observed Object IDs does not by itself convey any information" (`:364-390`).
- A publisher that loses state should pick a new track name or a time-based Group ID to avoid collisions (`:547-558`). This is canticle's epoch.

**Live versus catch-up.**

- `Largest Object` is the head (`:743-756`).
- Joining:
  - `SUBSCRIBE` at the Next Object is live only;
  - `SUBSCRIBE` plus `FILL_PARAMETERS` opens a **fill fetch stream** for the current or past groups alongside live delivery;
  - `FETCH` retrieves a closed range (`:759-1058`).
- A subscriber that "wants each Object delivered exactly once uses the Next Object Subscription Location Filter coupled with an open-ended fill range" (`:1007-1009`).
- `FILL_TIMEOUT` bounds the total upstream work of a fill; beyond it, gaps are reported as timed out (`:840-854`).
- `NEW_GROUP_REQUEST` lets a subscriber ask the original publisher to start a new group, i.e. a new join point (`:1059-1078`).

**Priorities and dropping stale data.**

- Scheduling order (`:1255-1356`):
  1. subscriber priority (0-255, lower is higher);
  2. publisher priority;
  3. group order (ascending or **descending, newest first**);
  4. subgroup or object ID.
- Delivery timeouts (`SUBGROUP_DELIVERY_TIMEOUT`, `OBJECT_DELIVERY_TIMEOUT`, `:1382-1453`) do the dropping:
  - an expired subgroup stream is **reset**;
  - an expired datagram is **dropped**;
  - the smaller of the publisher's and subscriber's values applies.
- A relay "MUST NOT reorder or drop objects received on a multi-object stream" (`:1967`). Dropping is by timeout or reset, not by the relay's whim.

**Relays** (`:1861-2004`).

- They are "endpoints" that terminate sessions.
- They may cache by (track, group, object). "An endpoint that receives a duplicate Object with a different … Payload MUST treat the track as Malformed" (`:1892-1893`).
- They deduplicate across multiple publishers (`:1940-1942`).
- They aggregate subscriptions into one upstream (`:1970-1985`), and must authorize each downstream subscriber independently (`:5266-5268`).
- `GOAWAY` lets subscribers switch relays gracefully (`:1991-2002`).

**Lease-like expiry.**

- `EXPIRES` on a subscription, extended via `REQUEST_UPDATE`. Relays "MAY introduce jitter to prevent many endpoints from updating simultaneously" (`:4009-4028`).

**Caching time is relative per hop.**

- `MAX_CACHE_DURATION` counts from when **each relay** received the object (`:4151-4164`), the same per-hop restart that NATS TTL has (RFC §12.4).
- Canticle's signed absolute `expires_at` is strictly better for "remaining life never resets" (I-3).

**Security.**

- MoQT relies on hop-by-hop TLS and QUIC plus relay authorization. Its impersonation defence is "a relay MUST verify that the authenticated identity or token scope permits publishing to the specific namespace" (`:5336-5361`).
- End-to-end source authenticity is deferred to Secure Objects (`:5363-5393`). That draft is an **SFrame-style symmetric AEAD** scheme, "End-to-End Symmetric Encryption and Authentication" [SEARCH-SNIPPET: https://datatracker.ietf.org/doc/draft-ietf-moq-secure-objects/, IETF 124 slides]. Any track-key holder can forge objects.
- Subscription amplification: "Relays SHOULD implement rate limiting on subscription requests" (`:5270-5280`); short-prefix namespace subscriptions are flagged (`:5452-5459`).

**Congestion.** MoQT names bufferbloat, the application-limited under-probing problem, and BBR's PROBE_RTT dips as issues for live media (`:5198-5245`).

### 5.4 What canticle could borrow from MoQ, concretely

| MoQ mechanism | Canticle equivalent or proposal | Where |
|---|---|---|
| Immutable object bytes; duplicate with different payload means Malformed | Already byte-identical loops (§7.2) and equivocation (§10.8). **Cross-validation**: MoQ reached the same invariant independently. | — |
| Largest Object / Next Object | Beacon `head_seq` per stream (§8.2). **Add `trail_seq`** (lowest live seq) so receivers can separate "lost, will loop again" from "gone" (PGM `TXW_TRAIL`, NMX oldest-seq, SCREAM `OLDEST`). | §8.2, §9.8 |
| SUBSCRIBE (live) vs fill fetch vs FETCH | LISTEN `join` field: `live` (default) \| `live+fill` (relay snapshot, today's §7.10 MAY) \| `fill-only`. The **fill is bounded by a fill budget and time** (`FILL_TIMEOUT`); deduplicate fill copies and live copies by tuple. | §7.10, §11.3.2 |
| Subscriber priority + publisher priority + group order | Relay egress scheduler per lease: (1) listener filter priority (new optional `prio` in the LISTEN filter); (2) class priority (control ≥ alarm > live-state > …, as §7.5 already orders); (3) **first copies, supersedes and plucks before repeats**; (4) newest `issued_at` first within a `state_key` (MoQ "descending"). | §12.2-§12.3 |
| Delivery timeout (drop, don't deliver late) | Per-lease egress: **drop a queued frame when `remaining_life < min_useful_ms[class]` or queued > `max_queue_ms`**; keep kernel send buffers small (`SO_SNDBUF` or pacing) so stale frames never sit where they can't be expired; for WebTransport set `outgoingMaxAge` = remaining life. | §12.3, §11.5 |
| `TOO_FAR_BEHIND` | Per-lease queue cap. On overflow, raise decimation (A2) for that lease, then send LEASE_UNKNOWN. Never grow memory. | §11.3.7 |
| `EXPIRES` + jitter | Already lease_s + renew jitter (§11.3.5). | — |
| `GOAWAY` | **Add a relay-signed `RELAY_GOAWAY{next_srv?}`** so a draining relay moves leases before they lapse (today listeners wait 3 × `relay_beacon_ms`). | §11.3.2, §11.3.9 |
| Subscription aggregation | Already: loop at the edge, backbone carries each item once (§12.4). | — |
| Rate-limiting short-prefix subscriptions | Wildcard filters (`key_id=null` / `stream_id=null`) SHOULD require a capability and count ×N against lease caps. | §11.3.6-§11.3.7 |
| Datagram vs subgroup-stream delivery modes | For a WebTransport binding: **datagrams for loop repeats and beacons; one short QUIC stream per first copy of alarm, control and pluck**, reset at expiry. This gives reliable-until-expiry delivery with head-of-line blocking confined to one item. | §11.5 |
| **Not** to borrow | Per-hop relative `MAX_CACHE_DURATION`; symmetric-key Secure Objects as source authentication; per-subscriber session state at the **station**; reliance on hop TLS for content authenticity. | — |

---

## 6. Biology: is "a chemokine binding a cell far more like TCP"?

Sources: primary papers via search snippets (PubMed and publishers were blocked), plus two arXiv physics papers read in full through alphaXiv.

### 6.1 Secretion, diffusion, gradients

- **The steady-state field.** For a point source secreting at rate J with diffusivity D and first-order decay k, the field is `c(r) = J/(4πDr)·e^(−r/ℓ)`, with decay length `ℓ = √(D/k)`. [VERIFIED at source: arXiv 2310.00062, the Dictyostelium folate model]
  - Secretion is **unaddressed broadcast**. The concentration a receiver sees is set by the source rate, the distance and the lifetime.
  - This is exactly RFC §12.1's *availability* quantity: loop rate ≈ J, TTL ≈ 1/k, relay depth decimation ≈ e^(−r/ℓ).
- **Many chemokines are not free-diffusing.**
  - They bind glycosaminoglycans (heparan sulfate). CCL21 is immobilised on HS in skin, and dendritic cells follow the **immobilised (haptotactic)** gradient. "Experimental delocalization or swamping the endogenous gradients abolishes directed migration" (Weber et al., Science 339:328, 2013). [SEARCH-SNIPPET]
  - GAG binding and oligomerisation are **required in vivo but not in vitro** (Proudfoot et al., PNAS 100:1885, 2003). [SEARCH-SNIPPET]
  - [ASSESS] A GAG-bound depot is a **local cache that presents the signal to whoever passes**. That is closer to a relay's live-set cache or carousel than to a one-shot broadcast.
- **The medium is actively shaped by non-signalling receptors.**
  - ACKR4 (CCRL1) on the lymph-node sinus ceiling **scavenges** CCL19/21 and so *creates* the functional gradient (Ulvmar et al., Nat Immunol 2014). [SEARCH-SNIPPET]
  - ACKR1 (DARC) internalises chemokines **without signalling** and transcytoses them across endothelium, presenting them intact on the other side (Pruenster et al., Nat Immunol 10:101, 2009). [SEARCH-SNIPPET] That is a biological **byte-identical, non-originating relay** (I-8).
  - Cells can create their own gradients by breaking down attractant, which lets them "solve mazes" (Tweedy et al., Science 369, 2020). [SEARCH-SNIPPET]

### 6.2 Receptor binding and GPCR activation

- **Two-site model.**
  - Site 1 (CRS1): the receptor N-terminus binds the chemokine core (N-loop/β3, 40s loop). It sets **affinity and selectivity**.
  - Site 2 (CRS2): the chemokine N-terminus inserts into the transmembrane pocket and **activates** the receptor.
  - Structural work since 2015 adds CRS1.5 and CRS3, so "two-site" is a useful simplification, not the full story (Kufareva, Salanga, Handel, Immunol Cell Biol 2015, PMC4406842; Biochem Soc Trans 52:1011, 2024). [SEARCH-SNIPPET]
- **GPCR activation and desensitization.**
  - The activated receptor couples to Gαi.
  - GRK phosphorylation of the C-tail recruits β-arrestin, which uncouples the G protein and drives clathrin-mediated internalisation, then recycling or lysosomal degradation (CXCR4 is ubiquitinated and degraded).
  - Ligand bias exists: CCL19, not CCL21, drives robust CCR7 phosphorylation and internalisation.
  - [SEARCH-SNIPPET: PMC2779657, PMC9465349, Cell Reports 2025 on CCR7]
- **Receptor occupancy integrates concentration over time.**
  - Berg–Purcell: `δc²/c² = 1/(4DacT)` for one perfectly absorbing receptor integrating over T. With N receptors, T is multiplied by N.
  - When the concentration itself changes on timescale τ, the best achievable error becomes `≈ 1/√(4Dacτ)`, attained at an effective window `T ≈ √(τ/4Dac)`: "the geometric mean between the mean time between binding events and the time scale of variation" (Mora & Nemenman, PRL 123:198101, 2019; arXiv 1908.04057). [VERIFIED at source]
  - Optimal averaging balances detection noise (∝ 1/(N·T)) against environmental change (∝ ω²T²). There are no-averaging, finite and infinite regimes (arXiv 2310.00062). [VERIFIED at source]
  - Neutrophils orient in gradients of about 1% across the cell (Zigmond, J Cell Biol 75:606, 1977). [SEARCH-SNIPPET]

### 6.3 The immunological synapse

- **Structure.** A **sustained, organised contact**, with cSMAC, pSMAC and dSMAC zones (Monks et al., Nature 395:82, 1998): "a central cluster of T cell receptors surrounded by a ring of adhesion molecules" (Grakoui et al., Science 285:221, 1999). [SEARCH-SNIPPET]
- **Duration.** Naive T cells hold contacts with dendritic cells for about **6-18 h** before committing (Iezzi et al., Immunity 8:89, 1998, as cited in Nat Immunol ni0601_487). Continuous TCR signalling is needed to maintain the synapse (Nat Immunol ni951). [SEARCH-SNIPPET]
- **Bidirectional.**
  - T-cell CD40L engages CD40 on the dendritic cell. This "two-way signaling" licenses the DC (IL-12, B7 up). CD40L even transfers to and is endocytosed by the APC.
  - The T cell secretes IL-2 and IFN-γ **into the synapse** (directed), but TNF and CCL3/CCL5 **multidirectionally** (Huse et al., Nat Immunol 7:247, 2006): the same cell runs a unicast channel and a broadcast channel.
  - [SEARCH-SNIPPET: J Immunol 173:3647; Eur J Immunol 2017; Huse 2006]
- **Serial engagement.** One pMHC serially engages up to about 200 TCRs (Valitutti et al., Nature 375:148, 1995). [SEARCH-SNIPPET]
- **Kinetic proofreading.** Modifications after binding introduce "a temporal lag between ligand binding and receptor signaling", so discrimination is by **off-rate (dwell time)**, not equilibrium affinity (McKeithan, PNAS 92:5042, 1995). [SEARCH-SNIPPET]
- **Digital response.** A **single pMHC** can trigger cytokine secretion, and more pMHC do not increase the secretion rate (Huang et al., Immunity 39:846, 2013). [SEARCH-SNIPPET]

### 6.4 Synaptic transmission

- **Cleft and clearance.**
  - Transmitter crosses the cleft by diffusion (glutamate D ≈ 0.76 µm²/ms).
  - It is cleared on millisecond timescales by enzymatic breakdown (acetylcholinesterase) or reuptake (EAAT2 takes about 95% of glutamate uptake, mostly in astrocytes).
  - [SEARCH-SNIPPET: Trends Neurosci; bioRxiv 670844] The cleft width of about 20 nm is textbook. [UNVERIFIED]
- **Individual central synapses are unreliable.** Failure probabilities at CA1 synapses sit in a broad peak between 0.5 and 0.95 (Allen & Stevens, PNAS 91:10380, 1994). [SEARCH-SNIPPET] A single synapse is a **lossy** channel. Reliability comes from many release sites, many synapses and rate coding.
- **Retrograde messages exist but are gain control, not ACKs.** Endocannabinoids released by the postsynaptic cell **suppress** presynaptic release (DSI; Wilson & Nicoll, Nature 410:588, 2001). [SEARCH-SNIPPET]
- Presynaptic autoreceptors (the sender sensing its own output) are textbook. [UNVERIFIED]

### 6.5 Juxtacrine signalling (Notch–Delta)

- **Contact required, and consumed on use.** Notch needs cell-to-cell contact. A ligand-generated **pulling force** (trans-endocytosis by the sending cell) unfolds the negative regulatory region, enabling proteolysis that releases NICD. "Each Notch molecule is irreversibly activated by proteolysis and signals only once without amplification" (Kopan & Ilagan, Cell 2009; Dev Cell 2017 review). [SEARCH-SNIPPET]
- **Senders and receivers exclude each other.** Cis-interactions make a cell **either** a sender (high Delta, low Notch) **or** a receiver, via an ultrasensitive switch (Sprinzak et al., Nature 465:86, 2010). [SEARCH-SNIPPET]

### 6.6 Mapping onto transport concepts: where the TCP analogy holds and where it breaks

| Biology | Best transport analogue | Where "TCP" holds | Where it breaks |
|---|---|---|---|
| Chemokine **secretion and diffusion** | **UDP broadcast / multicast carousel**: rate J (loop), decay k (TTL), reach ℓ (scope, relay depth) | — | No connection, no addressing, no sequence |
| GAG-bound **haptotactic depot**; ACKR1 transcytosis | **Relay live-set cache / carousel at the edge**; ACKR1 = relay that forwards without originating (I-8) | Persistent, local, presented to passers-by (like a snapshot) | Nobody requests it; it is not per-receiver |
| **Receptor binding** (two-site: dock, then activate) | Receiver-side admission: cheap recognition (CRS1 ≈ key_id, class and time checks) before costly activation (CRS2 ≈ signature and capability); cf. §12.2 order | **Holds partly**: binding is specific, one-to-one at the molecular level, and changes receiver state; dock then activate looks like a two-step handshake | **No ACK to the secreting cell**; secretion is not clocked by reception; no per-receiver retransmission; no ordering; the receptor cannot identify *which* cell secreted |
| **Desensitization and internalization** | Receiver-local AGC and refractory period (§14.6.4) | Stateful, but **at the receiver only** | Not negotiated with the sender. It is flow control *without* feedback, the opposite of TCP's receive window |
| **Occupancy integrates over time** | Receptor integration window with a threshold (§14.6) | — | Biology counts repeated arrivals of the same ligand: concentration *is* rate × lifetime. Canticle **deliberately breaks this** (I-4, repeats are no-ops). The honest mapping is that canticle's *strength* is **not** chemokine concentration; only *availability* is |
| **ACKR scavenging**, self-generated gradients | Receivers or relays that consume shape what others hear | — | TCP has nothing like it. In canticle, listening never depletes the signal, so a gradient-shaping sink is a *policy* choice (relay decimation), not physics |
| **Immunological synapse** | **The genuinely TCP-like case**: adhesion ≈ connection setup; hours of sustained, bidirectional, stateful exchange; the APC gets signals back (CD40L→CD40); directed secretion ≈ unicast | Session, bidirectionality, persistence, per-peer state, orderly termination | No sequence numbers or retransmission. Reliability comes from **serial re-sampling** (one pMHC, about 200 TCRs) and **kinetic proofreading** (require dwell time before commit), which is closer to "hear it several times over τ before acting" than to ACK/retransmit |
| **Synapse (neural)** | Point-to-point but **lossy datagram** (per-spike failure 50-95%), short TTL (ms clearance), reliability by redundancy and rate | Fixed pairing (like a connection) | No ACK. Retrograde endocannabinoid signals are **congestion or gain feedback** (like an RTCP receiver report or ECN), not acknowledgement |
| **Notch–Delta** | Handshake-gated, **consumed one-time token** (idempotency key; addressed mode §15.6) | Requires both parties present; physical coupling; 1:1 stoichiometric | Signals once, no amplification, no retransmission; it destroys its own "channel" element |

**Verdict** [ASSESS, HIGH]. The owner is half right. The *act of binding* is a specific, state-changing, one-to-one molecular event, and receptors do run a dock-then-activate sequence. But chemokine *communication* is broadcast. The secretor is open-loop: no ACK, no per-receiver retransmission, no knowledge of who heard. All the adaptation is **receiver-side**: integration windows, thresholds, desensitization. The TCP-like structure in immunology is the **immunological synapse**, and even that gets reliability from repeated sampling and dwell-time proofreading rather than from ACKs.

Two design consequences:

1. Canticle's receptor should borrow **kinetic proofreading** for action gating: require persistence over a dwell time or across *k* loop revolutions, or accord across principals, before a heard item can wake anything. §14.7.3 two-signal quarantine is already in this spirit.
2. It should size integration windows by Mora–Nemenman: window ≈ √(inter-arrival × change timescale), i.e. tied to the stream's advertised `loop_ms` and to supersession cadence, not a fixed constant.

---

## 7. Design lessons for canticle, ranked

1. **Keep the edge lossy UDP. The literature and the measurements confirm the choice, but for different reasons than "UDP is faster".** [HIGH]
   - TCP actually repairs a *single* low-rate loss faster than the carousel (Linux TLP ≈ 2·SRTT + 200 ms, against a ≥ 5 s loop floor; §4.3).
   - TCP loses on:
     - head-of-line blocking, where a newer supersede waits behind a lost stale item (§4.4);
     - un-expirable kernel buffers (§4.4);
     - per-subscriber queues that force drop or disconnect policies (§4.7), measured at about 4 KB idle to 20 KB with a 16 KB backlog per connection (§4.6);
     - 15-minute dead-peer detection (§4.1);
     - no multicast (§3.1).
   - Replication with supersession is the textbook answer for "a new position superseding the old one" (RFC 2887 §4.3).
   - Keep TCP/WebSocket only as the fallback (3-5% of networks block UDP; RFC 9308 §2) and as the replay tier.
2. **Advertise the repairable window, not just the head.** [HIGH]
   - Every surviving UDP design advertises both ends: PGM `TXW_TRAIL`/`TXW_LEAD`, NMX oldest-seq in *every packet*, SCREAM `OLDEST`, NORM `SQUELCH`.
   - Add `trail_seq` (lowest live seq) beside `head_seq` in each BEACON stream entry (§8.2, §9.8; about 3-5 bytes). A receiver then knows whether a gap is:
     - *lost and still looping* (wait one `loop_ms`, or request repair);
     - *expired or depth-evicted* (stop waiting; MoQ's "known not to exist").
   - This also makes §7.1's "honest gap" visible.
3. **Add receiver-requested repair at the relay, never at the station.** [MED-HIGH]
   - I-2 forbids a back-channel **to the station**. Relays already hold leases and a live-set cache (§12.4) and may snapshot (§7.10).
   - A **REPAIR** message is lease-scoped, cookie-validated and ≤ `granted_bps`. It lists missing `(key_id, stream_id, seq-ranges)` inferred from `head_seq`/`trail_seq`. The relay answers from its verified live set, only for items with enough remaining life, and returns `SQUELCH`-style "gone" ranges.
   - This is the NMX/NP/WIN/SCREAM pattern, and it gives TCP-like repair latency (about 1 RTT) without TCP's head-of-line blocking.
   - Adopt NORM's discipline:
     - one REPAIR per beacon interval with the lowest needs first;
     - a holdoff of (K+2)·RTT before re-asking;
     - relays rate-limit "gone" replies to once per 2·RTT.
   - On unicast leases there is no implosion to suppress; the per-lease caps bound the cost. Do **not** add NACKs on LAN multicast in v1.
   - Keep the carousel as the baseline. REPAIR is an optimisation, which the RFC's §21 non-goal 1 must then state as a scoped exception, like the lease exception.
4. **Meet RFC 8085 honestly on internet paths: turn RENEW into a receiver report.** [HIGH]
   - Relay→listener flows *have* return traffic (RENEW every ≈ 22 s), so §3.1.3 case 2 (≤ 1 datagram per 3 s without return traffic) need not bind. But only if the relay *uses* that traffic.
   - Add to RENEW: frames received and expected per stream since the last RENEW (computable from seq numbers, as rsudp does from timestamps), plus max observed gap.
   - The relay then:
     - (a) adjusts per-lease decimation (A2) or `granted_bps`;
     - (b) trips an RFC 8084-style per-lease circuit breaker on sustained high loss.
   - This is RTCP-RR-grade feedback, not an ACK.
   - On the LAN, justify the absence of feedback by RFC 8085 §3.6 (controlled environment), with `canticle doctor` as the control. State that the 1-30 s class floors deliberately depart from SAP's 300 s floor (§3.4).
5. **A MoQ-style egress scheduler with delivery timeouts at every relay.** [HIGH]
   - Priority order: listener filter priority, then class priority, then **first copies, supersedes, plucks and alarms before repeats**, then newest-first within a `state_key`.
   - Drop frames whose remaining life has fallen below a class minimum, or which have queued longer than `max_queue_ms`.
   - Cap per-lease queues (a `TOO_FAR_BEHIND` analogue: decimate, then LEASE_UNKNOWN).
   - Keep kernel send buffers small so stale frames never wait where they cannot be expired.
6. **Two receiver consumption modes, as NAQS has.** [MED] (A §14 extension.)
   - *raw*: land as soon as verified;
   - *completed*: hold up to `max_tolerable_latency` (default one `loop_ms`) for gaps to fill by loop or repair, then land in `issued_at` order.
   - NAQS "short-term completion" and nmxptool's `--maxlatency` are the precedent.
   - For the ringserver bridge, late copies must never create new ring packets. The RFC already has one ring packet per tuple (§18.3).
7. **Borrow kinetic proofreading for action gating, and Mora–Nemenman for window sizing.** [MED] See §6.6. It strengthens §14.7.3 and §14.10 without new wire fields.
8. **WebTransport binding: follow MoQ, not raw datagram-only.** [MED]
   - Datagrams for repeats and beacons, with `outgoingMaxAge` = remaining life and small `outgoingMaxBufferedDatagrams`.
   - One short stream per first copy of alarm, control and pluck, reset at expiry.
   - Refuse the capsule fallback for "lossy" semantics (it retransmits), or label it as the TCP tier.
   - This gets QUIC congestion control for free.
9. **Add relay GOAWAY.** [MED] A signed `RELAY_GOAWAY{next}` lets a draining relay move leases gracefully instead of waiting 3 × `relay_beacon_ms`.
10. **Never fragment; a lost fragment kills the whole message.** [HIGH] ringtocoax/coaxtoring is the 25-year-old proof (§2). This confirms §9.1. For large items, reference plus fetch (§9.12) is right. RaptorQ/FLUTE only if multi-part items ever return, since FEC adds round latency (RFC 2887 §4.4).
11. **NAT direction is solved by making the NATed party initiate: stations push to relays, listeners lease from relays.** [HIGH] This matches RefTek RTP, NP, Raspberry Shake, `export_actv` and GDI push. Already in §11.3. No change beyond citing these precedents. SeedLink-style "central pulls from station" must not reappear in the ringserver bridge; the bridge writes via DataLink from the relay.

---

## 8. What to borrow from MoQ, NORM and Nanometrics (summary)

- **MoQ**: §5.4 table. The highest-value items:
  - `join = live | live+fill | fill-only` with a fill budget;
  - the priority scheduler plus delivery timeout at relay egress;
  - the `TOO_FAR_BEHIND` queue cap;
  - GOAWAY;
  - rate-limited wildcard subscriptions;
  - datagrams plus per-item-stream for WebTransport.
  - **Not**: per-hop relative cache TTL, or symmetric Secure Objects as authentication.
- **NORM (RFC 5740/5401)**:
  - NACK only at boundaries or inactivity, `T_inactivity ≥ 1 s`;
  - one NACK per cycle, lowest needs first;
  - holdoff `(K+2)·GRTT`;
  - `SQUELCH` (advertise the repair window when asked for gone data), rate-limited to 2·GRTT;
  - `REPAIR_ADV` for unicast-feedback groups;
  - truncated-exponential random backoff, only if LAN multicast repair is ever added.
  - Receiver-driven (ALC) congestion control as a later LAN option: put first copies and repeats on separate groups or ports, so a congested receiver can drop repeats. [ASSESS, speculative]
- **Nanometrics (NMX/NAQS; NP/Apollo)**:
  - oldest-available sequence number in every data packet (`trail_seq`);
  - UDP push with repair requests served from the sender's store, while the gap is still within the store;
  - raw versus short-term-complete consumer modes with a max-tolerable-latency cutoff;
  - UDP for acquisition and in-order TCP (SeedLink) for distribution. Apollo notes that the in-order tier cannot carry late completion, which is canticle's two tiers joined at a ring.

---

## 9. Open items and unverified

- The RefTek RTP UDP details come from vendor pages and a PDF I could not open (window 16, adaptive RTO, DAS-initiated). A second source should confirm them.
- Nanometrics NP retransmission specifics (message format, who sends to whom through NAT, whether HTTP mode is used behind proxies) are from search excerpts only.
- WIN `sendt` buffering depth, and whether resends go to the requester or to the configured destination, are unverified. The source is on the blocked ERI host.
- GDI-link transport and ports are from Güralp manual snippets only.
- The biology is paper-level via search snippets. Only the two arXiv physics papers were read in full.
- The 4.1 KB and 20 KB per-socket figures were measured on loopback on one kernel (6.18.44). Ethernet skb truesize will differ.
- The RFC 8085 reading that RENEW counts as "return traffic" enabling more than 1 datagram per 3 s is my interpretation. The RFC ties rate to *loss detection*, so it holds only if RENEW actually carries loss statistics (lesson 4).

---

## 10. Source index

- **Clones**: see §0. Key paths:
  - `pd/moq-transport/draft-ietf-moq-transport.md`;
  - `pd/sc-seedlink/plugins/{q330plugin,lib330,reftek_plugin,reftek_libs,naqsplugin,descriptions,scream_plugin,scream2_plugin,win_plugin}`;
  - `pd/sc-seedlink/apps/seedlink/descriptions/seedlink.rst`;
  - `pd/fdsn-seedlink/protocol.rst`;
  - `pd/libslink/ChangeLog`;
  - `src/ringserver/doc/ringserver.md`, `src/ringserver/ChangeLog`;
  - `pd/rsudp/rsudp/{raspberryshake.py,packetloss.py}`;
  - `pd/nmxptool/{README.md,lib/nmxp_base.c,include/nmxp_data.h,src/nmxptool_getoptlong.c,no_dist/rapporto_tecnico_ingv/}`;
  - `pd/earthworm/src/data_exchange/{ringtocoax,coaxtoring,export,import_generic}`;
  - `pd/centaur_tools/Readme.md`;
  - `pd/w3c-webtransport/index.bs`;
  - `pd/wt-http3/draft-ietf-webtrans-http3.md`;
  - `pd/linux/{include/net/tcp.h,net/ipv4/tcp_input.c,net/ipv4/tcp_output.c,net/ipv4/tcp_recovery.c,Documentation/networking/ip-sysctl.rst}`;
  - `src/linux` for `Documentation/networking/tcp-thin.rst` via `git show`;
  - `src/nats.docs`, `src/mosquitto`.
- **RFCs** (`pd/rfc/*.json`, canonical at https://www.rfc-editor.org/rfc/rfcNNNN): 2887, 2974, 3208, 4987, 5401, 5681, 5740, 5775, 5827, 6298, 6330, 6726, 8084, 8085, 8985, 9002, 9221, 9293, 9308.
- **Measurement**: `scratchpad/pdexp/tcpmem.py` (run: `python3 tcpmem.py 4000`).
- **arXiv (read in full via alphaXiv)**:
  - https://arxiv.org/abs/1908.04057 (Mora & Nemenman);
  - https://arxiv.org/abs/2310.00062 (concentration sensing trade-offs).
- **Web (search snippets)**:
  - reftek.com/ref-tek-protocol-daemon-rtpd/;
  - reftek.com/case-study/leveraging-refteks-rtp-reliable-seismic-data-transmission-through-firewalls;
  - eri.u-tokyo.ac.jp/…/RTP.pdf;
  - nanometrics.ca Apollo Server data sheet;
  - epos-france.fr Centaur User Guide 17935R10;
  - ipgp.fr NanoCD docs (NAQSServer, Janus);
  - manual.raspberryshake.org/{udp,traces,firewallIssues}.html;
  - guralp.com/documents/html/MAN-MIN-0001/s5.html;
  - datatracker.ietf.org/doc/draft-ietf-moq-secure-objects/;
  - kegel.com/c10k.html;
  - blog.whatsapp.com/1-million-is-so-2011;
  - migratorydata.com/blog/migratorydata-solved-the-c10m-problem/;
  - mrotaru.wordpress.com/2013/10/10/scaling-to-12-million-concurrent-connections-how-migratorydata-did-it/;
  - c10m.robertgraham.com/p/manifesto.html.
- **Biology (search snippets)**:
  - science.org/doi/abs/10.1126/science.1228456 (Weber 2013);
  - pnas.org/doi/10.1073/pnas.0334864100 (Proudfoot 2003);
  - nature.com/articles/ni.2889 (Ulvmar 2014);
  - nature.com/articles/ni.1675 (Pruenster 2009);
  - science.org/doi/10.1126/science.aay9792 (Tweedy 2020);
  - pmc.ncbi.nlm.nih.gov/articles/PMC4406842 (Kufareva 2015);
  - portlandpress.com/biochemsoctrans/article/52/3/1011 (2024);
  - nature.com/articles/25764 (Monks 1998);
  - science.org/doi/abs/10.1126/science.285.5425.221 (Grakoui 1999);
  - nature.com/articles/375148a0 (Valitutti 1995);
  - pnas.org/doi/10.1073/pnas.92.11.5042 (McKeithan 1995);
  - pubmed 24120362 (Huang 2013);
  - nature.com/articles/ni1304 (Huse 2006);
  - journals.aai.org/jimmunol/article/173/6/3647 (CD40L at the synapse);
  - nature.com/articles/ni0601_487 (citing Iezzi 1998);
  - pnas.org/doi/pdf/10.1073/pnas.91.22.10380 (Allen & Stevens 1994);
  - nature.com/articles/35069076 (Wilson & Nicoll 2001);
  - cell.com/fulltext/S0092-8674(09)00382-1 (Kopan & Ilagan 2009);
  - nature.com/articles/nature08959 (Sprinzak 2010);
  - Zigmond 1977, J Cell Biol 75:606 (via PMC25243).
