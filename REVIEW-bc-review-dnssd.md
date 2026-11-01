# Read-only review: binary-canticle #123 and #125

| PR | Head | Verdict | Reason |
|---|---|---|---|
| #123 Add bounded read-only DNS-SD locator browse | `fc383d0215f9e7ac1d8c2f684254f7d132515ce2` | REQUEST_CHANGES | The browse surface has a concrete fail-closed gap: duplicate TXT keys are silently guessed by first-value wins, and the DNS name parser accepts syntactically invalid labels. |
| #125 Add station-owned DNS registration planner | `b93918262c9ed7141e08c4fe3f6c3fc9f3c1476d` | REQUEST_CHANGES | The planner can shorten a lease when provider calls take time, and its zone-name/target validation is not fully valid or in-zone. |

## Named refs

| Category | Ref | Full SHA | Local/tracking/server |
|---|---|---|---|
| Product/base for #123 | `feat/public-catalog-prereq` | `ce7c05d45faa2b26d55c9a1f7009cca47b1e98fc` | fetched remote; head review is `fc383d0215f9e7ac1d8c2f684254f7d132515ce2` |
| Product/head for #123 | `feat/dns-sd-browse-rune-20261030` | `fc383d0215f9e7ac1d8c2f684254f7d132515ce2` | local head; fetched remote |
| Product/base for #125 | `feat/dns-sd-browse-rune-20261030` | `fc383d0215f9e7ac1d8c2f684254f7d132515ce2` | #125 base equals #123 reviewed head |
| Product/head for #125 | `feat/dns-sd-registration-rune-20261030` | `b93918262c9ed7141e08c4fe3f6c3fc9f3c1476d` | fetched remote |
| Lane/safe branch | `codeagent/bc-review-dnssd` | `fc383d0215f9e7ac1d8c2f684254f7d132515ce2` | local == tracking == server before review publication |
| CI/workflow | N/A | N/A | focused touched-module tests only |
| Presentation | N/A | N/A | N/A |
| Docs/proof | N/A | N/A | N/A |

## PR #123 findings

### [MEDIUM] Duplicate TXT keys are silently resolved by first-value wins

**Location:** `prototype/canticle-station/canticle/dns_browse.py:121-122`

**Failure scenario:** A TXT RR contains `sid=<manifest-key>` followed by `sid=<wrong-key>` (or `k=<valid>` followed by `k=<bogus>`). The loop executes `if k not in hints`, so it keeps the first value and never reports a duplicate. A host that deliberately or accidentally changes the ordering can suppress the required mismatch alert. Unknown or duplicate input is not fail-closed, and the workorder explicitly requires duplicate input to be refused.

**Fix:** Add a duplicate-key marker when a key is seen again, report `txt-duplicate` or `txt-invalid`, and omit or invalidate the affected hint rather than selecting a winner. Add a test whose TXT answer has duplicate `sid` and `k` keys and proves the mismatch is reported and no value is guessed. The TXT record still remains a hint: RFC §13.4; mismatches must alert, never change trust.

### [MEDIUM] Domain-label validation accepts trailing hyphens

**Location:** `prototype/canticle-station/canticle/dns_browse.py:21`, `prototype/canticle-station/canticle/dns_browse.py:66`

**Failure scenario:** `Browser(..., "bad-.example.org")` passes `_NAME.fullmatch` because the regex allows a trailing `-` in a label. The malformed name is then sent toward dnspython as `_canticle._udp.bad-.example.org.`. A malformed caller input reaches the resolver boundary instead of being refused before I/O.

**Fix:** Use a label regex that requires an alphanumeric first and final character, for example `[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?`, and add a negative test for trailing-hyphen and leading/trailing-dot labels. Prefer the repository's existing DNS-name validation pattern if one is introduced.

## PR #125 findings

### [MEDIUM] Lease expiry starts before the provider call completes

**Location:** `prototype/canticle-station/canticle/dns_registration.py:158-163`, `prototype/canticle-station/canticle/dns_registration.py:169-171`

**Failure scenario:** `clock()` returns 0, `provider.publish(...)` blocks or performs a slow DNS operation until clock 100, and then returns a successful handle. The code stores `expires_at = 0 + 3600`, not `100 + 3600`, so the fake/local view declares the lease expired 100 seconds early. Renewal and withdrawal at actual times can therefore be refused or shortened. The renewal path has the same pre-call timestamp bug. The existing tests advance the clock between operations (`test_dns_registration.py:66-81`) but never advance the clock inside a provider call, so this lease-state claim is untested.

**Fix:** After `provider.publish` and `provider.renew` return successfully, read the clock once and set `_expires_at` from that post-success instant. For a provider with acknowledgement latency, test a provider that advances the clock inside `publish` and `renew`, proving the successor expiry equals the post-acknowledgement time and the old failed state remains unchanged.

### [LOW] SRV target validation rejects the zone apex

**Location:** `prototype/canticle-station/canticle/dns_registration.py:109-111`

**Failure scenario:** For `zone="example.org"` and `target="example.org"`, `_domain` normalizes both to `example.org.`, but `target.endswith(".example.org.")` is false. The planner refuses a valid in-zone SRV target at the zone apex.

**Fix:** Accept `target == zone or target.endswith("." + zone)`, and add a test publishing an apex target. Keep the existing rejection of targets outside the explicit zone.

### [MEDIUM] Zone and target labels use an incomplete DNS label grammar

**Location:** `prototype/canticle-station/canticle/dns_registration.py:14-24`

**Failure scenario:** `_domain("bad-.example")` passes `_NAME.fullmatch` and is normalized to `bad-.example.`, despite the malformed trailing hyphen. `Registration` can then construct the PTR/SRV/TXT publication and pass it to a provider. The station name at line 125 does not repair this; this helper is independently applied to both the zone and SRV target.

**Fix:** Require every DNS label to start and end with an ASCII alphanumeric character, and add negative tests for malformed zone and target names before a provider call. Ensure the helper rejects names longer than DNS label and total-name limits.

## Coverage and scope checks

- **Bounds:** #123 caps PTR/instance/record/TXT counts, TXT bytes, cache entries, TTLs, and per-query resolution lifetime. #125 caps public stream enumeration and TXT size and validates lease and port ranges. Neither PR has a real DNS transport.
- **Fail-closed:** #123's TXT duplicate bug and invalid-label bug above. #123 otherwise refuses missing public catalog scope, out-of-zone targets and revoked/ambiguous grants. #125 refuses multiple active names, absent public scope, mismatched grants, unsafe zones/targets and expired handles.
- **Session exactness:** N/A. Neither PR adds session reads or landing behavior.
- **Secrets/private content:** Neither PR broadcasts private stream names or credentials. #123 exports only manifest `public_streams`; #125 exports only public stream names and key metadata.
- **Claim-to-test coverage:** #123 tests public-only output, missing catalog, mismatches, oversized TXT, cache/TTL, instance truncation and out-of-zone SRV. It has no duplicate-TXT test or trailing-hyphen domain test. #125 tests opt-in, clock-bounded renew/withdraw, provider failure state, revocation, unsafe inputs and stale fake handles. It has no provider-call-duration expiry test or apex-target test.

## Context

This review is bounded to #123 and #125. RFC §13.1-§13.5 makes DNS-SD a locator and cross-check hint, with the manifest as trust (§13.1, §13.4). Design note #94 confirms pi-hole is a resolver/blocklist, not a DNS UPDATE or DNSSEC-signing authority, and proposes a separate authoritative zone with conditional forwarding. The PRs do not alter that topology, and both avoid real DNS mutation in #125. The issue is not reviewed for a lane scope change; this lane remains tied to #114.
