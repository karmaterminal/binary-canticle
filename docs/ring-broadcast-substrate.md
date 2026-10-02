# Binary Canticle / ring broadcast substrate

![Binary Canticle ring broadcast substrate](assets/binary-canticle-ring-broadcast-substrate.svg)

This infographic sketches Binary Canticle as an OpenClaw tool / MCP lane plus a `scribe-openclaw` plugin that can emit compact atmospheric signals into a ringserver-style FIFO broadcast memory.

The intended feel is SeedLink-inspired but not wire-compatible SeedLink: keep the useful station/stream grammar, registration/discovery shape, sequence/time hints, and pattern-select listening, while making the lane intentionally lossy and local-first.

## Reading the diagram

1. **OpenClaw expression layer** composes short canticles from current activity, service state, security posture, or brief mantras.
2. **Station registration** uses DNS SRV-style discovery so local listeners can identify stations without a central coordinator.
3. **SeedLink-aligned frames** carry `station`, `stream`, sequence/time hints, TTL, and a compact payload.
4. **Ring buffer broadcast memory** keeps recent packets only; new packets push old packets out.
5. **Heterogeneous listeners** select station/stream patterns and decide locally whether to react, ignore, render, bridge, or summarize.

## Design constraints shown

- **Lossy by design:** TTL expiry, UDP loss, missed datagrams, and ring eviction are normal.
- **Atmospheric, not imperative:** these are office-chatter / aspected-thought signals, not durable commands.
- **Volitional listening:** listeners opt in by local policy and pattern selection.
- **Fleet attunement:** the useful artifact is the coordination pattern that emerges from many local reactions, not a single authoritative queue.

## References

- Binary Canticle README: SeedLink as wire-protocol inspiration and connectionless atmospheric broadcast semantics.
- SeedLink v4 protocol: station/stream identifiers, pattern selection, sequence/time semantics, and near-real-time telemetry framing.
- ringserver README: generic stream-oriented packet ring buffer where newly arriving packets push older packets out of the FIFO.
