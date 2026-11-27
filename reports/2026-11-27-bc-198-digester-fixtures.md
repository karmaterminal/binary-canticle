# bc#198 digester fixture receipt — RFC-0003 cases 8–12

Date: 2026-11-27
Owner: Emeric (implementation); Rune owns the terminal-slot/crash contract and exact-head review.

## Pins

- Repository base: `88d486cc4bee66ade864de86b06e433304d13be2`
- RFC-0003 review head: `4e9dfaf2755b5babf8d13cf773aa3a4bdc2083e5`
- RED fixture commit: `55d642dd61dc5c99fa88693081852142b906be19`
- GREEN implementation commit: `a824d0b4da09863b6abda04d213d40cd9dd86787`

The RED commit introduced the cases before their fixture interfaces existed; the focused command refused at module
load because `FixtureConsentStore` and the rest of the cases 8–12 boundary were absent. The GREEN commit supplies
that fixture-only boundary.

## What the 12 fixtures prove

1. **8 i:** another actor's otherwise-valid consent is refused before a source read.
2. **8 ii:** another stream or consent narrower than the declared record set is refused before a read.
3. **8 iii–iv:** result audience and worker grantee are admission checks.
4. **8 v:** unverified/altered consent and an issuer without source authority are refused at admission.
5. **8 vi:** consent is fetched again for every read; replacement after record one refuses record two and fills a
   `refused_read` fixture failure.
6. **9 i:** every used consent is checked again at the slot accept; a revocation after the last read withholds the
   success and fills a `revocation` fixture failure.
7. **10 i–iii:** a success requires a verified runner attestation for this summons, binding and artifact; missing,
   mismatched and replayed attestations fill `worker_mismatch`.
8. **10 iv:** worker-authored identity fields are refused instead of becoming authority-stamped lineage.
9. **11 i–ii:** the integer-only RFC 8785 projection reproduces Vector 1's
   `sha256:88cdc08ee07bc70d0885a726addba1cd40c6abad2ed3a7835cbe17885b067fd9`; `attempt` and
   `log_destination` alone do not change it.
10. **11 iii:** same-binding retry reads duplicate; a changed admitted field is a conflict and does not inherit the
    first receipt.
11. **12 i–ii:** two source entries read only under their own consent; a crossed consent reference refuses the whole
    summons before either source is read.
12. **12 iii–iv:** an out-of-entry record is refused without a source read, and duplicate actor+stream entries are
    refused as ambiguous.

Every refusal with an admission boundary checks a source-owned read counter, not the worker's report.

## Commands and results

From `prototype/openclaw-canticle/`:

- `node --no-opt --test test/digester.test.ts` — **12/12 pass**.
- locked TypeScript 6.0.2 toolchain, `node --no-opt .../tsc -p tsconfig.json --typeRoots .../@types` — **pass**.
- `node --no-opt --test test/*.test.ts` — **149/149 pass**, zero skipped.
- `git diff --check` — **pass**.

## Deliberate limits

- In-memory fixtures only: no live OpenClaw record, session, transcript, model call, trigger, station, deployment or
  activation.
- `FixtureTerminalSlot` proves only one-process conditional first-fill/duplicate/conflict behavior. It is not durable,
  has no relay, and proves neither crash recovery nor replay.
- Rune's reopened-store cases for RFC-0003 1a vii–viii remain the crash evidence and review boundary. They are not
  attributed to this fixture lane.
- The production OpenClaw outbox is unchanged. Its deliberate `unknown`/no-replay behavior remains intact and is not
  used as evidence for the summons relay.
