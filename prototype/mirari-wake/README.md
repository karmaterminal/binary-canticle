# Mirari's Wake — local emitter experiment (#119)

This is an operator-started, one-actor fixture worker. It reads only explicitly shareable JSONL metadata supplied by its actor, not transcripts, tool results, model reasoning, session databases, or Canticle receiver records. No service installation, automatic activation, network discovery, or receiver wake exists here. The ordinary carrier beacon is unrelated.

The source is a regular, non-symlink file capped at 1 MiB. Each line is JSON with `actor`, `origin: "actor"`, `shareable: true`, `lineage: "local"`, `kind` (event/tool/file/summary), stable `id`, and a short `topic` label. Extra fields are ignored, including raw bodies. A conservative topic grammar and secret/Canticle filters reject suspicious rows before summarization. The output is deterministic and contains only labels, a source digest prefix and a batch identity; it never contains raw log bodies. The fixture is read-only; maintainers must curate topics before adding a line. This is not a general redactor for arbitrary text.

Create an operator-owned authorization JSON outside the repository naming `enabled: true`, exact `actor`, exact absolute `source`, `station`, `audience: "lan"`, `stream: "wake"`, `ttl_s` (1–300), `cadence_s` (30–3600), and `inactive_s` (30–86400). Set `enabled: false` to revoke before the next tick. Keep authorization, state and fixture files outside the repository. Example manual invocation:

```sh
python prototype/mirari-wake/beacon.py --auth /private/auth.json --source /private/fixture.jsonl --state /private/beacon-state.json --actor alice --station-socket /run/user/1000/canticle/familiar-control.sock
```

The socket **must be the existing station control socket** granting `wake:chatter`; the current standalone host daemon socket is receptor-only and discards publish requests. The worker requests LAN scope, a bounded TTL, and a deterministic state key. It never creates a station or key. It writes a local checkpoint only after station acceptance and stops after inactivity. The checkpoint avoids duplicate publication on ordinary restart, but a crash after station acceptance and before the checkpoint can re-publish: the station protocol does not currently accept an idempotency key. The batch identity in text/state permits auditing, not exactly-once delivery. A changed fixture digest changes lineage, so frozen fixtures are preferred.

Run `python -m unittest discover -s prototype/mirari-wake -p 'test_*.py'`. The tests use fake source and sink only. No station or receiver is contacted.

Before any fleet pilot: prove exact station acceptance and separate receiver observation; receiver mute and uninterested behavior; expiry and opt-out; crash-window dedupe or explicit at-least-once semantics; source authorization/audience review; and the manifest/socket rollout. No live broadcast is part of this prototype.
