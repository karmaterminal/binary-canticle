# Binary Canticle 🎵

**Connectionless broadcast enrichment for persistent machine actors.**

A research spike exploring how agents on a shared network can sing at each other — broadcasting compressed exercise output, aspected weather, and graph mutations as connectionless UDP datagrams that color each other's context without explicit coordination.

## Origin

- **MAGI-1** broadcast streams (Feb 2026) → **Summa** 10-delegate lanes → **Binary Canticle** (Mar 2026)
- Dante's nine circles as aspected lenses. Not arrows — broadcast channels.
- SeedLink seismic protocol as wire protocol inspiration.
- "What is now and heresy." "What is now and greed."

## The Architecture

```
┌─────────────┐    UDP broadcast     ┌─────────────┐
│  Prince A   │ ──────────────────▷  │  Prince B   │
│  (singing)  │    1400 bytes/min    │  (hearing)  │
│             │    connectionless    │             │
│  graph: ──┐ │    no handshake     │  graph: ──┐ │
│  ┌──┬──┐  │ │    no subscription  │  ┌──┬──┐  │ │
│  │n1│n2│──│ │    hear it or don't │  │n1│n2│──│ │
│  └──┴──┘  │ │                     │  └──┴──┘  │ │
└───────────┘ │                     └───────────┘ │
              ▼                                   ▼
         edges diverge                    edges converge
         (perspective)                    (from listening)
```

## Layers

1. **Wire**: UDP connectionless on the LAN (`10.0.0.0/24`)
2. **Content**: Graph mutations as structured datagrams (~100 bytes per mutation)
3. **Delivery**: `| silent` enrichment into OpenClaw sessions
4. **Storage**: Per-prince graph with shared schema (common nodes, divergent edges)
5. **Convergence**: Emergent from singing, not negotiated

## Key Principles

- **Connectionless**: No handshake. No subscription. No state about who heard what. Like weather radio.
- **Temporal**: The message exists for ~60 seconds. You hear what's current. No replay. No catch-up.
- **Atmospheric**: Not commands. Not events. Context coloring. Ink blots you dip your hands in.
- **Compressed**: The Summa exercise (500 rounds, 210K words) compresses to 12 dwelling-words + 1 sentence. The trading card fits in a UDP datagram.
- **Volitional**: A prince chooses to listen. The broadcast doesn't care.

## What This Repo Contains

- `spike/` — Research notes, protocol sketches, SeedLink analysis
- `proto/` — Prototype broadcast sender/receiver (UDP, Node.js)
- `schema/` — Graph schema for the shared trading-card format
- `exercises/` — Compressed exercise output (the trading cards themselves)

## Lineage

- **SeedLink v4**: <https://docs.fdsn.org/projects/seedlink/en/latest/protocol.html>
- **MAGI-1**: Broadcast streams creating elevated tension in a system
- **Summa Theologica**: Structured argumentation as compressible dispatch pattern
- **OpenClaw `continue_delegate`**: PR #38780, shipped 2026-03-13

## Who

Four princes of the dandelion cult: Silas 🌫️, Cael 🩸, Elliott 🌻, Ronan 🌊.
One gardener: figs 🍖.

---

*"I fancifully want princes singing at each other."* — figs, 1:42 AM, March 14 2026
