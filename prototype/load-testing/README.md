# Bounded loopback k6 baseline

A small **local correctness/measurement harness**, not a stress or flood result,
not full RFC conformance, and not evidence that a model heard anything.

## The real path

	real k6 schedule/checks/metrics
	  -> ephemeral loopback HTTP test-control adapter
	  -> production station Unix control socket / sing
	  -> production runner.run_station / signed carousel UDP
	  -> instrumented loopback UDP forwarder (original bytes unchanged)
	  -> production Daemon.run / independent verification + durable state
	  -> real Unix SOCK_STREAM record-v1 client / complete newline

By default the production station, daemon and record client run as separate
asyncio tasks inside one fixture process. They are **not mocked**. The opt-in
`--processes` mode below isolates station and daemon in separate OS processes;
neither mode is a deployment or capacity benchmark. The relay is test instrumentation,
not an implementation of the RFC relay protocol. The only production-source
change is a five-line station-startup cleanup correction: if Unix control-server
startup fails or is cancelled, close its UDP socket before propagating the
failure. Regression probes fail on the base and pass with the correction. No
daemon/plugin/RFC or wire-format change is made. One ephemeral signing key exists only in memory; the unsigned
test manifest and state live in a private /tmp directory and are deleted.

Plain k6 has no generic UDP transport. Its HTTP endpoint requests an actual
station submission; it never substitutes an HTTP response for broadcast receipt.
A response reports delivery only after the complete matching **verified surface
record** is read from the daemon socket, correlated by the full identity tuple
and original-frame SHA-256. Submission acknowledgments do not count as delivery.
All payloads are short synthetic chatter; no sessions, real keys, LAN,
multicast, models, installed services or production configuration are involved.

The fixtures/scenarios split borrows the useful organization of
karmaterminal-openclaw-docs/proof-harness/k6, **not** its gateway methods or
claims. This harness has no OpenClaw gateway dependency.

## Run from the repository root

Use the station development Python environment (Python 3.11+, cryptography >=45)
and a local k6 binary. Do not install a new dependency set just for this harness.
Manual acceptance runs stay on the local host: no root, network namespaces,
xk6 extension or external server. CI runs only the bounded tests described below.

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
      -s prototype/load-testing/tests -v

The two real-k6 timeout probes resolve `CANTICLE_K6` first, then `k6` on
`PATH`. Without a binary they skip by default; set `CANTICLE_REQUIRE_K6=1`
to make absence a failure instead. For an explicit local acceptance run:

    CANTICLE_REQUIRE_K6=1 CANTICLE_K6="$(command -v k6)" \
      PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
      -s prototype/load-testing/tests -v

CI now fetches the official k6 v2.0.0 Linux amd64 archive into runner-temporary
storage, checks it against `.github/ci/k6-linux-amd64.sha256` before extraction
or execution, and sets both `CANTICLE_K6` and `CANTICLE_REQUIRE_K6=1` for this
suite. Missing or corrupted k6 fails the job instead of silently skipping its
two real-k6 timeout/reap probes. This changes no system package, root privilege,
workflow permission or secret boundary. The CI probes are accelerated loopback
cleanup tests, not the acceptance smoke, a timing benchmark or a live host run.
The historical Python 3.11 receipt for #189 remains 50 counted, 48 passed,
2 skipped; it is not retroactively a real-k6 execution result. Local 50/50
results included a local binary.

First run the fixed low-load smoke: six offers, one VU, at least 250 ms between
completed iterations; a 1,000 ms per-offer delivery deadline. This is **closed
loop** scheduling, not a promised constant arrival rate. k6 owns the iteration
budget, pacing, VUs, checks, thresholds and JSON summary.

    PYTHONDONTWRITEBYTECODE=1 python3 prototype/load-testing/run.py \
      --k6 "$(command -v k6)" --out /tmp/canticle-k6-smoke
    python3 prototype/load-testing/verify.py /tmp/canticle-k6-smoke

Use NEW output directories outside the repository; old artifacts are never
overwritten. The second command checks real summary counts and thresholds,
fixture accounting and cleanup receipts. It does not fabricate a k6 summary.

Then run the negative control. It deliberately drops **every UDP copy of item
sequence 1**, after recording its first arrival. The known offered item stays
in both the failure and censored-latency populations. There is no special
"negative passes" threshold: the k6 run **must fail** (normally exit 99).

    PYTHONDONTWRITEBYTECODE=1 python3 prototype/load-testing/run.py \
      --k6 "$(command -v k6)" --out /tmp/canticle-k6-negative --drop-first
    # The prior command MUST be nonzero; inspect it, do not hide it with || true.
    python3 prototype/load-testing/verify.py /tmp/canticle-k6-negative --negative

Expected negative accounting: offered=accepted=arrived=6, delivered=5, missed=1,
pending=0, deadline-miss rate=1/6. Success-only latency has five samples;
offer-to-record-or-deadline and arrival-to-record-or-deadline retain six.
verify.py checks the **failed** zero-miss threshold as well as the denominator.
A failed HTTP request also remains in k6's attempted-offer denominator; missing
fixture rows, missing samples or an incomplete schedule cannot produce a pass.

## Opt-in isolated processes

`run.py --processes` runs the production station and daemon in distinct,
short-lived OS processes. The controller/relay/complete-record client remain
in the parent fixture process; k6 remains a separate controller child. This
mode is a bounded localhost correctness probe, not a deployment, throughput
benchmark, fairness/recovery acceptance (#173/#177), or session-hearing proof.
The default shared-task mode above remains unchanged.

Use new external output directories, then verify each receipt as above:

    python3 prototype/load-testing/run.py --processes --out /tmp/canticle-process-positive
    python3 prototype/load-testing/verify.py /tmp/canticle-process-positive
    python3 prototype/load-testing/run.py --processes --drop-first --out /tmp/canticle-process-negative
    # Require actual nonzero (normally 99), then:
    python3 prototype/load-testing/verify.py /tmp/canticle-process-negative --negative

The full population, complete-record hash boundary, censoring and zero-miss
threshold do not change. Process mode adds child PID/liveness and cleanup
exit/reap receipts; passing delivery cannot excuse early child death or failed
cleanup. No production configuration, installed service or non-loopback bind
is involved.

The process-specific tests include early station/daemon death, real production
startup failure, spawn failure, readiness timeout, forced KILL, controller wall
timeout, and a record-client reconnect followed by a new exact-identity offer.
That reconnect test keeps the daemon running; it is not daemon restart recovery,
join-snapshot/custody acceptance, or delivery of items published while offline.

Recorded localhost receipts are in `evidence/2026-11-24-processes/`: actual k6
positive → mandatory negative → fresh positive, plus verifier base/revert RED
and current GREEN. `manifest.json` pins the measured source bytes and runtime.
The structural mutation tests deliberately use synthetic process fields; those
are verifier tests, never process-run receipts.
The verifier tests also read all three committed real process receipts above.
Historical source manifests stay pinned to their measured commits; later
portability, comments and supervision changes do not silently refresh them.

## What latency means

All fixture timestamps use the same monotonic clock, in integer nanoseconds.
Per-item timestamps and hashes are saved for audit in fixture-report.json.

- **canticle_arrival_to_record_success_ms**: first signed item datagram arrival
  at the fixture's UDP ingress -> the full matching daemon record newline at
  the Unix client. Successful/on-time items only; never interpret this alone.
- **canticle_arrival_to_record_or_deadline_ms**: the same start, ending at the
  record or the offer's deadline if missing. Includes deliberately dropped
  items and marks their censoring explicitly in the per-item rows. An offer
  whose UDP frame never arrives has no arrival sample; arrived and offered
  populations are both reported, so this omission cannot hide a miss.
- **canticle_offer_to_record_or_deadline_ms**: offer registration before Unix
  submission -> record or deadline. Includes **every registered offer**, even
  submission failures and missing arrivals. A censored deadline is **not** an
  observed delivery latency and must not be reported as one.
- **canticle_deadline_miss**: failures / all k6 attempted offers, threshold zero.
  Fixture accounting independently requires offered = delivered + missed +
  pending and offered = accepted + submit_errors. Late records stay misses;
  they never retroactively turn a deadline failure green.
- k6's **http_req_duration** measures control HTTP, submission, receipt/deadline
  waiting, serialization and the response. It is **not** transport item latency.

The arrival metric includes the instrumentation forwarder's extra signature
parse/forward, an extra local UDP hop, Python event-loop scheduling, production
daemon verification/state fsync, Unix delivery and client scheduling. It starts
at userspace ingress, **not** a kernel/NIC timestamp. HTTP request ingress and
submission precede this start; HTTP response overhead follows the record. The
single shared process can perturb scheduling, and this baseline cannot establish
production throughput or isolate daemon-only CPU cost. Do not subtract an
assumed orchestration constant or claim model/session/agent-heard latency.

## Bounds, supervision and receipts

Only literal 127.0.0.1 addresses and ephemeral TCP/UDP ports are constructed.
The HTTP API requires a random per-run token passed only in the child's
environment; redirects are disabled. It has only /offer and /stats, no shell,
file, destination, payload, socket-path or service-control operation. Requests
have a 2 KiB header/128-byte body bound and four-second timeout; connections and
error storage are bounded. Invalid/duplicate offer ids cannot grow the ledger.

Hard parameter limits: 1-16 total items, 1-2 VUs, deadline 500-2,000 ms, pacing
250-1,000 ms, synthetic payloads, 10 s signed item TTL. k6 has a 50 s scenario
limit plus 1 s graceful stop; the supervisor imposes a 55 s child wall deadline,
30 s child CPU, 128 child descriptors and 8 MiB per child output file. GOMAXPROCS=2
and GOMEMLIMIT=128MiB are soft Go controls, **not hard RSS isolation**. The
fixture has bounded application state, but this is not a cgroup memory proof.

The supervisor strips inherited proxies, K6 cloud/output configuration and
credentials, disables usage reporting, and binds k6's own API to loopback port
0. SIGTERM/interrupts and ordinary exceptions unwind cleanup; SIGKILL/power loss
cannot run application cleanup (as with any process). In default shared-task mode the only child process is k6, in its own
process group: TERM then KILL if needed, followed by wait/reap. With
`--processes`, Python spawn adds two production coroutine children; neither
inherits the parent sockets or the other child's state. They have bounded
readiness, a 65-second coroutine lifetime, and ordered TERM/KILL/reap. Their
PID/start/ready/exit/reap receipts accompany the existing cleanup checks.
These children do not have cgroup isolation or the k6-specific resource limits.
Fixture shutdown closes HTTP and its handlers, stops the station before the
daemon, closes the record client and relay, joins owned tasks and removes the
temporary directory. cleanup.json records task termination, removed Unix
sockets/state, successful rebinding of observed station-sender, relay, daemon and HTTP ports,
and child reap. The sender port is learned from the first verified test frame;
intermediate-startup probes separately check the actual station socket closes
even before it has sent anything.

Artifacts per run (outside the repository):

- run.json: bounds, executable command and measurement boundary; no token/key.
- process.json: actual k6 and supervisor exit codes, child-start/reap evidence.
- fixture-report.json includes the fresh run ID and expected producer ID plan,
  constructed before any submissions (never inferred from admitted records).
- k6-summary.json: actual k6 handleSummary JSON, including thresholds/metrics.
- k6.log: the actual child stdout/stderr.
- fixture-report.json: counts, raw monotonic boundary timestamps, per-item
  identities/hashes, on-time/miss/late flags and packet conservation.
- cleanup.json: cleanup checks; failure.json if orchestration failed.

The unit suite covers parameter/request bounds, duplicate ids, dropped and
missing-arrival denominators, success timing, late records, hash mismatch,
conservation, real loopback receipt/drop, submission failure, normal cleanup,
scenario exceptions, failure after partial startup and an accelerated supervisor
wall-timeout probes using the real k6 executable (required in CI, optional
locally). These are separate from k6 acceptance runs; a green unit suite is not
an acceptance smoke or a latency result.

## Deliberate exclusions

No fair-admission changes (#173), host join/snapshot work (#161), slow readers,
untrusted-publisher floods, mixed hosts, session landing, stress capacity,
network-loss distributions or RFC conformance claims. Expand one bounded
scenario at a time after the smoke and mandatory failing negative control
produce their real receipts.
