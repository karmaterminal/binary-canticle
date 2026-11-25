# Elected derived publication: control transport

This component connects the #159 effect adapter to the existing station Unix control server.
It carries an already issued, host-owned capability and exact elected bytes. It neither creates
an exposure receipt nor makes an election for a prince. The station wire format is unchanged.

## Trusted host attachment

The owning host constructs its `ReplyProposal` from its private database, the issuer's public key
(and, on the issuer side only, its private key), issuer name and reviewed grant. The station side is
constructed without the private key, so it can verify and admit a capsule but never mint one (#162 F3). `content_policy.derived_text_allowed` supplies a real UTF-8,
credential and high-entropy check; it ports the existing OpenClaw sender policy. The host must also
establish source-use permission, sensitivity/audience policy and that the payload is an elected
summary rather than private reasoning. Those decisions do not come from the payload.

The host supplies `DerivedControlBridge(DerivedStationProposal(..., enabled=True))` through
`run_station(..., derived_bridge=bridge)` for the exact same Station object, whose derived admission
flag must also be enabled. A mismatched station or disabled flag refuses. Omitting the bridge keeps
ordinary startup unchanged. There is no new agent tool or automatic CLI enablement.

Only these internal control messages are accepted:

| Operation | Exact fields | Result |
|---|---|---|
| `derived_publish` | `op`, `capsule_b64`, `text` | The existing immutable station-acceptance receipt. |
| `derived_query` | `op`, `election_id` | The existing claim state and known acceptance, with no send or retry. |

`capsule_b64` is strict base64 of the existing version-2 authenticated host capsule. `text` must be
its exact UTF-8 elected payload, at most 800 bytes before the grant's narrower bounds. The transport
does not accept lineage, audience, signer, stream, database path or policy fields. The capsule and
the issuer's private key stay outside model-visible tool input and output.

Both operations require the actual Unix peer UID to match the station process UID. Missing kernel
peer identity refuses. The existing 0600 control socket and request-size ceiling remain in effect.
The publication operation also respects the control socket's chatter class restriction. The
existing effect adapter independently verifies the issuer's Ed25519 signature, complete ledger, exact generations,
election, full signer, current authority, budgets and deadlines before the one-use Station effect.
The bridge scans outgoing text again even if a producer's callback was incorrectly permissive.
Refusals name a finding kind and never include the matched credential.

The station event loop performs the dispatch synchronously with its ordinary mutations and polling.
Lost control replies are not replayed. The host queries the same election; it must not create a new
election to retry an uncertain effect. Query does not assert that a known acceptance is still on air.

## Scope of the proof

`tests/test_derived_control.py` exercises actual Unix control requests, real Station signing,
loopback UDP and signature-verifying Listener reception. It also checks a lost control reply,
query-only recovery, refusal of replay, default-off operation, peer identity, exact request shape,
station/class narrowing, altered elected bytes and the non-bypassable secret scan. The origin and
host exposure in this transport suite are explicitly synthetic; no actual prince encounter is
claimed. Socket tests are required and do not convert an environment refusal into a passing proof.

```sh
PYTHONPATH=prototype/canticle-station python -m unittest discover \
  -s prototype/canticle-station/tests -p 'test_derived_control.py' -v
```

The existing candidate retains its isolated-subagent Reader shape and its unadopted all-history-
fresh/all-chatter policy. This component changes neither. The actual OpenClaw/frond-ear exposure
producer, continuing-session custody, inherited exposure and permitted room egress remain separate
host integration. A configured socket alone is not a released continuing-session route.
