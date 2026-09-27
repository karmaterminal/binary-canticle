# binary-canticle: transport, discovery and the "membrane" (research notes)

Author: transport reader (retry run). Date: 2026-09-27. Repo baseline: `karmaterminal/binary-canticle` main `b46a45a`.

Labels used below:
- **[SAY]**: what a source states (repo doc, RFC, vendor doc, issue).
- **[DONE]**: what the repo has actually decided or implemented.
- **[ASSESS]**: my own judgment. Confidence is marked **HIGH**, **MED** or **LOW**.

## 0. Method and access limits (read this first)

- **WebFetch was egress-blocked** for every documentation host I tried: rfc-editor.org, ietf.org, datatracker, docs.aws.amazon.com, docs.cloud.google.com, learn.microsoft.com, docs.haproxy.org, nginx.org and tex2e.github.io. `www.haproxy.com` had already been denied by the proxy (403 CONNECT in `/__agentproxy/status`), and `git.zx2c4.com` was denied too. I did not route around these denials.
- **WebSearch worked.** Vendor facts marked "(search)" come from search-result excerpts of the cited URLs. I could not open the page itself, so treat those as **MED** unless a primary source is also cited.
- **Primary sources were read by `git clone` from GitHub, which was allowed.** All clones are sparse and live in the scratchpad `src/`:
  - HAProxy `haproxy/haproxy` @ `9e7c5d245f60e6cd8828dc20e973762184f02a63` (VERSION `3.5-dev7`, 2026-09-27), plus tags `v3.0.0`, `v3.2.0` and `v3.3.0`. File: `doc/configuration.txt` and friends.
  - nginx docs `nginx/nginx.org` @ `058813404c2622da433827f841850a3713d3636e`, under `xml/en/docs/stream/*.xml`.
  - Envoy `envoyproxy/envoy` @ `bf3d00bf6dee83c5af042440a3c58567aa081194`, file `docs/root/configuration/listeners/udp_filters/udp_proxy.rst`.
  - Nebula `slackhq/nebula` @ `7cfa47d569e8cf89623f6f7078ebbd95067d76a5`: `inside.go` and `examples/config.yml`.
  - EarthScope ringserver @ `4f034c83bdf4bc68e270f7bf02c4d01a60154e2d`: `README.md` and `doc/ringserver.md`.
  - Linux `torvalds/linux` @ `fd179f8a05be3ccae366b9b96e176b51fbe54aab`: `Documentation/networking/nf_conntrack-sysctl.rst`.
  - **RFC text**: English originals are taken from `tex2e/rfc-translater` @ `55f03a2295911c81b67875b793b3744417302f63`, in `data/*/rfcNNNN-trans.json`. They were converted locally, and section numbers were recovered from headings. The canonical URL for each is `https://www.rfc-editor.org/rfc/rfcNNNN`.
- GitHub MCP was used read-only (issue #30).

---

## 1. Repo baseline: what binary-canticle says about transport today

### 1.1 What the repo decided

- [SAY/DONE, v0.1 spec §3.1] The wire is UDP on port `9999`, using IPv4 broadcast `<subnet>.255` or multicast `239.13.13.13`. The spec says to "prefer multicast when supported … fall back to broadcast". Frames are "≤ 1472 bytes including IP+UDP headers" (`proto/protocol-spec-v0.1.md:109-121`, specifically `:114` and `:118`).
- [SAY/DONE] Scope-2, a single LAN, is "the scope binary-canticle v0.1 + v0.2 are designed for". There, "UDP broadcast/multicast is free" (`proto/scope-framing-and-noosphere-mapping.md:67-80`).
  - Scope-3 is a "relay station that bridges UDP broadcast … via WireGuard / TLS / SSH tunnel, OR … DTN". There, "relay registers as a proxy-station" and "relay verifies frame signatures and re-signs … (or simply forwards signed frames)" (`:84-99`).
  - The summary table is at `:263`.
- [SAY/DONE] NAT and cross-subnet are "not in v0.2 base-layer scope" (`proto/stations-and-streams-v0.2.md:156`).
- [SAY/DONE] No subscriber tracking:
  - "No subscriber tracking at sender side is load-bearing" (`proto/stations-and-streams-v0.2.md:79`).
  - "No subscription registry at the sender" (`proto/explicit-non-goals.md:86`).
  - "No participant-table / DDS-style discovery" (`:87`).
- [SAY/DONE] Carrier-beacon: 1 Hz, about 35 B CBOR, fields `{station_id u128, head_seq u64, wallclock_ns i64, schema_version u8, streams[{stream_id u32, default_ttl u32}]}` (`proto/stations-and-streams-v0.2.md:13-45`).
- [SAY/DONE] Discovery (§5):
  - SRV at `_canticle._udp.<zone>` with default zone `thornfield.local.`. The TXT record sits at a *different* name, `silas-stations.thornfield.local.` (`proto/protocol-spec-v0.1.md:252-280`, specifically `:257`, `:262` and `:272-279`).
  - A static `~/.binary-canticle/stations.toml` fallback is a MUST (`:305`).
- [SAY/DONE] Auth is not settled. The documents disagree:
  - v0.1 §9.4 proposes HMAC-SHA256 with a pre-shared frond key (`protocol-spec-v0.1.md:494`).
  - The open question is "pre-shared frond-key vs. per-station Ed25519 keys with frond-CA" (`:588`).
  - v0.2 says "base-layer canticle assumes trust-of-LAN" and makes Ed25519 a "v0.3 overlay" (`stations-and-streams-v0.2.md:124-126`).
  - Scope-2 says "pre-shared HMAC" (`scope-framing…:75`, `:263`).
- [DONE, code] The only running transport is `prototype/ringserver-udp-cue`, landed at `65e6705`:
  - The listener refuses anything but IPv4 loopback (`canticle_receptor/udp.py:21-22`).
  - `MAX_PACKET_SIZE = 1200` (`canticle_receptor/codec.py:14`).
  - Every envelope must carry an Ed25519 signature, and verification fails closed (README).
  - Ringserver is TCP-only: "supported protocols are all TCP-based: DataLink, SeedLink and HTTP/WebSocket" (ringserver `README.md:5`; prototype `README.md` cites v4.5.4).
- [SAY] Issue #30 (2026-05-15) proposes three layers: UDP multicast carrier, an HAProxy "membrane", and prince verbs `LISTEN/SEND/HUSH/WHO`. It claims:
  - "**HAProxy 3.2+** (June 2025 release added native UDP load balancing; pre-3.2 was TCP/HTTP only)".
  - "Protocol interpreter via SPOE/Lua … *interpreting* BC protocol frames".
  - "Per-prince ACL state via stick-tables + Runtime API".
  - "once BC content is on multicast UDP, anything with a socket can listen".

### 1.2 Defects found in the baseline

Each defect is covered in detail in the sections below.

1. **The HAProxy premise in #30 is false for community HAProxy (HIGH).** Community HAProxy has no generic UDP proxying in 3.0.0, 3.2.0, 3.3.0 or 3.5-dev7. The doc text is identical in all four: `udp@` listeners are "supported only in log-forward sections":
   - `configuration.txt:6822-6830` @ 3.5-dev7;
   - `:5776-5778` @ v3.0.0;
   - `:6086-6088` @ v3.2.0;
   - `:6323-6325` @ v3.3.0.

   See §5.
2. **The multicast address `239.13.13.13` is in a range RFC 2365 says to leave unassigned (HIGH).** RFC 2365 §6.2.1 says "239.0.0.0/10, 239.64.0.0/10 and 239.128.0.0/10 are unassigned and available for expansion … should be left unassigned until the 239.192.0.0/14 space is no longer sufficient." Use `239.255.0.0/16` (Local Scope, §6.1) or a sub-range of `239.192.0.0/14` (Organization Local, §6.2) instead.
3. **"≤ 1472 bytes including IP+UDP headers" is arithmetically wrong (HIGH).**
   - 1472 is the maximum UDP *payload* for IPv4 at MTU 1500 (1500 − 20 − 8). With headers counted, the figure would be 1500.
   - For IPv6 at MTU 1500 the payload maximum is 1452.
   - Every overlay the owner might use is smaller still:
     - WireGuard's default MTU is 1420 (search: Wikipedia and other results).
     - Tailscale's `tailscale0` is 1280 (search: tailscale issue #246 and blog).
     - Nebula's default is 1300 ("safe setting is (and the default) 1300 for internet based traffic", `nebula/examples/config.yml:267-268`).
   - A 1472-byte payload would be fragmented or dropped on all of them. The prototype's 1200 is the right number. See §3.5.
4. **`.local` is mDNS-only by definition (HIGH).** RFC 6762 §3 says "any fully qualified name ending in '.local.' is link-local" and "Any DNS query for a name ending with '.local.' MUST be sent to the mDNS IPv4 link-local multicast address 224.0.0.251 (or … FF02::FB)."
   - So `_canticle._udp.thornfield.local.` cannot be served by a unicast DNS server, and cannot carry DNSSEC.
   - The TXT at `silas-stations.…` is not reachable from the SRV name, so it is not DNS-SD-conformant (RFC 6763 puts SRV and TXT on the same service-instance name).

   See §6.
5. **"anything with a socket can listen" holds only inside one L2 multicast domain (HIGH).**
   - It does not hold for cloud VPCs, Tailscale/WireGuard/Nebula, most Kubernetes CNIs, Docker Desktop, or the internet.
   - A cross-network listener must obtain the stream through a relay, and behind NAT the listener must initiate. See §2 and §3.

---

## 2. Q1: LAN multicast without special hardware

### 2.1 Facts

**Wired switching**

- [SAY, RFC 4541 §1] A switch without IGMP snooping floods multicast like broadcast: "Packets will be flooded into network segments where no node has a…" interest. This means cheap unmanaged switches "just work" for small fleets. Every port gets every group, which is fine at canticle's rates.
- [SAY, RFC 4541 §2.1.2] Snooping switches handle unregistered groups inconsistently: "If a switch receives an unregistered packet, it must forward that packet on all ports to which an IGMP router is attached. **A switch may default to forwarding unregistered packets on all ports.**" Some models flood unregistered groups and some drop them.
- [SAY, RFC 2236 §8.4] The IGMPv2 Group Membership Interval = Robustness × Query Interval + Query Response Interval. With defaults of 2 × 125 s + 10 s, that is **260 s**.
- [SAY, search: Cisco community, HamSCI igmp-querier] With snooping on and **no querier**, streams stop after about 260 s. The switch opens the port on the host's initial join. Hosts only re-report when queried, so the entry ages out.
  - Fixes: enable the switch's IGMP querier, run a router, or run a software querier (for example https://github.com/HamSCI/igmp-querier).
  - Refs: https://community.cisco.com/t5/switching/multicast-traffic-stops-flowing-after-some-time-when-using-igmp/td-p/2819455 and https://github.com/HamSCI/igmp-querier.

**Wi-Fi (RFC 9119)**

- [SAY, §3.1.1] "since there are no ACKs for multicast packets, it is not possible for the AP to know whether or not a retransmission is needed."
- [SAY, §3.1.2] Multicast is "generally transmitted at the slowest rate of all the connected devices. This is also known as the basic rate". There can be "more than 3 orders of magnitude difference in the transmission rate between multicast/broadcast versus optimal unicast". Lower rate means more airtime and a larger interference area.
- [SAY, §3.1.4] "Multicast traffic is delayed in a wireless network if any of the STAs in that network are power savers." §4.3 adds "In practice, most APs will send a multicast every 30 packets."
- [SAY, mitigations] §4.6.1 says "it's a good choice to use unicast instead of multicast over the Wi-Fi link". §4.6.3 covers DMS, where individually addressed frames "are acknowledged and are buffered for power-save STAs". GCR (802.11aa) exists but needs support on both AP and STA.
- [SAY, search: OpenWrt #23140, openwrt-devel 2015] Linux/OpenWrt `multicast_to_unicast` requires the AP to isolate stations (`ap_isolate=1`), with the bridge hairpinning traffic back. Guest or "client isolation" SSIDs block station-to-station multicast outright.
  - https://github.com/openwrt/openwrt/issues/23140
  - https://lists.openwrt.org/pipermail/openwrt-devel/2015-June/007744.html

**Containers and orchestration**

- [SAY, search] Docker:
  - Containers on one bridge network can multicast to each other.
  - Traffic between hosts over the Swarm VXLAN overlay does not carry multicast (moby/libnetwork#552).
  - macvlan/ipvlan give containers LAN L2 presence, but only on Linux hosts. The macvlan driver "only works on Linux hosts … not supported on Docker Desktop for Mac/Windows".
  - ipvlan L3 mode has no broadcast or multicast.
  - [ASSESS, MED] `--network host` on Linux behaves like the host. Docker Desktop's "host" is the VM's network, so LAN multicast will not reach it.
- [SAY, search/docs] Kubernetes:
  - "Most CNI plugins, such as Calico, Flannel … do not support multicast" (search).
  - **Cilium** has "Multicast Support (Beta)". It requires VXLAN tunnel mode, supports IPv4 only, and needs kernel ≥ 5.10 on amd64 or ≥ 6.0 on arm64 (https://docs.cilium.io/en/stable/network/multicast/).
  - **Antrea** multicast has been beta since 1.12 and is disabled by default (search: Medium/Antrea).
  - OVN-Kubernetes has a per-namespace multicast enable. I did not verify this in this session (MED).
  - `hostNetwork: true` pods behave like the node.

**Cloud**

- [SAY, search: AWS docs] AWS VPCs have no native multicast. **Transit Gateway multicast** exists:
  - It supports "IGMPv2 … not the later version 3".
  - Non-Nitro instances cannot be senders.
  - It is not supported over Direct Connect, Site-to-Site VPN, peering or TGW Connect attachments.
  - Ref: https://docs.aws.amazon.com/vpc/latest/tgw/tgw-multicast-overview.html and https://docs.aws.amazon.com/vpc/latest/tgw/how-multicast-works.html
- [SAY, search: GCP docs] "VPC networks do not support broadcast or multicast addresses within the network" (https://cloud.google.com/vpc/docs/vpc). Newer **Cloud Multicast** is a managed service using IGMP group membership, with multicast domains and group ranges. It covers Compute Engine only, and does not work over Interconnect or VPN (https://docs.cloud.google.com/vpc/docs/multicast/overview).
- [SAY, search: Azure FAQ] "multicast, broadcast, IP-in-IP encapsulated packets, and Generic Routing Encapsulation (GRE) packets are blocked in virtual networks" (https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-faq).

**Overlays**

- [SAY, search: ZeroTier docs] ZeroTier emulates Ethernet, so broadcast and multicast work. There is a catch: `multicastLimit` defaults to **32**, the "Maximum number of recipients per multicast or broadcast". If more members have joined a group, "the sender chooses a random subset" (https://docs.zerotier.com/protocol/; https://pkg.go.dev/github.com/zerotier/terraform-provider-zerotier/pkg/zerotier; ZeroTierOne#1024).
- [SAY, search: Tailscale docs/issues] Tailscale is a layer-3 tun device. Multicast and mDNS do not cross it; the open feature requests are tailscale/tailscale#11134, #1013 and #8884 (https://tailscale.com/docs/concepts/tailscale-osi).
- [SAY, code: Nebula @7cfa47d] Nebula has no multicast fan-out. In `inside.go:76-79`, multicast is dropped if `tun.drop_multicast` is set. Otherwise the destination is looked up as a unicast VPN address (`:81-104`), and the packet is dropped with "vpnAddr not in our vpn networks or in unsafe networks". `tun.drop_local_broadcast` / `drop_multicast` defaults are at `examples/config.yml:261-264`.
- [ASSESS, MED] WireGuard's cryptokey routing is unicast. A multicast packet can go to at most the one peer whose AllowedIPs cover 224.0.0.0/4, so there is no fan-out.

**Scoping**

- [SAY] RFC 2365:
  - §6.1: `239.255.0.0/16` is Local Scope.
  - §6.2: `239.192.0.0/14` is Organization Local.
  - §6.2.1: keep 239.0/10, 239.64/10 and 239.128/10 unassigned.
  - §7: "packets sent to groups covered by 239.255.0.0/16 must not be forwarded across any link for which a scoped boundary is defined."
- [SAY] RFC 5771 §10: "Addresses in the Administratively Scoped Block are for local use within a domain."
- [SAY] RFC 4291 §2.7 IPv6 scop values: 2 = Link-Local, 4 = Admin-Local, 5 = Site-Local, 8 = Organization-Local, E = Global. RFC 7346 defines 3 = Realm-Local (for example, mesh). `ff02::` never leaves the link; `ff05::` is site scope, which routers must be configured for.
- [SAY] RFC 8815 deprecates ASM for *interdomain* multicast but "does not make any statement on the use of ASM within a single domain".
- [ASSESS, HIGH] Linux sends multicast with IP TTL 1 by default (`IP_MULTICAST_TTL`). Canticle multicast therefore stays on the link unless an app raises the TTL *and* multicast routing (PIM) exists. That almost never happens in homes, labs or clouds.

**Same-host fan-out**

- [ASSESS, HIGH] Several processes on one host can each receive a multicast or broadcast datagram if they bind with `SO_REUSEADDR`/`SO_REUSEPORT`: each socket gets a copy. Unicast with `SO_REUSEPORT` is *load-balanced*, so only one socket gets each datagram.
- Consequence: "N sessions on one host all hearing a unicast relay stream" needs a per-host receptor daemon that fans out locally. `scope-framing…:72` already proposes a per-host daemon.

### 2.2 When multicast is viable

| Environment | Multicast | Notes |
|---|---|---|
| One wired L2 segment, unmanaged switch | **Yes** | Flooded to all ports. |
| Managed switch with snooping, querier present | **Yes** | |
| Managed switch with snooping, no querier | **Breaks after ~260 s** | Needs a querier. |
| Wi-Fi | **Works but degraded** | Basic rate, no ACK, DTIM delay. Blocked by client isolation. Prefer unicast (RFC 9119 §4.6.1). |
| Linux VMs/containers bridged to the LAN (host net, macvlan) | **Yes** | |
| Docker bridge | **Only within one bridge** | |
| Docker Desktop, Swarm overlay | **No** | |
| Kubernetes default CNIs | **No** | Cilium (beta, VXLAN) and Antrea (beta) are opt-in. |
| AWS VPC | **No** | Except TGW multicast (IGMPv2). |
| GCP | **No** | Except the Cloud Multicast managed service. |
| Azure | **No** | |
| ZeroTier | **Yes** | Raise `multicastLimit` above fleet size (default 32). |
| Tailscale, WireGuard, Nebula | **No** | |
| Internet | **No** | Interdomain is SSM-only in theory (RFC 8815). In practice, AMT relays (RFC 7450) are rare. |

### 2.3 Recommendation for Q1

- **R1.1 (HIGH).** Keep LAN multicast as an *optional fast path*. Do not make it a dependency. Define a transport abstraction with three bindings:
  - (a) LAN multicast;
  - (b) unicast lease via relay, which is universal (see §3);
  - (c) host-local (loopback or unix socket) from a per-host receptor daemon.

  Binding (b) is the one guaranteed to work everywhere. Make (b) the default for Claude Code and OpenClaw clients that are not known to be on the fleet VLAN.
- **R1.2 (HIGH).** Change the default group to `239.255.x.y` (IPv4 Local Scope), for example `239.255.13.13`, or allocate from `239.192.0.0/14`. Add an IPv6 twin at `ff02::…` (link) and optionally `ff05::…` (site). Keep IP TTL at 1 by default.
- **R1.3 (MED).** Use ASM with one group per "band" and filter by station/stream at the application layer. That is what the carrier-beacon and receptor already do, and it keeps IGMP state trivial. Per-station groups buy nothing on unmanaged switches.
- **R1.4 (HIGH).** Ship a `canticle doctor` self-test:
  - Join the group and send a probe beacon. See whether the probe's own beacon comes back via `IP_MULTICAST_LOOP` and whether peers answer in their beacons.
  - Wait more than 260 s and check again, to catch the missing-querier failure.
  - If it fails, fall back to subnet broadcast. Broadcast has the same L2 reach but needs no IGMP; it is fine for fewer than about 10 hosts and blocked in clouds. If that fails too, fall back to the relay lease.
- **R1.5 (MED).** On Wi-Fi-heavy fleets, do not rely on multicast. Either run the relay and use unicast leases, or enable AP multicast-to-unicast. That forces AP isolation plus bridge hairpin, so test it.
- **R1.6 (HIGH).** For ZeroTier, set `multicastLimit` ≥ expected listener count. Otherwise the network silently delivers to a random 32.

---

## 3. Q2: internet UDP listeners

### 3.1 NAT facts

- [SAY, RFC 4787 §4.3] "REQ-5: A NAT UDP mapping timer MUST NOT expire in less than two minutes … A default value of five minutes or more … is RECOMMENDED." "REQ-6: The NAT mapping Refresh Direction MUST have a 'NAT Outbound refresh behavior' of 'True'." Refresh by *inbound* packets is optional (§13 explains why it is a security risk).
- [SAY, RFC 8085 §3.5] Keep-alives "SHOULD NOT [be transmitted] more frequently than once every 15 seconds". It also warns that "empirical evidence suggests that a significant fraction of currently deployed middleboxes unfortunately use shorter timeouts", and says to add jitter. It also says keep-alives are "NOT RECOMMENDED for general use", so use them only when needed, as here.
- [SAY, Linux doc @fd179f8 `Documentation/networking/nf_conntrack-sysctl.rst:194-200`] `nf_conntrack_udp_timeout` defaults to **30** s. `nf_conntrack_udp_timeout_stream` defaults to **120** s, and applies once traffic is seen both ways. Most home routers and CGNAT boxes run Linux conntrack.
- [SAY, search: wireguard.com quickstart] WireGuard: "A sensible interval that works with a wide variety of firewalls is 25 seconds" (PersistentKeepalive).
- [ASSESS, HIGH] A listener behind NAT must send first, and must keep sending outbound at least every ~25 s. The relay→listener stream itself is not guaranteed to refresh the mapping (REQ-6 covers outbound only).
- [ASSESS, HIGH] The relay must reply from the same IP:port the listener sent to. Port-restricted or symmetric NATs drop anything else.
  - This matters for multi-homed relays and for `SO_REUSEPORT` socket pools.
  - HAProxy's docs flag the same trap: "for UDP, specific OS features are required when binding on multiple addresses to ensure the correct network interface and source address will be used on response" (`configuration.txt:6810-6814`).

### 3.2 The "no subscription" principle, reconciled

- [DONE] The repo forbids a subscription registry *at the sender* (`explicit-non-goals.md:86`, `stations-and-streams-v0.2.md:79`).
- [ASSESS, HIGH] Even LAN multicast already relies on subscription soft state. An IGMP join *is* a subscription: switches and routers hold it, and it expires (260 s) unless refreshed. The station never sees it.
- The internet equivalent is a **lease held by the relay/membrane, never by the station**:
  - The listener sends `LISTEN`, with filters and an optional capability.
  - The relay keeps `(src ip:port) → {filters, expiry}`.
  - The listener re-sends every ~20–25 s ± jitter. That one packet is both the lease renewal and the NAT keepalive.
  - A missed renewal lets the lease lapse after about 3 intervals.
- This keeps the station broadcast-only, so the non-goal survives.
- It does **not** survive issue #30's `WHO <station>` ("see who's tuned in"). The relay could expose an aggregate listener count at most. Recommend dropping `WHO` or redefining it as "stations heard" (from beacons), not "listeners".
- Prior art for this exact shape: **AMT, RFC 7450 §4.2.1.2**. The gateway sends a Request with a nonce. The relay "generates a message authentication code (MAC) … from the message source IP address, source UDP port, request nonce, and a private secret", and the gateway must echo that MAC in its Membership Update before traffic flows. In other words, a leased, return-routability-checked unicast replication of multicast. Canticle's relay is AMT-shaped, without requiring SSM infrastructure.

### 3.3 Relay tiers and fan-out cost

- [ASSESS, HIGH] Tier shape:
  - station(s) → LAN multicast or unicast → **edge relay (membrane)** → unicast fan-out to leased listeners;
  - optionally relay → relay chaining (subscribe once upstream, fan out many downstream).
- [SAY, search: IETF MoQ] Media over QUIC's relays do the same: "A Relay acts as a subscriber to receive tracks from upstream … and simultaneously acts as a publisher to forward those same tracks downstream … subscribe-once-fan-out-many". Hardening against congestion and DoS is where the effort goes (https://datatracker.ietf.org/doc/draft-ietf-moq-transport/). MoQT is a good template for relay semantics, not something to adopt.
- [ASSESS, MED] Cost model: egress ≈ listeners × Σ_streams(loop_rate × items × frame_bytes) + listeners × beacon_bytes.
  - Example: 1 station with 5 live items, each looped at 1 Hz at about 600 B, plus a 1 Hz beacon of about 100 B signed. That is about 3.1 KB/s, or about 25 kbit/s, per listener.
  - 1,000 listeners → about 25 Mbit/s and about 6k pps.
  - 10,000 listeners → about 250 Mbit/s and about 60k pps.
  - A single Go or Rust relay using `sendmmsg`/UDP GSO handles this. The Python prototype would not. For more than about 10k listeners, or for geography, add relay tiers.
  - **Loop frequency is the main bandwidth knob.** The membrane should enforce per-station byte budgets, attenuating by lowering loop rate before dropping items. That is the literal "cell membrane attenuation".
- [ASSESS, HIGH] One lease per *host* (the per-host receptor daemon), not per session. Otherwise 50 sub-agents on one laptop cost 50× bandwidth and 50 NAT mappings.

### 3.4 QUIC datagrams, WebTransport and DTLS

- [SAY, RFC 9221]
  - §2: "QUIC datagrams are subject to QUIC congestion control."
  - §5: "Although DATAGRAM frames are not retransmitted upon loss detection, they are ack-eliciting", and "DATAGRAM frames cannot be fragmented".
  - §3: support is negotiated via `max_datagram_frame_size` (0x20).
  - The sender "MUST either delay sending the frame until the controller allows it or drop the frame" (search excerpt).
  - For a lossy radio this is ideal: congestion simply sheds frames.
- [SAY, search: MDN, webrtc.ventures, caniuse] WebTransport `datagrams` gives browsers an unreliable, unordered channel over HTTP/3. Support: Chrome 97+, Edge 98+, Firefox 114+, and **Safari 26.4 (March 2026)**, which made it "Baseline" (MED; secondary source).
  - https://developer.mozilla.org/en-US/docs/Web/API/WebTransport/datagrams
  - https://webrtc.ventures/2026/04/webtransport-is-now-baseline-what-it-means-for-real-time-media/
- [SAY, HAProxy 3.5-dev7 docs] No mention of WebTransport, CONNECT-UDP (RFC 9298) or RFC 9297 datagrams (grep of `configuration.txt`). HAProxy's QUIC is for HTTP/3 request/response.
- [SAY, Envoy docs] `udp_proxy` can "tunnel raw UDP over HTTP requests" (`udp_proxy.rst:119-128`) and has an `http_capsule` session filter.
- [ASSESS, MED] Browser listeners, such as the ews dashboard, get two paths:
  - (a) **WebTransport datagrams** terminated by the canticle relay itself, for example with Go `quic-go/webtransport-go` or Rust `wtransport`. This is the lossy, radio-true path.
  - (b) **WebSocket** SeedLink/DataLink from ringserver (`doc/ringserver.md:264-272`: `/seedlink`, `/datalink`). This path is reliable and uses replay-from-ring, and is where HAProxy fits (§5).
- [SAY, RFC 9147 §5, §5.1] DTLS 1.3 "reuses TLS 1.3's 'cookie' extension to provide a return-routability check … an important DoS prevention mechanism for UDP-based protocols". In DTLS 1.2 this was HelloVerifyRequest.
- [ASSESS, MED] Use DTLS or QUIC only for relay↔listener links that need confidentiality, meaning private stations. Public or fleet broadcast content is better served by per-frame signatures (§7), which survive relays and multicast untouched. Do not put DTLS on multicast; it has no group mode.

### 3.5 MTU and sizes

- [SAY, RFC 9000 §14] "QUIC assumes a minimum IP packet size of at least 1280 bytes … maximum datagram size of 1232 bytes for IPv6 and 1252 bytes for IPv4". QUIC fixes "the smallest allowed maximum datagram size of 1200 bytes" (§14.1).
- [SAY, RFC 8085 §3.2] An application "SHOULD NOT send UDP datagrams that result in IP packets that exceed the Maximum Transmission Unit (MTU) along the path". Without PMTUD, stay under EMTU_S; for IPv6 that is 1280. Also: "some NATs and firewalls drop IP fragments", and each datagram should be "received independently".
- [ASSESS, HIGH] Use **1200 bytes as the maximum canticle UDP payload everywhere**. That matches the prototype `codec.py:14`, is safe over Nebula (1300), Tailscale (1280) and IPv6 minimum MTU, and removes the need for a separate LAN profile.
- [ASSESS, MED] If frames must also fit **WebTransport datagrams** on a 1200-byte path, the app payload budget is about 1100–1150 B. QUIC short header, AEAD tag (16), DATAGRAM frame type and length, and the WT quarter-stream-id eat about 30–60 B. Recommend a canonical frame ≤ **1100 B** so one frame maps 1:1 onto raw UDP, relay envelopes and WT datagrams. The 1472 "LAN" figure should be dropped; it buys about 20% and costs portability.

### 3.6 FEC

- [ASSESS, MED] Items already **loop until TTL**. The loop is a repetition code, and a late joiner or a lossy listener gets another chance each cycle. Add jitter to loop schedules so burst loss does not kill every copy.
- Real FEC (Reed-Solomon RFC 5510, RaptorQ RFC 6330) is only worth it for multi-fragment items (spec §3.4, `frag`), for example XOR parity per k fragments.
- [SAY, RFC 4082 §4] "reliable multicast tools based on forward error correction are highly susceptible to denial of service due to bogus packets". Authenticate before decoding. Low priority.

### 3.7 Recommendation for Q2

- **R2.1 (HIGH).** Define a relay-held soft-state lease protocol with messages `HELLO → COOKIE → LISTEN(cookie, filters[, capability]) → stream …`, and `RENEW` every 20–25 s ± 20% jitter. The lease lapses after about 75 s without renewal.
- **R2.2 (HIGH).** One lease per host daemon. Local fan-out to sessions goes over a unix socket or loopback.
- **R2.3 (MED).** Offer WebTransport-datagram egress from the relay for browsers, and the WebSocket SeedLink path for reliable, replayable dashboards.
- **R2.4 (HIGH).** Frame ≤ 1100–1200 B, with no IP fragmentation, ever.

---

## 4. Q3: UDP abuse (reflection and amplification)

### 4.1 Facts

- [SAY, RFC 8085 §6] "Applications that respond to short requests with potentially large responses are a potential vector for amplification attacks … That could mean authenticating the sender before responding; noting that the source IP address of a request is not a useful authenticator, because it can easily be spoofed."
- [SAY, RFC 9000 §8] Before address validation, an endpoint "MUST limit the amount of data it sends to the unvalidated address to three times the amount of data received". §8.1.2 covers Retry tokens.
- [SAY, HAProxy docs @3.5-dev7] HAProxy exposes this for QUIC:
  - `tune.quic.fe.sec.retry-threshold` (default 100 half-open) auto-enables Retry (`configuration.txt:5278-5290`).
  - `quic-initial` rules can `accept | dgram-drop | reject | send-retry` on `src`/`dst` ACLs "prior to any connection element instantiation" (`:12364-12393`).
- [SAY, RFC 9147 §5.1] "An attacker can use the server as an amplifier by sending connection initiation messages with a forged source address that belongs to a victim." DTLS borrows the "stateless cookie technique used by Photuris [RFC2522] and IKE".
- [SAY, RFC 7450 §4.2.1.2] AMT's relay MAC over (src IP, src port, nonce, secret) is the same idea applied to multicast relays.
- [SAY, search: CISA https://www.cisa.gov/news-events/alerts/2014/01/17/udp-based-amplification-attacks] Bandwidth amplification factor = response size / request size. The search excerpt gives DNS with EDNS0 at about 70:1 (60 B → about 4,000 B), NTP up to 4,670×, and memcached up to about 51,000×. The DNS 28–54× and NTP 556.9× figures from CISA's own table are from memory, because the page itself was not fetched.
- [SAY, RFC 2827 (BCP 38) §1] Ingress filtering "will prohibit an attacker within the originating network from launching an attack … using forged source addresses". [SAY, search: CAIDA Spoofer https://spoofer.caida.org/summary.php] About 24% of observed netblocks and 25% of ASes still allow spoofing. **Assume spoofed sources exist.**
- [SAY, RFC 8085 §6] GTSM (TTL 255 check) can be used "when the intended endpoint is on the same link". This is useful for LAN-only control messages.
- [SAY, RFC 4082 §2.1] A receiver that buffers packets awaiting authentication must protect itself from "a flood of bogus packets". The same applies to any receptor ring.

### 4.2 Assessment and recommendation

A canticle relay that starts streaming in response to one small `LISTEN` is a **perfect reflector**. A spoofed `LISTEN` would aim a multi-KB/s stream at a victim until the lease lapses; with 10k spoofed leases, that becomes a DDoS. Mitigations:

- **R3.1 (HIGH).** Require a **stateless cookie round-trip before any stream**:
  - `COOKIE = trunc16(HMAC(relay_secret_epoch, src_ip ‖ src_port ‖ epoch))`, the same shape as DTLS HRR, QUIC Retry and AMT.
  - Every pre-validation response must be ≤ the request that triggered it. Pad `HELLO` to ≥ the `COOKIE` reply size. This is stricter than QUIC's 3×, and cheap.
- **R3.2 (HIGH).** Renewals must carry the cookie. Rotate the secret per epoch, accepting current and previous.
- **R3.3 (HIGH).** Short leases (≤ ~75 s). Per-lease byte budget. Per-source-IP and per-/24 (IPv4) or per-/56 (IPv6) caps on lease count and bytes/s. A global egress cap. Enforce at two layers:
  - in the relay;
  - in the kernel, as an nftables `meter` keyed on `ip saddr` with `limit rate`, applied to the lease port (§5.4).
- **R3.4 (HIGH).** Stay silent on everything unauthenticated: no errors, no "status" or "list stations" replies over UDP (the lesson of NTP `monlist` and memcached `stats`). Station catalogs belong in DNS (§6) or over TCP/HTTPS.
- **R3.5 (HIGH).** Station ingress, meaning who may *publish* into the relay, needs a valid Ed25519 signature and an allowlisted key before anything is looped or re-broadcast. Otherwise the relay amplifies attacker content to every listener, which is a content-amplification attack even without IP spoofing.
- **R3.6 (MED).** Apply BCP 38 at the fleet's own edge, for example nftables `fib saddr . iif oif missing drop` or `rp_filter`, so fleet hosts cannot spoof either.
- **R3.7 (MED).** On LAN-only control messages, where a hop count applies, use a GTSM-style check: send with TTL 255, and accept only if received with 255.

---

## 5. Q4: HAProxy, and what the membrane should be

### 5.1 Community HAProxy (2.x/3.x): what it does with UDP (HIGH, primary docs)

- **QUIC/HTTP3 frontends** (`quic4@`/`quic6@`, `configuration.txt:6845-6858`), with the QUIC-specific `quic-initial` filtering and Retry described in §4.1. This is HTTP/3 only: no WebTransport, no CONNECT-UDP, and no raw datagram passthrough.
- **Syslog `log-forward` sections** (§12.6, `:32646-32765`; added in 2.3 per https://www.haproxy.com/blog/announcing-haproxy-2-3):
  - `dgram-bind <addr>` receives UDP syslog: "silently ignored as irrelevant for UDP/syslog case" for most bind params (`:32667-32672`).
  - The available keywords are only `backlog`, `bind`, `dgram-bind`, `log`, `maxconn`, `timeout client`, `option assume-rfc6587-ntf`, `option dont-parse-log` and `option host`.
  - **There are no ACLs, no stick-tables, no `tcp-request` rules and no rate limits in log-forward.**
- **Log backends** (`mode log`): "Log backends support UDP servers by prefixing the server's address with the 'udp@' prefix" (`:9914-9922`).
- **DNS resolvers** over UDP (`:20438-20480`).
- The `udp@`/`udp4@`/`udp6@` bind prefixes are "supported only in log-forward sections" (`:6822-6830`). The same sentence appears at v3.0.0 `:5776-5778`, v3.2.0 `:6086-6088` and v3.3.0 `:6323-6325`. **So "HAProxy 3.2+ added native UDP load balancing" (issue #30) is false for the community edition.**
- [SAY, search: https://www.haproxy.com/solutions/udp-load-balancing, GitHub haproxy#1963, discourse 10147] "HAProxy Community speaks UDP for DNS resolution and syslog, but it does not load balance them. General-purpose UDP load balancing … is available only in HAProxy Enterprise."
- **Lua** has `core.tcp()` sockets (`doc/lua-api/index.rst:884`) and no UDP socket class. **SPOE** (`doc/SPOE.txt`) never mentions UDP. So #30's "SPOE/Lua interpreting BC protocol frames" at the UDP boundary is not possible in community.
- [ASSESS, LOW, a hack only] `log-forward` with `option dont-parse-log` and `log … format raw` (`:32724-32730`, `:32567`) could in principle forward raw datagrams to a *static* list of UDP targets. With `sample` it can split them; without `sample` every target gets every line.
  - It is one-way, has no leases, no NAT awareness and no ACLs, and it applies log `maxlen` and framing.
  - It is not a membrane. Mentioned only so nobody rediscovers it and builds on it.

### 5.2 HAProxy Enterprise and ALOHA (MED, search excerpts; haproxy.com blocked)

- The **Enterprise UDP Module** adds a `udp-lb` section:
  - `dgram-bind` listener; `balance` / `hash-type` / `hash-balance-factor`;
  - `use-server … if/unless <cond>`, which implies ACLs on at least the source IP;
  - a max datagram payload setting that defaults to 1472 (max 65507);
  - "udp-lb sections don't inherit settings from defaults".
  - Examples cover RADIUS, syslog and DNS.
  - Refs: https://www.haproxy.com/documentation/haproxy-enterprise/enterprise-modules/udp-load-balancing/reference/ and https://www.haproxy.com/blog/load-balancing-radius-with-haproxy-enterprise-udp-module
- **Not verified:** whether `udp-lb` supports stick-tables, per-source rate limits, or any 1:N fan-out. It is described as load balancing, which is 1:1 to one chosen server, not replication.
- **ALOHA** does UDP via LVS (L4) and a "Layer7 tab" UDP LB (https://www.haproxy.com/documentation/haproxy-aloha/load-balancing/layer-4/load-balance-udp/).

### 5.3 Where HAProxy (community) genuinely fits (HIGH)

- **TCP/TLS/WebSocket replay and dashboard tier in front of ringserver** (SeedLink 18000, DataLink 16000, HTTP/WebSocket):
  - TLS termination and HTTP/2/3 for web.
  - Rate-limit new connections with ACLs and stick-tables, for example `tcp-request connection track-sc0 src` plus `tcp-request connection reject if { sc0_conn_rate gt 10 }` (`configuration.txt:14431-14440`).
  - Pass the client IP to ringserver with `send-proxy-v2` (`:19921`). ringserver accepts it with the `PROXYv2` listener flag, which ringserver says to use only on ports reachable solely by trusted proxies (`doc/ringserver.md:233`).
  - ringserver itself adds `-M maxclientsperIP`, `-m maxclients` (default 600), `WriteIP` and `TrustedIP` (`doc/ringserver.md:69-73`, `:136-146`), TLS (`:231`), and WebSocket `/seedlink` and `/datalink` (`:264-272`).
  - This is the path the ews-concept-new and nerv-ui dashboards should use.
- **HTTP control plane for the membrane.** Guard `LISTEN`/`HUSH` capability issuance, station key registration and policy edits behind HAProxy with ACLs and rate limits. Stick-tables plus the Runtime API (`set table`, `clear table`) can hold per-prince allow/deny *for the TCP/HTTP tier* (MED; not re-verified in this session).
- **HTTP/3 QUIC front door** for normal web, with `quic-initial` source ACLs and Retry.
- **Not** for raw canticle datagrams in community HAProxy. At most a log-forward hack, which should not be used.

### 5.4 Alternatives for a UDP membrane

- **nginx `stream`:**
  - `listen … udp` (1.9.13). "In order to handle packets from the same address and port in the same session, the reuseport parameter should also be specified" (`ngx_stream_core_module.xml:148-154`).
  - `proxy_responses` gives "the number of datagrams expected from the proxied server in response to a client datagram … a hint for session termination" (`ngx_stream_proxy_module.xml:331-343`).
  - `proxy_requests` sets when the UDP session binding is dropped (`:310-320`).
  - `limit_conn` limits "the number of connections per the defined key" (`ngx_stream_limit_conn_module.xml:19`). For UDP these are sessions (MED).
  - `proxy_download_rate` is "set per a connection" (`ngx_stream_proxy_module.xml:151-163`). Trac #2496 reports that UDP bandwidth is not limited by `proxy_upload_rate`/`proxy_download_rate` (https://trac.nginx.org/nginx/ticket/2496; search).
  - Verdict: 1:1 request/response proxy with coarse per-key limits. **No 1:N fan-out** (MED-HIGH).
- **Envoy `udp_proxy`:**
  - A "*non-transparent* proxy". Sessions are "index[ed] by the 4-tuple" and last until an idle timeout that defaults to 1 minute (`udp_proxy.rst:12-24`; search).
  - Optional per-packet load balancing (`:22-26`).
  - Sessions are limited by the cluster circuit breaker, "By default this is 1024" (`:55-57`).
  - A source-IP matcher routes datagrams to clusters (`:62-80`).
  - Session filters include `http_capsule`, `dynamic_forward_proxy` and `ext_authz`, and there is UDP tunneling over HTTP (`:117-128`).
  - Verdict: good L4 policy and routing, still **1:1**. It would need a custom filter to fan out.
- **Kernel shaping, which belongs on every relay host (HIGH):**
  - nftables per-source meters, for example `udp dport $LEASE_PORT meter lease4 { ip saddr limit rate 20/second } accept` then `drop`, with `ip saddr and 255.255.255.0` for /24 buckets. Syntax per https://wiki.nftables.org/wiki-nftables/index.php/Meters (search excerpts show the TCP form; UDP is identical).
  - Egress `tc` HTB or `police` to cap total relay bandwidth.
  - eBPF/XDP per-source token buckets if floods ever exceed what nftables handles. XDP drops "before the kernel allocates an sk_buff" (search: iximiuz labs https://labs.iximiuz.com/tutorials/ebpf-ratelimiting-dbc12915). This is a later optimisation.
- **Purpose-built relay in Go or Rust (HIGH, recommended).** Only a custom relay does what the membrane must do:
  - verify Ed25519;
  - apply station allowlists, TTL caps, per-station byte budgets and "amplification threshold" criteria;
  - dedup by `(station, stream, seq)`;
  - loop scheduling;
  - the cookie/lease handshake;
  - 1:N unicast replication with `sendmmsg`/GSO, and optionally WebTransport egress.
  - Size: a few thousand lines. Go (`quic-go`, `webtransport-go`, `x/net/ipv4` for multicast joins) or Rust (`quinn`, `wtransport`, `socket2`).

### 5.5 Recommendation for Q4

- **R4.1 (HIGH).** The "membrane" is a **canticle relay daemon**, a custom Go or Rust daemon, with nftables meters and a tc cap underneath. It is *not* HAProxy.
- **R4.2 (HIGH).** HAProxy (community) goes **beside** it, on the TCP tier:
  - TLS, ACL and stick-table rate limits in front of ringserver SeedLink/DataLink/WebSocket, with PROXYv2 so ringserver sees real client IPs;
  - the HTTPS control API for leases, capabilities and keys.
- **R4.3 (HIGH).** Correct issue #30:
  - Replace "HAProxy 3.2+ native UDP" with the facts above.
  - Move "health checks = relay criteria" and "SPOE/Lua interpreting BC frames" into the relay's policy module.
  - If you still want HAProxy-style policy data, have the relay read a stick-table-like key/value config over HAProxy's Runtime API, or simply use its own config. Do not build UDP policy inside HAProxy.
- **R4.4 (MED).** If a commercial box is acceptable, HAProxy Enterprise `udp-lb` could front a *pool* of relays for 1:1 load balancing of `LISTEN` traffic. It still does not replace the relay's fan-out.

---

## 6. Q5: discovery

### 6.1 Facts

- [SAY, RFC 2782] The format is `_Service._Proto.Name TTL Class SRV Priority Weight Port Target`. Clients "MUST attempt to contact the target host with the lowest-numbered priority"; weight gives proportional selection within a priority.
- [SAY, RFC 6763] DNS-SD adds a PTR at `_service._proto.domain` that lists **instance names** `<Instance>._service._proto.domain`. **SRV and TXT live on the instance name.**
  - §6.2 on TXT size: "intended to be small -- 200 bytes or less"; "under 400 bytes" fits a 512-byte message; "Using TXT records larger than 1300 bytes is NOT RECOMMENDED".
  - §6.4: "The key SHOULD be no more than nine characters long".
  - §6.1: each constituent string is ≤ 255 bytes.
  - §7.2: mDNS is "useful for up to a few hundred instances of a given service type, but probably not thousands".
- [SAY, RFC 6762 §3] `.local.` is link-local, and queries "MUST be sent to" 224.0.0.251 / FF02::FB.
- [SAY, RFC 8766 §1] "link-local Multicast DNS packets, by design, are not propagated onto other links". A Discovery Proxy republishes mDNS into unicast DNS.
- [SAY, RFC 9665 (SRP, June 2025)]
  - Registration via "DNS Update … using only unicast packets … without multicast".
  - Registration is authenticated "using SIG(0)", so a second requester "will not possess the SIG(0) key … its claim will be rejected".
  - Registrations have a **lease**, "on the order of two hours".
- [SAY, RFC 8375] `home.arpa.` is the special-use domain for residential or home networks, and is safe to serve from a local unicast DNS server. This is the correct replacement for `thornfield.local` if the zone is unicast.
- [SAY, RFC 6335] Service names go in the IANA registry; SRV's `_Service` label draws from it. `_canticle` should be registered, or at least checked for collisions, before any public use.

### 6.2 Recommendation for Q5

**R5.1 (HIGH).** Adopt real DNS-SD structure, used identically over mDNS on the LAN and over unicast DNS for the WAN.

WAN example (unicast DNS, DNSSEC-signed zone):

```
; enumeration
_canticle._udp.fleet.example.                 300 PTR  magi1._canticle._udp.fleet.example.
; optional subtypes = lenses (RFC 6763 §7.1), lets a tuner browse "threat" stations only
_threat._sub._canticle._udp.fleet.example.    300 PTR  magi1._canticle._udp.fleet.example.
; instance: where to send HELLO/LISTEN (relay) or where the LAN surface is
magi1._canticle._udp.fleet.example.           120 SRV  0 0 47113 relay1.fleet.example.
magi1._canticle._udp.fleet.example.           120 TXT  "txtvers=1" "sid=01J9Z…(ULID)"
                                                       "streams=threat,healing" "mode=lease"
                                                       "grp=239.255.13.13" "mtu=1100"
                                                       "k=ed25519:<base64 32B = 44 chars>"
                                                       "carrier=1"
```

- In the TXT, `mode=lease|mcast|bcast` says which transport binding applies. `grp` gives the LAN group and appears only in mDNS/LAN views. `carrier` is the beacon Hz.
- The whole TXT is ≈ 150–200 B, within RFC 6763 §6.2. All keys are ≤ 9 characters.
- `_canticle._tcp` SRV records point at the SeedLink/WebSocket replay tier, if present.
- LAN: the same records under `.local.` via mDNS (Avahi, Bonjour or `zeroconf` libraries). The repo's static `stations.toml` stays as the fallback (`protocol-spec-v0.1.md:305`).
- WAN registration: stations (or the relay on their behalf) register via **RFC 9665 SRP / DNS UPDATE + SIG(0)** (or TSIG), with leases of about 1–2 h. Registrations are refreshed by the relay, not by chatty sessions.

**R5.2 (HIGH).** Keep the repo's split: DNS answers "where is the surface / relay and which key signs this station", and the 1 Hz carrier-beacon answers "who is alive now and where is the head". It is already stated at `stations-and-streams-v0.2.md:35-39` and `protocol-spec-v0.1.md:238-250`. Do not push liveness into DNS.

**R5.3 (MED).** TTLs:
- PTR 300 s; SRV/TXT 60–300 s. Station churn is slow and liveness comes from the beacon.
- Use negative-cache TTLs (SOA minimum) of about 60 s so newly registered stations appear quickly.
- On key rotation, publish the old and new `k=` values side by side for at least one TTL.

**R5.4 (MED).** Authenticity of discovery. A TXT-published key is only as good as the path that delivered it:
- On the WAN: sign the zone with **DNSSEC** and require a validating resolver in the relay and daemon (DANE-style trust in `k=`). Or pin keys out of band in `stations.toml` or a signed fleet manifest.
- On mDNS there is no DNSSEC. Treat mDNS-learned keys as trust-on-first-use or require pinning.
- [ASSESS] For "thousands of agents responding to a security threat", key pinning via a signed fleet manifest (Ed25519 root) is more robust than DNSSEC operations for a small team.

**R5.5 (HIGH).** Move the default zone off `.local.` for unicast use (`home.arpa.` or a real domain), and put the TXT on the SRV owner name.

---

## 7. Q6: per-frame authenticity for a lossy broadcast

### 7.1 Facts

- [SAY, RFC 8032] Ed25519 has a 32-octet public key and a 64-octet signature: R‖S, split "into two 32-octet halves" in §5.1.7. §1 claims "high performance on a variety of platforms".
- [SAY, search: https://ed25519.cr.yp.to/ and paper https://ed25519.cr.yp.to/ed25519-20110705.pdf] About 273k cycles per verify; batch verification of 64 is under 134k cycles per signature. "a quad-core 2.4GHz Westmere can verify 71,000 signatures per second". These are 2011 numbers; modern CPUs are faster.
- [SAY, RFC 4082 TESLA]
  - Abstract: TESLA "allows all receivers to check the integrity and authenticate the source of each packet in multicast or broadcast data streams … can tolerate any level of loss without retransmissions, and requires no per-receiver state at the sender".
  - §2: it "requires … delayed disclosure of keys … In practice, the delay is on the order of one RTT"; receivers must be "loosely time-synchronized"; "Delayed authentication … requires buffering of packets".
  - §3.2: disclosure delay `d = ceil(2m / T_int) + 1`.
  - §2.1 and §3.8: buffering exposes receivers to bogus-packet floods.
- [DONE] The prototype already uses Ed25519 fail-closed over canonical JSON, with issuer/key policy, a 60 s max TTL, 5 s skew, persistent replay claims and tombstones (prototype `README.md`, `canticle_receptor/receptor.py`).

### 7.2 Trade-offs

| Scheme | Bytes per frame | Source auth | Loss tolerance | Latency | Ops cost | Fit |
|---|---|---|---|---|---|---|
| **Ed25519 per frame** | 64 sig + 8 key-id ≈ 72 (6% of 1200) | Yes (per station, non-repudiable) | Perfect: each frame is independent | None | Key distribution by public key only (DNS TXT, manifest) | **Best default** |
| HMAC with group key | 16–32 | **No.** Any member can forge any station | Perfect | None | Shared-secret distribution and rotation. One leak compromises everyone | LAN "frond membership" pre-filter only |
| TESLA (RFC 4082) | about 16 MAC + 4 interval + 16 disclosed key ≈ 36 | Yes (after delay) | High (key chain recovers lost disclosures) | Must buffer ≥ d intervals (≈ 1 RTT to seconds via relays) | Time sync, key-chain bootstrap (needs a signature anyway), receiver buffering and DoS exposure | Only if verify CPU becomes the bottleneck (e.g., MCUs or huge fan-in) |

### 7.3 Recommendation for Q6

- **R6.1 (HIGH).** **Ed25519 per frame is the base**, not a v0.3 overlay:
  - Sign the canonical frame bytes; beacons included.
  - Carry an 8-byte key-id (a hash of the public key), not the full 32-byte key.
  - Sign once per item. Loop re-broadcasts resend the identical signed bytes; the loop does not re-sign.
  - Receivers dedup by `(station, stream, seq)` within the TTL window. Replay protection uses `ts + ttl_ms` with skew tolerance and a seq window.
  - **Relays forward signed bytes untouched**, so relays are trusted for availability only, never for authenticity. This settles scope-3's "relay verifies … and re-signs … (or simply forwards)" (`scope-framing…:94-95`) in favour of *forward, don't re-sign*. The relay adds its own envelope signature only if it needs to attest routing.

  Rationale: the owner's threat-response use case has thousands of agents with remote context enrichment. "Trust-of-LAN" collapses as soon as there is a relay or Wi-Fi, and the prototype already proves Ed25519 fail-closed works.
- **R6.2 (MED).** Optional HMAC group tag (16 B) as a cheap **pre-filter at the membrane**. It lets the relay drop non-fleet junk before Ed25519 verification under flood. It is never the authority for "who said this".
- **R6.3 (LOW).** Revisit TESLA only if verification cost dominates, for example very high-rate streams on constrained listeners. If adopted, bootstrap its key-chain commitment with Ed25519.
- **R6.4 (MED).** The owner's "trusted clients could directly enrich remote context" is the dangerous capability. Authorization should use per-station keys plus a listener-side allowlist; the receptor policy is `issuer`/`key_id` as in the prototype. Posture changes (`posture: defense` → "signed frames only", `protocol-spec-v0.1.md:497-500`) should switch receivers to rejecting unsigned frames. Better still, make rejecting unsigned frames the default outside `127.0.0.1`.

---

## 8. Consolidated architecture (my recommendation)

```
[session / sub-agent] --unix/loopback--> [per-host canticle daemon]  (one per host; local fan-out to N sessions)
        |                                   |  \
        | put TTL item (signed)             |   `-- LAN binding: 239.255.x.y:port, TTL=1 (optional, doctor-tested)
        v                                   |
[station = daemon role: ring + loop scheduler + 1 Hz beacon]
        |  unicast (signed frames)  or  LAN multicast
        v
[canticle relay = MEMBRANE (Go/Rust)]
   - ingress: Ed25519 verify + station allowlist + TTL cap + per-station byte budget + threshold/"amplify?" criteria + dedup
   - egress: cookie→lease handshake; 1:N unicast replication (sendmmsg/GSO); optional WebTransport datagrams
   - kernel: nftables per-source meters on lease port; tc egress cap
   - can chain: relay -> relay (subscribe-once-fan-out-many)
        |
        +--> internet listeners (hosts behind NAT; RENEW every 20–25 s ± jitter = NAT keepalive)
        +--> ringserver (DataLink write) --> [HAProxy community: TLS, ACL, stick-table conn-rate, PROXYv2]
                                             --> SeedLink/WebSocket replay --> ews-concept-new / nerv-ui dashboards
DNS: DNS-SD PTR/SRV/TXT (mDNS on LAN; DNSSEC'd unicast zone + SRP/SIG(0) registration on WAN); beacon = liveness
```

Byte budget per frame (≤ 1100–1200 B):

| Part | Bytes |
|---|---|
| Header: v, station ULID, stream u32, seq, ts, ttl, kind | ≈ 45 |
| Ed25519 signature | 64 |
| Key-id | 8 |
| Optional HMAC pre-filter tag | 16 |
| **Payload** | **≈ 950–1050** |

---

## 9. Contradictions and open risks

1. **Issue #30 vs reality (HIGH).** Community HAProxy has had no UDP load balancing in any 3.x release through 3.5-dev7, and no Lua/SPOE UDP. The #30 Phase-3 plan ("HAProxy 3.2+ membrane") cannot be built as written.
2. **"No subscription" vs internet listeners (HIGH).** NAT forces listener-initiated, periodically refreshed leases. This is compatible with the non-goals only if the lease lives in the relay, not the station. `WHO <station>` (#30) conflicts with `explicit-non-goals.md:86`.
3. **Trust model is split three ways (HIGH):**
   - HMAC frond key (v0.1 §9.4, scope-2 table);
   - trust-of-LAN with Ed25519 deferred to v0.3 (v0.2 `:124-126`);
   - Ed25519 fail-closed (prototype code on main).

   The prototype is the only one implemented. Recommend normatively adopting it (R6.1).
4. **Frame size (HIGH).** Spec 1472 (and "including headers", which is wrong) vs prototype 1200. 1472 breaks on IPv6, Tailscale, Nebula and WireGuard paths.
5. **Multicast address (HIGH).** `239.13.13.13` sits in RFC 2365's reserved expansion range.
6. **`.local` SRV zone (HIGH).** Incompatible with unicast DNS and DNSSEC; TXT not linked to SRV.
7. **Wi-Fi and cloud reality (MED-HIGH).** The owner's "unclear whether LAN multicast is practical" is answered as: practical on wired L2, degraded on Wi-Fi, absent in cloud VPCs and L3 overlays except ZeroTier (with `multicastLimit` ≥ fleet size).
8. **ZeroTier `multicastLimit` = 32 (HIGH).** A fleet above 32 nodes would silently get random-subset delivery.
9. **Amplification (HIGH).** Any relay that answers `LISTEN` with a stream without a cookie round-trip is a reflector. About 25% of ASes still allow spoofing.
10. **Unverified (MED/LOW):**
    - HAProxy Enterprise `udp-lb` stick-table and rate-limit support;
    - OVN-Kubernetes multicast annotation;
    - WebTransport Safari 26.4 date (secondary source);
    - nginx `limit_conn` semantics for UDP sessions;
    - IANA status of port 9999 and service name `_canticle` (not checked).
11. **Aside, outside transport scope (LOW).** The ews error "Not enought bytes for header, need 47, found 6" suggests a non-miniSEED payload, or a SeedLink control or short frame, reached the miniSEED parser. If canticle frames are ever pushed through ringserver and SeedLink to those dashboards, they must be wrapped in a format the dashboard parser expects, or be filtered by stream-ID pattern. Other readers cover the dashboards.

## 10. Source index (URLs)

**RFCs** (text via tex2e/rfc-translater @55f03a2; canonical at rfc-editor):
- https://www.rfc-editor.org/rfc/rfc2236 (IGMPv2 §8.4 GMI)
- https://www.rfc-editor.org/rfc/rfc2365 (admin scope)
- https://www.rfc-editor.org/rfc/rfc2782 (SRV)
- https://www.rfc-editor.org/rfc/rfc2827 (BCP 38)
- https://www.rfc-editor.org/rfc/rfc4082 (TESLA)
- https://www.rfc-editor.org/rfc/rfc4291 (IPv6 scopes)
- https://www.rfc-editor.org/rfc/rfc4541 (IGMP snooping)
- https://www.rfc-editor.org/rfc/rfc4787 (NAT UDP)
- https://www.rfc-editor.org/rfc/rfc5771 (multicast blocks)
- https://www.rfc-editor.org/rfc/rfc6335 (service names)
- https://www.rfc-editor.org/rfc/rfc6762 (mDNS)
- https://www.rfc-editor.org/rfc/rfc6763 (DNS-SD)
- https://www.rfc-editor.org/rfc/rfc7346 (realm-local)
- https://www.rfc-editor.org/rfc/rfc7450 (AMT)
- https://www.rfc-editor.org/rfc/rfc8032 (EdDSA)
- https://www.rfc-editor.org/rfc/rfc8085 (UDP guidelines)
- https://www.rfc-editor.org/rfc/rfc8375 (home.arpa)
- https://www.rfc-editor.org/rfc/rfc8766 (discovery proxy)
- https://www.rfc-editor.org/rfc/rfc8815 (ASM deprecation)
- https://www.rfc-editor.org/rfc/rfc9000 (QUIC)
- https://www.rfc-editor.org/rfc/rfc9119 (multicast over Wi-Fi)
- https://www.rfc-editor.org/rfc/rfc9147 (DTLS 1.3)
- https://www.rfc-editor.org/rfc/rfc9221 (QUIC datagrams)
- https://www.rfc-editor.org/rfc/rfc9665 (SRP)

**HAProxy:**
- `haproxy/haproxy` `doc/configuration.txt` @9e7c5d2 and tags v3.0.0, v3.2.0, v3.3.0
- https://www.haproxy.com/blog/announcing-haproxy-2-3
- https://www.haproxy.com/solutions/udp-load-balancing
- https://www.haproxy.com/documentation/haproxy-enterprise/enterprise-modules/udp-load-balancing/reference/
- https://github.com/haproxy/haproxy/issues/1963

**nginx:**
- `nginx/nginx.org` @0588134 (stream docs)
- https://trac.nginx.org/nginx/ticket/2496

**Envoy:**
- `envoyproxy/envoy` @bf3d00b `udp_proxy.rst`
- https://www.envoyproxy.io/docs/envoy/latest/configuration/listeners/udp_filters/udp_proxy

**Nebula:** `slackhq/nebula` @7cfa47d (`inside.go`, `examples/config.yml`).

**ringserver:** `EarthScope/ringserver` @4f034c8.

**Linux:** `torvalds/linux` @fd179f8 `Documentation/networking/nf_conntrack-sysctl.rst:194-200`.

**Cloud:**
- https://docs.aws.amazon.com/vpc/latest/tgw/tgw-multicast-overview.html
- https://cloud.google.com/vpc/docs/vpc
- https://docs.cloud.google.com/vpc/docs/multicast/overview
- https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-faq

**Overlays:**
- https://docs.zerotier.com/protocol/
- https://github.com/zerotier/ZeroTierOne/issues/1024
- https://tailscale.com/docs/concepts/tailscale-osi
- https://github.com/tailscale/tailscale/issues/11134
- https://docs.cilium.io/en/stable/network/multicast/

**Wi-Fi:** https://github.com/openwrt/openwrt/issues/23140

**Abuse:**
- https://www.cisa.gov/news-events/alerts/2014/01/17/udp-based-amplification-attacks
- https://spoofer.caida.org/summary.php

**Browser/QUIC:**
- https://developer.mozilla.org/en-US/docs/Web/API/WebTransport/datagrams
- https://webrtc.ventures/2026/04/webtransport-is-now-baseline-what-it-means-for-real-time-media/
- https://datatracker.ietf.org/doc/draft-ietf-moq-transport/
- https://datatracker.ietf.org/doc/html/draft-jholland-quic-multicast-06 (SSM-only QUIC multicast channels; prior art only)

**Crypto:**
- https://ed25519.cr.yp.to/
- https://ed25519.cr.yp.to/ed25519-20110705.pdf

**Misc:**
- https://github.com/HamSCI/igmp-querier
- https://www.wireguard.com/quickstart/
- https://wiki.nftables.org/wiki-nftables/index.php/Meters
- https://labs.iximiuz.com/tutorials/ebpf-ratelimiting-dbc12915
