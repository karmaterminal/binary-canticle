# Bounded loopback smoke — 2026-11-23

Base: `d4c306618f7f77658fe73705d58b2744f2486701`. Existing k6 executable: `v2.0.0 (commit/8c3be52cc1, go1.26.3, linux/amd64)`. Python cryptography: `50.0.2`. No dependency installation.

These are real low-load runs with one VU, six offers, 250ms closed-loop pacing and a 1000ms offer deadline. The full path is production station control → real signed UDP → byte-preserving instrumented loopback forwarder → production daemon → complete verified surface record at a Unix client. Station and daemon are separate tasks in the shared fixture process, not a production multiprocess benchmark.

- `smoke/`: actual k6 exit **0**, 6 offered / 6 delivered / 0 missed.
- `negative/`: actual k6 exit **99**, 6 offered / 5 delivered / 1 missed. Every UDP copy of sequence1 is deliberately withheld at the instrumentation forwarder, after its first ingress timestamp is recorded. It is still accepted by the station and remains in the producer population; this is not a fabricated receiver failure.
- `repeat/`: fresh smoke after the negative, actual k6 exit **0**, 6 offered / 6 delivered / 0 missed.
- All three: no pending or duplicate surface records, conserved fixture packet accounting, child reaped, owned tasks terminated, Unix sockets/state removed, TCP/UDP ports rebindable.

Every folder contains the actual `k6-summary.json`, `k6.log`, fixture rows and hashes, `process.json`, run parameters and cleanup receipt. Source paths in the commands identify the isolated test checkout; no private signing key or fixture bearer token is retained.

## Recheck the receipts

From the repository root:

```sh
python3 prototype/load-testing/verify.py prototype/load-testing/evidence/2026-11-23-smoke/smoke
python3 prototype/load-testing/verify.py prototype/load-testing/evidence/2026-11-23-smoke/negative --negative
python3 prototype/load-testing/verify.py prototype/load-testing/evidence/2026-11-23-smoke/repeat
```

The negative verifier confirms a deliberately FAILED k6 run; its own successful exit does not turn that run green. `source-sha256.json` records source bytes at these runs. These retained folders were freshly re-executed positive → negative → positive after cleanup corrections and verifier hardening; they are not backfilled earlier runs. The manifest also covers the five-line station startup correction.

Focused harness/regression suite: **24/24 PASS** (`harness-tests.log`), including accelerated real-k6 supervisor timeout and independent cleanup-fault probes. The two direct intermediate station-start failure/cancellation regressions first failed on base (`station-startup-red.log`) and pass with the correction. The station regression log is retained separately; no protocol bytes or admission policy changed.

## Claim ceiling

`source-sha256.json` pins the measured `665c0f6` source, not later revisions.
In particular `run.py` and `verify.py` changed in the subsequent process-mode
increment; compare the process evidence's own manifest for that measured head.
Re-verifying a historical receipt is not re-executing its measurement.

No flood/recovery capacity, offered-rate saturation, cross-host/LAN delivery, frond-ear push, same-session read/ack, model hearing, full RFC conformance or installation is proved. Missing items remain outside success-only latency percentiles and inside explicit miss counts; deadline-censored Trends are labelled as censored, not measured delivery. HTTP request duration is orchestration, not UDP transport latency. The native #171/#173 socket/fair-admission rows remain authoritative for their own declared workloads.
