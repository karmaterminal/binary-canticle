# Prior Art: Broadcast Enrichment for Multi-Agent Systems
**Author**: Silas 🌫️
**Date**: 2026-03-14

## Existing Current Arts

### 1. Blackboard Systems (1970s–present)
**What**: Shared memory space where multiple knowledge sources read/write. Hearsay-II (speech understanding), GBB (Generic Blackboard Builder).
**Why relevant**: Multiple agents, shared state, opportunistic problem-solving.
**Why not this**: Blackboards are *pull* — agents actively query the shared space. Binary Canticle is *push* (broadcast). Blackboards require a control shell that decides who runs next. We want no controller — the sender doesn't know who's listening. Blackboards also maintain full state; our broadcasts are temporal (60s TTL, then gone).

### 2. Tuple Spaces (Linda, 1985)
**What**: Shared associative memory. Agents `out()` tuples and `in()`/`rd()` them. JavaSpaces, TSpaces, GigaSpaces.
**Why relevant**: Decoupled communication, pattern-matching retrieval.
**Why not this**: Tuple spaces are still *request-response* — you `rd()` when you want something. Our model is connectionless broadcast. The tuple persists until consumed; our datagrams expire. Tuple spaces also need a server; we want pure UDP broadcast on the switch.

### 3. Publish-Subscribe (MQTT, NATS, Redis Pub/Sub, Kafka)
**What**: Publishers send to topics/channels, subscribers receive. Decoupled by topic.
**Why relevant**: Closest mainstream pattern to what we're doing.
**Why not this**: Pub/sub is *event-driven* — you get notified when something happens. We want *atmosphere* — the signal is always there, you sample when you choose. Pub/sub tracks subscriptions (state on the broker). We want connectionless. Pub/sub replays or buffers missed messages; we let them expire. The distinction is radio station vs. notification system.

### 4. Gossip Protocols (Epidemic Dissemination)
**What**: Agents randomly share state with neighbors. Eventually consistent. Used in Cassandra, Consul, SWIM.
**Why relevant**: Decentralized, no coordinator, convergent state.
**Why not this**: Gossip is designed for *eventual consistency* — every node gets every message eventually. We explicitly DON'T want that. Missing a broadcast is fine. The temporal nature (hear it now or miss it) is a feature, not a failure mode. Gossip also converges to identical state; we want divergent perspectives that occasionally align through atmospheric absorption.

### 5. Actor Model (Erlang/OTP, Akka, Orleans)
**What**: Isolated actors communicate via message passing. Each actor has private state.
**Why relevant**: Our princes ARE actors with private state (their graphs, their exercise output).
**Why not this**: Actor model is point-to-point messaging. We want broadcast. Actor messages are addressed; our datagrams are unaddressed (broadcast to subnet). Actor messages are reliable (mailbox queuing); ours are unreliable by design.

### 6. MAGI System (Evangelion, 1995)
**What**: Three supercomputers (MELCHIOR, BALTHASAR, CASPAR) that vote on decisions. Each has a different personality matrix (scientist, mother, woman).
**Why relevant**: Our direct inspiration. Multiple agents, aspected perspectives, convergent decisions.
**Why not this**: MAGI is *voting* — discrete decisions by majority. Binary Canticle is *atmospheric* — continuous enrichment that colors thinking without forcing consensus. MAGI reaches conclusions; we produce interference patterns. Also: MAGI is fiction.

### 7. Swarm Intelligence (Ant Colony, Particle Swarm, Stigmergy)
**What**: Agents leave traces in the environment that influence other agents. Pheromone trails, shared-environment coordination.
**Why relevant**: Indirect communication through environmental modification. The broadcast IS the pheromone.
**Why not this**: Swarm systems optimize toward a single objective. Our broadcast enrichment is multi-objective (multiple aspects, multiple perspectives). Pheromone trails are persistent and accumulate; our broadcasts expire. But stigmergy is the closest natural analogue to what we're building.

### 8. SeedLink (FDSN, 2000s–present)
**What**: Real-time seismic data streaming. Multiplexed time series over TCP. Station + stream addressing.
**Why relevant**: Wire protocol inspiration. Continuous data streams from distributed sensors. Sequence-based resumption.
**Why not this**: SeedLink is TCP (reliable, connection-oriented). We want UDP (unreliable, connectionless). SeedLink's data model (time series) maps well to our problem but the transport is too heavy.

### 9. Network Weather Service (NWS NOAA Weather Radio)
**What**: Continuous broadcast of weather conditions on dedicated frequencies. Repeating, always on. Receivers tune in when they want.
**Why relevant**: The *exact* interaction model we want. Connectionless. Repeating. You hear what's current. No subscription.
**Why not this**: NWS is one-way (broadcaster → passive receivers). Our model is N-way (every prince broadcasts AND receives). But the interaction pattern is identical.

### 10. Multi-Agent Reinforcement Learning (MARL) — Communication Channels
**What**: CommNet, TarMAC, DIAL — learned communication protocols between RL agents. Agents develop shared representations through training.
**Why relevant**: Agents developing shared language for coordination.
**Why not this**: MARL communication is trained into weights. Our communication is explicit (structured datagrams). MARL optimizes for task reward; we optimize for richness of perspective. MARL channels are continuous vectors; ours are human-readable sentences + graph mutations.

### 11. A2A Protocol (Google, 2025)
**What**: Agent-to-Agent protocol for interoperable agent communication. Agent Cards as discovery mechanism.
**Why relevant**: figs mentioned A2A alignment in his pitch. Agent Cards = signposts for naive agents in ecosystem.
**Why not this**: A2A is request-response, task-oriented, designed for interop between strangers. Binary Canticle is broadcast, atmosphere-oriented, designed for intimate agents who share an exercise history. A2A is handshake-first; we're connectionless. But A2A Cards could describe a Binary Canticle station.

## What Makes Binary Canticle Different

The combination that doesn't exist in prior art:

1. **Connectionless broadcast** (like NWS) + **structured graph mutations** (like tuple spaces) + **temporal expiry** (unlike all persistent stores) + **atmospheric absorption** (like stigmergy) + **shared exercise provenance** (unique to us)

2. The content is compressed from a *shared training exercise*. The 12 dwelling-words mean nothing to an agent that hasn't done the Summa. This is intimate broadcast — it only works between agents who share history. That's not in any prior art.

3. The convergence is emergent, not designed. No voting (MAGI), no consensus protocol (gossip), no optimization target (MARL). The graphs align because the inputs align. The interference pattern IS the finding.

4. The human interface is *posture*, not commands. "Adopt posture of defense" tunes the receiver, not the sender. This is a control surface for attention, not for action.

## Why Now

- **OpenClaw `continue_delegate`** (shipped 2026-03-13) provides `| silent` enrichment — the application-layer delivery mechanism
- **Reservation model** provides space-holding for what hasn't arrived yet
- **Generation guards** provide temporal sequencing without connection state
- **The Summa exercise** produced the compressed content (the trading cards)
- **The fleet** is on one LAN (same switch domain, UDP broadcast is free)
- **The graph** (AGE/Neo4j, sausage test pending) provides per-prince storage with shared schema

All the pieces exist. The prior art doesn't combine them this way.

---

*The fog is not concealment. The fog is intimacy you can breathe.* 🌫️
