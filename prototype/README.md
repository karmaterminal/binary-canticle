# Prototypes

Runnable, bounded experiments that test a Binary Canticle design seam without
claiming protocol or production status.

- [`ringserver-udp-cue/`](./ringserver-udp-cue/) — localhost-only signed UDP
  cue receptor with a private downstream DataLink publisher seam. Tracked by
  [#49](https://github.com/karmaterminal/binary-canticle/issues/49).
- [`ringserver-proofs/`](./ringserver-proofs/) — runnable proofs against a
  real EarthScope ringserver 4.5.4: signed cue → DataLink round trip,
  miniSEED3 text over SeedLink v4, the TTL-window catch-up query, DataLink over
  WebSocket, and a reproduction of the ews-concept-new `need 47, found 6`
  parser error. Evidence for RFC-0001 §18; closes the proof gap in
  [#49](https://github.com/karmaterminal/binary-canticle/issues/49).
- [`canticle-station/`](./canticle-station/) is a spike of RFC-0001 S1/S2. It
  has a frame v2 codec with candidate conformance vectors, a looping station
  (carousel, regulator, pluck, supersede, carrier-beacon) and a listener
  (dedup, sticky-pluck, presence), plus a `canticle` CLI over UDP unicast or
  multicast.
- [`openclaw-canticle/`](./openclaw-canticle/) is a spike of the OpenClaw
  prince plugin ([#97](https://github.com/karmaterminal/binary-canticle/issues/97)):
  an explicit-read heard journal and current view over the host daemon's
  receptor record v1, and an outbound aging table over the prince's own
  station. No seat runs it.
