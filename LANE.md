# bc#198 — digester fixture lane

Owner: Emeric (implementation). Rune owns RFC-0003 case 1a vii–viii and reviews the terminal-slot boundary.

## Pins

- Repository base: `88d486cc4bee66ade864de86b06e433304d13be2`
- RFC-0003 review head: `4e9dfaf2755b5babf8d13cf773aa3a4bdc2083e5`
- Scope: fixtures only. No live source reads, trigger, deployment, or activation.

## First fixture slice

The first executable RED is RFC-0003 §8 case 8 i: a valid fixture consent belonging to another actor must be
refused at admission, before the fixture source is read. The receipt is the structured refusal plus the source's
read counter, not the worker's report.

The next slices stay in the same harness:

- 8 ii–vi: source/audience/grantee/integrity/replacement checks, with per-source read counters.
- 9: revocation at the slot accept, kept separate from read-time revocation.
- 10: runner-owned artifact attestation; the worker cannot self-attest.
- 11: the RFC 8785 binding vector and changed-payload conflict.
- 12: one source entry to one consent, with per-entry scope and counters.

Rune's crash-position fixture is evidence for the terminal-slot/station seam. This lane will consume its contract;
it will not replace the existing outbox's deliberate at-most-once/unknown behavior.
