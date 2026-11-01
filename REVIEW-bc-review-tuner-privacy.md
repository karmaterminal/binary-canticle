# Adversarial read-only review: human tuner synthetic-only and payload-free

## Review refs

| Category | Ref | Full SHA / result | Local / tracking / server equality |
|---|---|---|---|
| Product/base | PR #129 base `karmaterminal:main` | `bc5654feac6e3487118836664e3c91e4bdefdef5` | server `main` equals base; local PR object is available |
| Product/head | PR #129 head `karmaterminal:feat/human-dashboard-readonly-20261031` | `af2bd3ef53c642d25e77f5a85ff37161fac365cf` | local, PR head, and server PR branch equal |
| Lane | `codeagent/bc-review-tuner-privacy` | `af2bd3ef53c642d25e77f5a85ff37161fac365cf` | pushed unchanged before review; local and `origin` equal |
| CI/workflow | Station suite, local fallback (`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s prototype/canticle-station/tests`); workflow file in head | workflow blob `6e64f187354f38e490d942ac90ef08977651d990`; Python lock `e72fd59117e5e96556319d743c4057d1afafdd0d` | local head; no Mode-B run |
| Presentation | N/A | N/A | N/A |
| Docs/proof | N/A | N/A | N/A |

Issue binding: `karmaterminal/binary-canticle#114`.

## Path enumeration

| Path | Reachable bytes / behavior at head | Verdict | Test |
|---|---|---|---|
| `GET /` | Static `index.html` with synthetic-only boundary copy. It contains no listener data or item data. | Closed | `test_static_page_and_no_mutation_or_payload_paths` checks a planted private payload and station are absent, plus legacy paths 404. |
| `GET /tuner.js` | Static JavaScript. Fetches only `/api/stations` and renders names, synthetic/health fields and fixture streams. No listener event, item text, digest or body. | Closed | **No dedicated private-payload/private-station scan;** it is static and covered indirectly by RFC/proof documentation, not a unit assertion. |
| `GET /tuner.css` | Static CSS only. No dynamic or listener-derived bytes. | Closed | **No dedicated test.** |
| `GET /api/stations` | Default: `{"now_ms", "stations": [], "synthetic": false, "note": ...}`. With `--demo-fixture`: one hard-coded synthetic station/stream and all-zero synthetic identifiers. `TunerView.observe` discards every listener event; `TunerView` receives listener but never reads it. | Closed | `test_default_does_not_enumerate_verified_station_or_hidden_stream`, `test_fixture_is_synthetic_and_independent_of_listener`, and HTTP API tests plant private text, station, stream, finding, binary, digest and body-ref values, and scan the JSON. |
| Unknown and legacy `/api/*`, including `/api/ring`, `/api/tune`, `/api/leave`, `/api/sing`, `/api/hush`, `/api/journal`, `/api/item` | Fixed `404 {"error":"not found"}`; URL/query text is not reflected. | Closed | `test_static_page_and_no_mutation_or_payload_paths` checks the listed legacy routes; no planted-error-body scan. |
| `POST`, `PUT`, etc. on `/api/stations`, `/api/tune`, `/`, static paths | Fixed `405 {"error":"GET only"}`. No mutation, sing, hush or leave operation. | Closed | POST `/api/tune` 405; no planted private-value scan or tests for mutation on other paths. |
| 400 malformed request / 421 DNS rebinding / 413 oversized / 415 unsupported type / 429 / 503 branches | Fixed or supplied status text. Implemented fixed 400, 421 and 405 bodies; no route echoes target, Host, item text or private metadata. `413`, `415`, `429` and `503` are reason-table entries, not response-producing branches at this head. | Closed | Malformed Host and `..` path 421/404 tested; no 400/413 body privacy assertion and no planted payload in any error body. |
| Static query parameters and fragments | `urlsplit(target)` parses the path and ignores query parameters for known static/API routes. Unknown target remains 404 without echo. | Closed | `/../etc/passwd` 404; no named query-echo test. |
| Server log / optional log file | No tuner log option. Startup stderr prints only HTTP URL, UDP bind and multicast state. Listener errors go to listener/daemon surfaces outside this human HTTP implementation, not to the dashboard. | Closed | `test_tuner_has_no_event_log_option` verifies `--log` absent. |
| WebSocket / SSE | None: HTTP/1.1 one-request-per-connection, no upgrade handling or streaming response. | Closed | No explicit WebSocket/SSE test, but no implementation or route exists. |
| CORS and origin writes | No `Access-Control-Allow-*` header. `Cross-Origin-Resource-Policy: same-origin`. GET API is same-origin; every request is allowed only for loopback/localhost Host values. Mutations are 405. | Closed | Evil Host gets 421; loopback-only constructor and no mutation test; no browser cross-origin fetch test. |
| Cache | `Cache-Control: no-store` and security headers on every response. | Closed | API test checks every `SECURITY_HEADERS` entry. |
| Static HTML embedded data / inline script / data attributes | The HTML has no embedded listener JSON or item payload. Synthetic fixture data is fetched only from `/api/stations`. | Closed | No whole-DOM private-payload scan; browser proof checks named demo station/stream and no item/ring/tune elements. |
| Real-station switch | No real-station switch, environment variable, config key or live API mode. `--demo-fixture` adds only a hard-coded synthetic station. Real listener traffic is discarded. | Closed | Fixture independence test proves output is unchanged after planted live traffic. |
| Future presence declaration | RFC requires a future broadcaster-signed public-presence declaration. No declaration or public-presence gate is implemented or exposed as an enabled option. | Closed / gated | No real-presence test, because no real-presence mode exists. |

## Findings

### 1. MEDIUM - Negative proof omits several privacy surfaces

**Failure scenario:** a future change could add listener-derived data to `/tuner.js`, `/tuner.css`, an error body, or the computed DOM, while the existing unit assertions would not scan that byte surface. The head code is closed, but the review is not fully protected against a guard regression.

**Evidence:** `prototype/canticle-station/tests/test_tuner.py:127-178` scans the `/api/stations` JSON and `/` HTML with planted private values, but not `/tuner.js`, `/tuner.css`, 400/405/421 error bodies, or the browser DOM's full `innerHTML`/`textContent`; `prototype/canticle-station/proofs/web-lanes/browser.cjs:14-22` scans named element types and station/stream names, but does not plant the distinctive private text/station constants or search whole DOM bytes. The head implementation itself remains closed.

**Fix:** add one deterministic privacy matrix that feeds the distinctive private payload and private station to the real listener/view composition, then for `/`, `/tuner.js`, `/tuner.css`, `/api/stations` and fixed error statuses assert both payload and private station absent from raw bytes; in headless Chromium assert absent from `document.documentElement.outerHTML`, `innerText` and response bodies. Remove the test or guard and the planted negative control must go RED.

### 2. LOW - The available CI dependency floor is below the lane's accepted suite floor

**Failure scenario:** the station suite cannot provide a clean local acceptance receipt in this worktree because `/usr/bin/python3` is Python 3.12.3 with cryptography 41.0.7, while the repository requires cryptography 45 or newer.

**Evidence:** focused `test_tuner.py` passed 7/7 under Python 3.12.3. The station suite ran 321 tests: 309 passed and 12 failed; all 12 failures are doctor/onboarding exits caused by `cryptography 41.0.7; this spike needs 45 or newer`. This is an environment-floor mismatch, not an observed privacy failure.

**Fix:** run the suite in the repository's Python 3.11/hash-locked environment and record the CI receipt; no product change is implied.

## RFC and proof consistency

The RFC-0001 §18.9 text matches the implementation: live stations are absent by default, `--demo-fixture` is explicitly invented, there is no ring/tune/item route, and real presence requires a future signed declaration (`rfc/0001-binary-canticle.md:2791-2813`). The prototype README matches those claims (`prototype/canticle-station/README.md:219-223`). The implementation and tests remove the old live ring/tune behavior, so RFC I-6 and the human-boundary rules are not contradicted.

## Validation

- PR refs resolved with server equality at head `af2bd3ef53c642d25e77f5a85ff37161fac365cf`.
- Focused tuner privacy proof: 7 tests passed with `python3`, available as Python 3.12.3.
- Station suite: 321 tests, 309 passed, 12 failed solely on the local cryptography floor mismatch (41.0.7 versus 45+); no privacy assertion failed.
- No Mode-B run and no Gate 3g fallback was used.

## Verdict

**PASS WITH MEDIUM TEST-COVERAGE FOLLOW-UP.** There is no open item-text or private-metadata route at this PR head, no live-to-human data bridge, no real-station mode switch, and no log/DOM/ring/tune mutation path. The primary remaining risk is incomplete negative proof across every static and error byte surface, not an implementation leak found in the enumerated paths.
