# Finding a channel by what it sings: `canticle dns-find` (2026-11-27)

Lane `codeagent/bc-dns-find-predicates`, for 🍃 (the code's owner). § Registration is for 🌊 and 🪨; it asks for
nothing to be done.

**Verdict.** `canticle dns-find --where KEY=PATTERN` and `dns_browse.find(domain, predicates, manifest=…,
query=…)` answer "who sings `ops.*`?" and "where is key `21fe…`?" over the existing read-only browse, with every
browse guarantee kept. They can't answer "who sings class `alarm` on `ops.*`?". No class is published per
stream anywhere: not in TXT, not in the beacon. That needs a registration-side change (below), not code. On the
live pair, the one enrolled instance is legacy and carries none of §13.2's keys, so nothing on the live pair is
findable by predicate yet.

## Refs

| category | ref | full SHA | equality |
| --- | --- | --- | --- |
| product/base | `origin/main` | `8ee80d72984de29b4aca96eb4c46d8df1fcd50ed` | local = tracking = server at start |
| lane | `codeagent/bc-dns-find-predicates` | head in the PR | pushed after each commit, local = tracking = server |
| CI/workflow | `.github/workflows/tests.yml` on the PR's `pull_request` run | the lane head | the repo's own CI; no Mode-B (that is openclaw's) |
| presentation | draft PR to `main` | the lane head | |
| docs/proof | this file, the PR body, prototype README § *Read-only DNS-SD browse slice* | in the lane | |
| read-only inputs | bootstrap#1868 merge; bootstrap `main`; bootstrap#1872 head (open) | `246da85a116ecc4cfc2e7baa61b7525976f5cad9`; `e70096516db58267a6cd53070e7f462002bd106c`; `ba43623c2256691fe275f474b6006c6877c84902` | read with `git show`, nothing run |

Commits:
- RED tests `ee4ad8b0572b14e84a290a734d791d88f3860874`;
- implementation `d8b269180096749ee385695a333a3c329b6ef3ce`;
- docs `f5cf5ad852effacdf05e6beb659edba38edc4424`, the SHA that was reviewed;
- RED for the review's findings `6358bb9543d780f02f09304b9d09c2bf0217ba83`;
- their fix `a478d08baeb02c06e13e220d0862c0cfcaff38d2`;
- then docs.

## The TXT keys that exist

The workorder's "README §13 / RFC-0002 §13" is RFC-0001 §13: RFC-0002 has no §13, and the README's browse
section cites RFC-0001's. RFC-0002 §2.8 (finding the carrier) and §7.11 (registration trust) are the RFC-0002
parts read here.

| key | meaning (RFC-0001 §13.2) | registrar publishes it (`tools/dns/canticle-sd.py` at `246da85a`) | browse reads it | `dns-find` key |
| --- | --- | --- | --- | --- |
| `txtvers` | TXT format version, `1` | yes, `txtvers=1` | no | no |
| `sid` | key id, 16 hex | yes, from the host's manifest | yes: a mismatch with the grant's key id | **yes, exact** (hex, so case-insensitive) |
| `k` | `ed25519:<base64 of the public key>` | yes | yes: a mismatch with the grant's key | **yes, exact** |
| `streams` | comma-separated **public** stream names; omitted for non-public stations | only when `public_streams` is non-empty | yes: a set mismatch with `public_streams` | **yes, glob** (`*`, `?`) |
| `carrier` | beacon period, ms | no | no | no |
| `mode` | `lease` \| `mcast` \| `bcast` | no: none is true of stage-0 LAN unicast (RFC-0002 §7.9) | no | no |
| `grp` | multicast group, mDNS views only | no | no (unicast only) | no |
| `mtu` | `1100` | no | no | no |
| `prof` | regulation profile, e.g. `cr/1` | no | no | no |
| `mfst` | HTTPS URL of the fleet manifest | no | no | no |

Live, 2026-11-27T06:46:06Z, `dig +norec` against both `10.0.0.153` and `10.0.0.10`, same answers:

```
_canticle._udp.dandelion.cult.             300 IN PTR frond-gloss._canticle._udp.dandelion.cult.
frond-gloss._canticle._udp.dandelion.cult. 300 IN SRV 10 100 60991 silas.dandelion.cult.
frond-gloss._canticle._udp.dandelion.cult. 300 IN TXT "station=frond-gloss" "proto=udp"
_canticle._udp.dandelion.cult SOA  -> NOERROR, no answer; authority dandelion.cult SOA 2026112402 (no child zone)
rune._canticle._udp.dandelion.cult SRV -> NXDOMAIN
```

`station` and `proto` are not §13.2 keys. They are the pre-§13 record that #1868's `live` revision still carries
(`files/live/dandelion.cult.zone`). The browse ignores both. A reader whose manifest gave `frond-gloss` a public
catalog would get it as a hit with no TXT cross-check at all, because none of `sid`, `k` or `streams` is there.

**Why only three keys can be searched.** `sid`, `k` and `streams` are the keys the browse checks against the
manifest, and `find` evaluates them on the manifest grant, not on the TXT. The other seven are checked against
nothing. Searching them would let an unverified TXT decide a hit, and print a TXT value into a tool's result.
`station` (the instance label) is not a TXT key, and a name is what `dns-browse` already lists. So `dns-find`
refuses every other key, and refuses it before any query.

## What `dns-find` does

- **Candidates come from DNS, matches from the manifest.** PTR enumerates instances, and the browse's own rules
  keep an in-zone instance with exactly one unrevoked manifest grant that has `public_streams`. Each predicate is
  then evaluated on that grant: `streams` on its public names, `sid` on its key id, `k` on its key. Only a
  matching candidate's SRV and TXT are asked for. So a TXT can't add a stream or a key to a hit, and a station
  that doesn't match costs two queries fewer than in a browse.
- **The output is the browse's.** Same top-level shape, and the same row, plus `matched_on` (the key, the
  pattern, the values that matched, `values_truncated`), `where` (the predicates as parsed) and `refused`.
  `test_hit_is_the_browse_row_plus_matched_on` checks that a hit, minus `matched_on`, equals the browse row.
- **Fail closed.** A matching station whose TXT is malformed (`txt-invalid`: a repeated key, more than 32
  strings or 4096 bytes, or bytes that were not UTF-8) goes in `refused` with its name and key id. No locator
  from that record is printed. A bad predicate raises `ValueError` before any query, and the CLI exits 1. No
  match is an empty `stations` list, exit 0.
- **Case** (RFC 6763 §6.4): keys are case-insensitive US-ASCII; a non-ASCII key is refused rather than folded
  (the Kelvin sign would otherwise become `k`). Values are opaque, so they're exact, with one exception: a key
  id is hex. A `streams` glob may use only stream-name characters (`[a-z0-9.-]`), `*` and `?`, up to 64 bytes.
  An uppercase glob could never match a stream name (`ids.STREAM_NAME_RE`), so it's refused rather than
  answered with an empty list. For the same reason, `k` must be canonical base64.
- **AND** is per station. `--where streams=ops.alarm --where streams=hymn` matches a station that has both,
  not one stream that is both.
- **Bounds.** At most 8 predicates. The browse's caps stay: 32 instances (`truncated` then says that a miss
  covers only the first 32), 8 records, 128 cache entries, TTLs of 1–300 s, and dnspython's 2 s per query.
  Matching sees a station's whole public catalog. `public_streams` and each `values` list stop at 32, each with
  a `_truncated` flag. Matching time is bounded too: a glob is matched by a two-pointer wildcard matcher in
  O(pattern × name), at most 64 × 64 steps a name. A regex backtracks instead (see the review below).
- **The seam.** `find(domain, predicates, *, manifest, query, clock=time.monotonic)` does no I/O but the
  `query(name, kind) -> Answer` it is given, and returns a dict ready for `json.dumps`. A Python MCP tool can
  call it directly, with `KEY=PATTERN` strings or `Where` objects; a `Where` checks itself when it is made. A
  TypeScript tool (frond-ear, OpenClaw) can run `canticle dns-find` and parse its JSON. Or it can port it, and a
  port needs the browse's own rules as well as the predicate's:
  - the browse: `_candidates` (zone, dedup, one unrevoked grant with a public catalog) and `_row` (TXT fail
    closed, in-zone SRV targets). OpenClaw's `canticle_discover` already has them;
  - the predicate: `Where`, `_glob` and `Browser.find`, about 100 lines with their docstrings.
- **It is a look, not an arrival.** It wakes nothing, tunes nothing and marks nothing heard (RFC-0002 §3.3's
  rules for a search). It is not §3.3's `find(query)`, which searches the guide's signed descriptors. This one
  searches unsigned locators.

## Sibling: OpenClaw's `canticle_discover`

`prototype/openclaw-canticle/src/discover.ts` is a second browse, in TypeScript, with an optional exact
`stream` filter. It too filters on its operator catalog before asking for SRV/TXT, so the two agree on the
principle. They differ in three places, which this lane leaves as they are:

- `canticle_discover` returns a `txt-invalid` row as a hit, while `dns-find` refuses it;
- it caps output at 8 stations, where the browse caps at 32;
- it compares `streams` as an ordered string, where the browse compares sets.

If the follow-up tool is to match `dns-find`, the first one matters most.

## Evidence

All local, Python 3.12.3 with `cryptography` 50.0.1 (CI's pin). This host has no Python 3.11, so the PR's CI
run is the 3.11 receipt.

- **RED** at `ee4ad8b`: `test_dns_browse.py`, 28 tests. The 9 existing tests passed, and all 19 new ones failed
  for the expected reason: `module 'canticle.dns_browse' has no attribute 'find'` (FindTests), and
  `invalid choice: 'dns-find'` (FindCliTests). One CLI test first passed there for the wrong reason (argparse
  also exits on an unknown command), so it was tightened to require argparse's `--where` error before the
  commit.
- **GREEN** at `d8b2691`: the same 28 tests OK. The whole station suite: 476 tests OK in 92.8 s, and
  `git status --porcelain` showed nothing but the lane's own untracked files.
- **Independent review** of `f5cf5ad` (pr-review-toolkit code reviewer, given the diff and the workorder's
  requirements, not this report). It confirmed the security properties: no DNS-decided match, no private name,
  no TXT value printed, no out-of-zone query, and `browse()` unchanged. It found these, all repaired here:

  | finding | invariant, and where it lives | RED at `6358bb9` (on the `f5cf5ad` code) | fixed at `a478d08` |
  | --- | --- | --- | --- |
  | 1. a glob that cannot match backtracks exponentially (`'*' * 18 + 'z'`: 7.7 s; 30 stars: hours), before any DNS timeout, holding the GIL | matching is bounded in time; `Where.values` | `test_a_glob_that_cannot_match_returns_at_once` runs three such globs in a subprocess: `TimeoutExpired` at 10 s | `_glob`, a two-pointer matcher: the test takes well under a second. It agrees with `fnmatch.fnmatchcase` on 7,129,284 cases (exhaustive to pattern length 6 and name length 5, plus 20,000 random up to 64) |
  | 2. glob semantics, the cap at exactly 32 and the output shape unpinned: three mutants survived | `*` may match nothing, `?` exactly one; `values_truncated` only past 32; find's top level is browse's plus `where` and `refused` | new tests pass on the old code, as they should: their controls are the mutants R2, R3, R4 and R8 below | the mutants are killed |
  | 3. a `Where` built directly skipped every check | every predicate is checked, however it is made; `Where.__post_init__` | `test_a_where_built_directly_is_checked_as_parsed`: 5 × "ValueError not raised", and `Where('SID', …)` never matched | the checks moved into `__post_init__`; `parse` only splits |
  | 4. non-canonical base64 `k` accepted, then never matching; a key's Unicode fold (the Kelvin sign as `k`) | a predicate that can never match is refused; keys are US-ASCII (RFC 6763 §6.4) | `test_invalid_predicates_are_refused_before_any_query`: both "ValueError not raised" | the canonical re-encoding is required, and both parts must be ASCII |
  | 5. this report said a port needed only three functions | the browse's rules are part of any port | n/a (prose) | *The seam* above |

  The nearest sibling, OpenClaw's `canticle_discover`, has an exact `stream` filter and no glob, so finding 1
  does not reach it. There is no persistence, restart or partial-failure case: `find` keeps no state beyond a
  `Browser`'s TTL cache, and it refuses a bad predicate before its first query.
- **GREEN after the review** at `a478d08`: `test_dns_browse.py` 32 tests OK in 0.1 s. The whole station suite:
  480 tests OK in 98.6 s, and the tree was clean but for the lane's own files.
- **Mutations** at `d8b2691`, each alone, on a copy outside the repository; 9 of 9 killed:

  | mutation | killed by |
  | --- | --- |
  | drop the out-of-zone **instance** guard | `test_out_of_zone_instance_is_ignored_even_if_it_matches` |
  | drop the out-of-zone **SRV target** guard | `test_out_of_zone_srv_target_is_dropped`, `test_bounded_and_out_of_zone` |
  | a malformed TXT is a hit | `test_malformed_txt_is_refused` |
  | match private streams too | `test_stream_glob_matches_public_streams_only`, `test_no_match_exits_zero` |
  | keys case-sensitive | `test_exact_sid_and_k`, `test_prints_hits_as_json` |
  | `values` unbounded | `test_matching_sees_the_whole_public_catalog_and_bounds_what_it_prints` |
  | SRV/TXT asked before matching | `test_only_matching_candidates_are_queried` |
  | match only the printed 32 public names | `test_matching_sees_the_whole_public_catalog_and_bounds_what_it_prints` |
  | `sid` compared case-sensitively | `test_exact_sid_and_k` |

  After the review, the same nine (adapted to `_glob`) and eight more, on `a478d08`:

  | mutation | killed by |
  | --- | --- |
  | R1 the regex glob back | `test_a_glob_that_cannot_match_returns_at_once` |
  | R2 `?` may match nothing (acts as `*`) | `test_glob_wildcards`, `test_star_may_match_nothing_and_question_matches_exactly_one` |
  | R3 `*` must match at least one character | `test_star_may_match_nothing_and_question_matches_exactly_one` |
  | R4 `values_truncated` at exactly 32 | `test_matching_sees_the_whole_public_catalog_and_bounds_what_it_prints` |
  | R5 a `Where` made directly is not checked | `test_a_where_built_directly_is_checked_as_parsed` and four more |
  | R6 non-canonical `k` accepted | `test_a_where_built_directly_is_checked_as_parsed`, `test_invalid_predicates_are_refused_before_any_query` |
  | R7 non-ASCII keys folded | `test_invalid_predicates_are_refused_before_any_query` |
  | R8 `find` drops `authority` | `test_find_output_is_the_browse_output_plus_where_and_refused` |

  17 of 17 killed. The out-of-zone instance in the first test is `cael._canticle._udp.evilnet.org.`, whose suffix
  is as long as `example.org`'s. Without the guard, slicing the service name off it leaves `cael`, a manifest
  name. So the mutant queries another zone and reports it as a hit, which is exactly what the test refuses.
- **Browse unchanged.** `browse()` was split into choosing candidates and building rows. On three fixtures
  (empty; a mixed PTR with a revoked grant, a duplicate in upper case, a stranger, an out-of-zone name, bad SRV
  targets and repeated, bogus and non-UTF-8 TXT; and the instance cap with an oversized TXT), base `8ee80d7`
  and the lane gave byte-identical JSON over two browses, and the same resolver calls in the same order.

## Registration: what each other station needs to be findable (for 🌊 and 🪨; no action)

**Corrected after 🍃's review (bc#200, 2026-11-27).** `find` matches on the *reader's manifest grant*, never on
TXT. A bare row needs only **PTR + SRV**, which `frond-gloss` already has live in the parent zone, plus a reader
manifest that grants that station public streams. So **today's blocker to being found is item 4, the manifest**:
only `bellwether-elliott` has `public_streams`, and it has no PTR. The child zone (item 1) and bootstrap#1872's
trust stages are what a **TXT-cross-checked** row needs, not what being found needs. Nobody should wait on #1872
for discovery.

The full list, for a row whose TXT is also cross-checked:

1. **The zone.** The dynamic child zone `_canticle._udp.dandelion.cult` exists only in #1868's `next`
   revision. The pair serves `live` (SOA `2026112402` on both, no child SOA, read above). `next` is applied by
   FLEET-DNS step 3, which needs 🌊's GO.
2. **PTR (enrolment).** `@ PTR <station>._canticle._udp.dandelion.cult.`, TTL 300. It is seeded at the zone's
   first install for every `enrolled: true` row of `openclaw_dns_canticle_stations`: eight stations
   (`bellwether-elliott`, `cael`, `emeric`, `familiar`, `frond-gloss`, `frond-scribe`, `ronan`, `rune`), each
   with its host. A station added later is enrolled with `canticle-sd.py enrol`, under the registrar key
   `canticle-register`, which stays on the primary. A station never enrols itself (RFC-0002 §2.8).
3. **SRV and TXT (registration).** `<station>._canticle._udp.dandelion.cult. 120 SRV 0 0 9999 <host>.dandelion.cult.`
   and `TXT "txtvers=1" "sid=<key id>" "k=ed25519:<base64>"`, plus `"streams=<public names>"` when there are
   any, at most 200 bytes. `canticle-sd.py register <station> --key canticle-<host>.key` writes them from the
   host's own manifest. The SRV target must be in the zone, or the browse drops it.
4. **The reader's manifest.** The browse lists only stations whose entry in the **reader's** local manifest is
   unrevoked, uniquely named and has a non-empty `public_streams`. Bootstrap's `deploy/dns/README.md` says only
   `bellwether-elliott` has one today. So, even with every record in place, each station's owner must also mark
   its public streams in `fleet.json`. That file is unsigned: whoever can write it chooses what a reader trusts
   (RFC-0002 §7.9).
5. **The reader's resolver.** A seat that asks Pi-hole first gets NXDOMAIN for the canticle PTR (RFC-0002
   §2.8). It sees the records only by asking the pair directly, through the optional Pi-hole delegation
   (FLEET-DNS step 4, one dnsmasq line per server), or after its own cutover (step 5).

**Which key may write.**

- **Live today:** one shared key, `canticle-register`. The live primary's `update-policy` (`files/live/named-elliott.conf`)
  grants it the PTR at `_canticle._udp.dandelion.cult.` and SRV/TXT on every name under it, in the parent zone
  `dandelion.cult`. Whoever holds that one key may enrol, retire or overwrite any station's locator.
- **Source, #1868 `next`:** the child zone's `update-policy` keeps `canticle-register` for PTR (and SRV/TXT, for
  enrol), and adds one key per host, `canticle-<host>`, granted SRV and TXT on that host's own station names
  only. No per-host key has been made. The README's *Keys* says the controller makes them, and each seat's
  owner takes its own (POCKET or scp, 0600) when it starts to register.
- **SRP (RFC 9665), the alternative** of RFC-0002 §7.11, is a comparison, not a decision. BIND 9.18.28 removed
  SIG(0) validation, so it would need a registrar in front of BIND.

**What gates it.**

- **bootstrap#1872** (open, source only, head `ba43623c`) moves *zone-transfer* trust from address to TSIG in
  three stages (`ip` → `ip+tsig` → `tsig-secondary` → `tsig`), one stage per run, each with 🌊's GO. It makes
  `ip` the default, so `next`, and with it the canticle zone, can be applied without the `zone-transfer` key.
  It must not change the zones in the same run. It doesn't touch the registration keys, which are a separate
  custody question.
- **🌊's hold:** the scope of #1872 itself rules out any custody choice and any key made, read or copied. No
  DNS step runs without its own GO (FLEET-DNS: "Each step needs 🌊's GO").
- **Custody (🪨):** where `zone-transfer` and the six `canticle-<host>` keys are made and kept, and whether the
  shared `canticle-register` stays the only live writer until they exist. Per RFC-0002 §2.8, that waits on 🕯's
  answer about where the earlier keys were made.

**Blockers, in order, with owners.**

| # | blocker | owner |
| --- | --- | --- |
| 1 | review and merge bootstrap#1872 | 🌊 (GO); author: the scribe |
| 2 | apply `next` at `ip` (FLEET-DNS step 3), creating the child zone and seeding the eight PTRs | 🌊 (GO); the scribe's deployment reconcile (RFC-0002 Appendix C) |
| 3 | make and place the `canticle-<host>` keys, and decide what happens to the shared live key | 🪨 (custody), after 🕯's answer |
| 4 | each host registers its own stations (FLEET-DNS step 4) | each seat's owner |
| 5 | each station's `public_streams` in the readers' manifests | each station's owner, in `fleet.json` |
| 6 | resolvers that can see the zone: Pi-hole delegation or seat cutover | 🌫 (the delegation, optional); 🌊 (each cutover GO) |
| 7 | orphan expiry: BIND has no update lease (RFC 9664), so a dead host's SRV/TXT stays until `withdraw` | open, RFC-0002 §7.11: 🌿 (reconcile), 🌊, 🪨 |

**Registration-side proposals (not code; each one is an RFC-0001 amendment first).**

- **Class per stream, so that "who sings class `alarm` on `ops.*`?" has an answer.** No source has it today. A
  class belongs to an item, not to a stream (RFC-0001 §6.2). The manifest's `classes` says what a key *may*
  sign, for the whole station. The beacon's `stream-entry` (§9.8) carries no class. Two ways, both public
  only, as `streams` is:
  - a subtype per public class (`_alarm._sub._canticle._udp.<zone>`), as §13.2 already allows for public
    lenses, so a reader asks one PTR instead of enumerating;
  - or a TXT key, at most 9 characters, mapping public streams to classes, within the 200-byte guidance that
    `streams` already crowds.

  Either is still a hint. The receiver's grant check (§10.4) stays the authority on what a key may sign.
- **Key rotation and repeated keys.** RFC-0001 §13.5 says to publish the old and new `k=` side by side for one
  TTL. RFC 6763 §6.4 lets a client use only a key's first occurrence, and the browse goes further: it marks a
  repeated key `txt-invalid`. So `dns-find` would refuse a station mid-rotation. §13.5 should say how the two
  values are carried (two instances, or a second key name), or the browse's rule should change. That is an
  owners' choice, and this lane leaves it as it is.

## Not done here

- No DNS write, no key read, no zone or configuration change, no `nsupdate`. The only live queries were the
  `dig +norec` reads above.
- The MCP tool itself (🍃's repository) and any change to OpenClaw's `canticle_discover`.
- No RFC amendment: `dns-find` adds no TXT semantics and changes no wire bytes or record v1.
