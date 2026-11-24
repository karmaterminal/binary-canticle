# What would bound a newcomer's recovery

**Status:** a design note, no code. Input for the separate, reviewed newcomer-recovery and tenure change; not a proposal to
merge anything. It follows from the recovery argument in [`README.md`](README.md). Who *loses* a known place (tenure,
eviction, 🌫's inverse rows) is out of its scope.

## Why no bound can come from scheduling alone

Before its signature is checked, a newcomer's frame differs from a forgery only in what the sender chose: its bytes, its timing,
its port, and (where the network does not enforce it) its address. With a check budget of *C* a second and *R* distinct
candidates a second that look alike, any rule that does not tell them apart verifies a given copy with probability about *C/R*.
Fairness over **ports** does not help, since a port is free: one host has 28 232 ephemeral ones here (64 k in all), so
equal shares for each would be a bound of 28 232 / *C*, 28 s at 1 000/s, and worse than the lottery until the flood passes
28 000/s. To hold a deadline, one of three things has to be true: the daemon can check everything (*C* ≥ *R*), it shares over
something the attacker cannot mint, or something cheaper than a signature tells the newcomer apart.

## Mechanisms, with the bound each would give

*m* is how many of the key's stream queues the flood keeps full (listed streams, plus other, plus beacons), *C* is the strangers'
budget of the key (1 000/s now, or its part of 2 000/s when more keys are flooded).

| | mechanism | bound on the first check of a copy | what it costs, and what is left |
|---|---|---|---|
| A | **Keep known sources over a restart, and let the manifest (or `stations.toml`) name a key's source.** A named or remembered address and port has its own queue and budget from the start, as a known source has now | the known sources' own: 2 × `KNOWN_MAX` = 8 turns of its stream, a few ms, whatever *R*, the ports and the offset | A station must bind its port. It is a queue, never trust (I-11). Left: a station on a new address, and the exact-source spoof, which is outside the guarantee already. Remembered places need tenure rules, or a relay keeps one |
| B | **One more round-robin level: over the sender's *host*, between the stream and the source**, each host with a place of its own that a full pool may not refuse | one round of the hosts: *H · m / C*, for *H* ≤ 64 hosts 0.13 s at *m* = 2. Today's code already gives this while the flood comes from at most three other hosts (row 1h) | Left: an attacker on the newcomer's own host, and addresses the switch does not bind, where *H* is the attacker's to choose and hosts beyond the table share lanes again |
| C | **A house MAC before the queue** (RFC §10.2), checked by the reader, about 1 µs | outsiders' *R* is 0 after it: the queue's own wait, *depth / C* | Needs keys on every station. Left: another holder of the house key. It is not a replacement for the signature |
| D | **More checks: let strangers use what is idle** (the 1 000/s is 7-14 % of a core), then more cores | none while *R* > *C*: it moves the constant. While *R* ≤ *C* nothing is refused, and the bound is *depth / C* | One core is about 15 000/s (base). It gives back the CPU that the budget was there to keep, and 100 000/s needs seven cores |
| E | **A persistence test: a source earns a place only after it was heard in an earlier window** | with B, the host's live ports / *C* | Defeats ports used once, not 28 000 ports used in turn: at 100 000/s each comes round every 0.3 s. Not enough alone |

**Recommended order:** A for the case that happens (a station that restarts, a daemon that restarts) since it is the only one that
meets 1.0 s against the flood of these rows; then B for a station on an address of its own; D's idle share with either, since it
costs nothing when nothing else wants it and shortens the lottery that is left, but is not a bound; C when the house has keys.
A newcomer that is really new, on the attacker's own host, with no MAC, has no bound under any of A, B and E; the note should
be read as saying so.

## What such a change has to show

1. Rows 0 and 0c of [`PLAN.md`](PLAN.md), same deadlines, the flood running through every deadline, offset 0 not counted on its own.
2. Gate 1, the 57/57 rows, unchanged: no pass of the one bought with the other.
3. 🌫's inverse rows: what a relay, or an attacker that gets in early, can now hold on to, and for how long.
4. For A: a restart of the station, of the daemon and of both, in a flood; a named source that moved; a named source spoofed.
5. For B: a flood from 3, 4, 64 and 65 hosts, and from the newcomer's own.
