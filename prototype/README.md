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
