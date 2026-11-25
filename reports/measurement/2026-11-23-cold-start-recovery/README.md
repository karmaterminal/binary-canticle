# Newcomer recovery under a sustained forged flood, on #173

**Status:** measurement for [#173](https://github.com/karmaterminal/binary-canticle/pull/173) (cure for
[#171](https://github.com/karmaterminal/binary-canticle/issues/171)), pass 3. The rows, the deadline and the run counts were declared in
[`PLAN.md`](PLAN.md) before any run; what was added later is dated there. Host **ronan, aarch64** (20 cores, kernel
`7.0.0-1019-nvidia`), Python 3.12.3, **cryptography 50.0.1** (the CI lock, recorded in every run; the doctor's check is in
[`results/runtime.json`](results/runtime.json)). Loopback, throwaway keys, every process at `nice -n 19 ionice -c3`, one measurement at a
time. Nothing live was touched, and the numbers don't carry to another host.

| ref | SHA |
|---|---|
| head: #173's daemon | `ab61baf2fa1989fc3b3959db8bdcf00433508328` (the PR's head is `a0862c3eeb0b84236661451ca5c3d00127536d27`, documentation only over it) |
| base: `main` | `d4c306618f7f77658fe73705d58b2744f2486701` |
| `narrow`: the split candidate | `codeagent/bc-173-narrow`, `f8a91c1f19d1a990b376ff287436fd519b0126b9`; `tests.yml` run 45338423871 on it, 4 of 4 jobs green |
| `nobudget`: the second candidate | head + [`toggles/a-budgets.patch`](toggles/a-budgets.patch); no branch |
| `nobudget-wake`: a diagnostic, not a candidate | head + [`toggles/a-budgets-wake.patch`](toggles/a-budgets-wake.patch); no branch |
| this lane | `codeagent/bc-173-pass3c`, from `codeagent/bc-173-pass3b` `98fa9cbe7b93fdfe834fe6d75f0b43193ddf1d10` |
| CI workflow | `.github/workflows/tests.yml`, as on `main` |
| presentation ref | N/A |

## Verdict

**No tree passes both gates, so nothing here is proposed for merge, and #173 stays held.** The two gates are judged apart; neither stands in for
the other.

| | head (#173) | base | `narrow` | `nobudget` |
|---|---|---|---|---|
| **Gate 1**: an established station is protected. Scaled rows, 5 runs each (3 of base), 57 of 57 during the flood | **PASS**: 25 of 25 runs | FAIL: 0 of 15 | FAIL: 5 of 25 (R4 only) | **PASS**: 25 of 25 |
| Gate 1 at full length (570 s R, 300 s F) | not run in this pass: PASS in pass 2 (R rows, `e2d331d0`) and pass 1 (F rows, `0d8fafe4`, an earlier `intake.py`); their files don't record the runtime | FAIL (#171, 1 run of each; not checked here) | FAIL: 5 of 11 rows pass (R4a, R4b, F0, F2b, F4: 5 of 5 runs each); R1, R2, R3, R3c, F3b, F5 fail on their first run | FAIL: 10 of 11 rows pass (5 of 5 runs each); R4a fails (11 of 57 on time) |
| **Gate 2**: cold start under churn, row 0. 8 cells, one miss fails a cell | **FAIL**: 1 of 8 cells | FAIL: 1 of 8 | FAIL: 2 of 8 | FAIL: 1 of 8 |
| a bound on a newcomer's recovery that follows from the code (a churned flood from its own host) | **none** | none | none | none |
| an *estimate* from the code, not a bound: the flood from one other host | one round of the lanes and a retry, 0.18 s; seen 0.155-0.185 s at the client (row 1h; conditions in "What the code estimates") | none | none | same queues as the head, not measured |

- **The cold-start delay has no bound on the head** when the churned flood comes from the newcomer's own host. It is a lottery: a copy of a newcomer's frame is checked with
  chance *C/R*, the checks spent on strangers over the flood's rate. The code says so and the runs fit it (below). It grew from 20 000/s to 100 000/s (15 runs a side); from there to 200 000/s
  (15 and 5) the runs can't tell. One head newcomer at 100 000/s was not heard for the whole 64 s, and lost all 20 of its items.
- **The head fails 7 of 8 deciding cells, and 6 of 6 saturation cells of row 1.** Among the churned rows it passes only the station that starts when the flood does, at
  20 000/s (and, row 1h, one on another address; and of the ports-held-open companions 5 of 14). Base misses the same deadline too, by 4 of 240 items at 20 000/s (2.03-4.03 s) and by 156 of 240 at 100 000/s (43 lost). These
  are acceptance thresholds for this workload, and neither tree was built to them.
- **Attribution: the runs are consistent with the head's budget of 1 000 checks a second for all strangers of a key being the cause.** Lifted alone it does not pass: at 20 000/s a second defect shows, at 100 000/s the lottery is still there
  (C/R 13 %). The superseded runs pointed the same way; what changed is that the pinned runtime does not pass `a-budgets`.
- **The split does not make a candidate for landing.** `narrow` carries the parts that don't cause the delay, and protects nobody: it fails gate 1 as base does,
  but for replays (R4), and it reports its losses. At 100 000/s its newcomer's items are late and lost as on base.

## What ran

Every newcomer run records its tree, the versions and the load before it; `established*` and `scaled-*` runs record the versions only. One run at a time. "5/3" is runs of the head / of base.

| row | what | runs | raw |
|---|---|---|---|
| 0 | recovery, deciding: `churn-40`, 20 000 and 100 000/s, offsets 0, 5, 30 and 120 s; head, base, `narrow`, `nobudget` | 5 / 3 / 5 / 5 | `recovery-churn.json` (144) |
| gate 1, scaled | R1, R2, R3, R3c, R4; the same four trees, and `nobudget-wake` | 5 / 3 / 5 / 5 / 5 | `established.json` (90), `established-wake.json` (25) |
| 1 | saturation, `churn-12/40/200`, offset 1 s | 5 / 3 | `saturation-churn.json` (48) |
| 2 | attribution, five toggles of the head, offset 1 s | 5 each | `attribution.json` (50) |
| 2w | attribution, wake: `nobudget-wake` on row 0's eight cells | 5 | `recovery-wake.json` (40) |
| 1s, 1r, 1h | evenly spaced sender; 200 000/s; the newcomer on another address | 5 / 3 (head only: 1s, 1r) | `saturation-extra.json` (15), `otherhost.json` (16) |
| 0c, 1c | companions: the `fixed` reading (12, 40 and 200 ports) | 5 / 3 | `recovery-fixed.json` (64), `saturation-fixed.json` (48) |
| candidates | pass 2's cold start, spoof, relay-first rows, head beside them; full length: R rows 570 s, F rows 300 s | 5 each (scaled); 1 run of each full-length row, then four more of every row whose first run passed (done: 82 runs) | `scaled-*.json` (150), `full/` |
| 1m | the model, the head's own `Intake` in virtual time, alone, last | 4 seeds a line | `model-head.md` |

The deadlines (PLAN.md): the first valid frame at most 1.0 s after the newcomer's first actual send, each item at most 2.0 s after its own; one
miss, late or lost, fails its cell. "More than 10 s late" is a label ("more than one loop late"), never a gate. The flood ran 59 s or more past
every deadline in every run (`flood_end_after_last_deadline_s`), so no pass was scored from recovery after it stopped.

## Gate 2: cold start under a churned flood (row 0)

`churn-40`: 40 sockets open, each datagram from a newly opened one. In a cell: the verdict, the worst first valid frame, first-frame misses (>
1.0 s), item misses (> 2.0 s or lost). [`newcomer_table.py`](newcomer_table.py) prints the full table, with every run's first frame and the refusals.

| row (sources-ports-rate-offset) | head | base | narrow | nobudget |
|---|---|---|---|---|
| churn-40-20000-0 | PASS: worst first 0.04 s; first 0/5, items 0/100 | PASS: worst first 0.02 s; first 0/3, items 0/60 | **FAIL**: worst first 0.02 s; first 0/5, items 1/100 | PASS: worst first 0.16 s; first 0/5, items 0/100 |
| churn-40-20000-5 | **FAIL**: worst first 1.78 s; first 2/5, items 7/100 | **FAIL**: worst first 0.03 s; first 0/3, items 2/60 | **FAIL**: worst first 0.08 s; first 0/5, items 2/100 | **FAIL**: worst first 3.74 s; first 4/5, items 30/100 |
| churn-40-20000-30 | **FAIL**: worst first 3.05 s; first 4/5, items 35/100 | **FAIL**: worst first 0.03 s; first 0/3, items 1/60 | PASS: worst first 0.22 s; first 0/5, items 0/100 | **FAIL**: worst first 18.66 s; first 5/5, items 100/100 (lost 0, > 10 s 60) |
| churn-40-20000-120 | **FAIL**: worst first 3.04 s; first 4/5, items 24/100 | **FAIL**: worst first 0.03 s; first 0/3, items 1/60 | PASS: worst first 0.08 s; first 0/5, items 0/100 | **FAIL**: worst first lost; first 5/5, items 100/100 (lost 20, > 10 s 80) |
| churn-40-100000-0 | **FAIL**: worst first 7.21 s; first 4/5, items 57/100 (lost 0, > 10 s 19) | **FAIL**: worst first 0.63 s; first 0/3, items 37/60 (lost 14, > 10 s 10) | **FAIL**: worst first 1.25 s; first 1/5, items 60/100 (lost 15, > 10 s 26) | **FAIL**: worst first 1.01 s; first 1/5, items 0/100 |
| churn-40-100000-5 | **FAIL**: worst first 34.23 s; first 5/5, items 86/100 (lost 0, > 10 s 66) | **FAIL**: worst first 0.34 s; first 0/3, items 41/60 (lost 7, > 10 s 17) | **FAIL**: worst first 1.14 s; first 1/5, items 63/100 (lost 12, > 10 s 32) | **FAIL**: worst first 1.57 s; first 2/5, items 4/100 |
| churn-40-100000-30 | **FAIL**: worst first 48.72 s; first 5/5, items 71/100 (lost 0, > 10 s 34) | **FAIL**: worst first 2.34 s; first 1/3, items 41/60 (lost 14, > 10 s 12) | **FAIL**: worst first 1.14 s; first 2/5, items 73/100 (lost 15, > 10 s 35) | **FAIL**: worst first 1.86 s; first 2/5, items 9/100 |
| churn-40-100000-120 | **FAIL**: worst first 30.34 s; first 4/5, items 65/100 (lost 0, > 10 s 38) | **FAIL**: worst first 0.93 s; first 0/3, items 37/60 (lost 8, > 10 s 17) | **FAIL**: worst first 1.04 s; first 1/5, items 69/100 (lost 10, > 10 s 23) | **FAIL**: worst first 1.07 s; first 1/5, items 0/100 |
| **cells passed** | **1 of 8** | **1 of 8** | **2 of 8** | **1 of 8** |

The first valid frame per run, seconds; `lost` is not heard at all for the whole flood:

| row | tree | first valid frame, s, per run | item latency, s: min / median / p95 / max | > 10 s late | lost | verdict |
|---|---|---|---|---|---|---|
| churn-40-20000-0 | head | 0.04, 0.03, 0.04, 0.03, 0.03 | 0.01 / 0.02 / 0.02 / 0.04 | 0 | 0 | PASS |
| churn-40-20000-0 | base | 0.02, 0.01, 0.02 | 0.02 / 0.03 / 1.03 / 1.04 | 0 | 0 | PASS |
| churn-40-20000-0 | narrow | 0.02, 0.02, 0.02, 0.02, 0.02 | 0.02 / 0.08 / 1.07 / 2.08 | 0 | 0 | **FAIL** |
| churn-40-20000-0 | nobudget | 0.09, 0.12, 0.16, 0.12, 0.15 | 0.02 / 0.23 / 0.69 / 0.98 | 0 | 0 | PASS |
| churn-40-20000-5 | head | 0.95, 1.78, 0.40, 0.86, 1.48 | 0.01 / 0.02 / 2.01 / 2.02 | 0 | 0 | **FAIL** |
| churn-40-20000-5 | base | 0.03, 0.03, 0.03 | 0.02 / 0.03 / 1.03 / 2.04 | 0 | 0 | **FAIL** |
| churn-40-20000-5 | narrow | 0.08, 0.07, 0.07, 0.08, 0.08 | 0.06 / 0.08 / 0.08 / 2.09 | 0 | 0 | **FAIL** |
| churn-40-20000-5 | nobudget | 2.35, 1.77, 0.27, 1.27, 3.74 | 0.06 / 1.42 / 3.37 / 3.74 | 0 | 0 | **FAIL** |
| churn-40-20000-30 | head | 2.74, 2.27, 0.52, 1.07, 3.05 | 0.01 / 1.02 / 4.02 / 4.03 | 0 | 0 | **FAIL** |
| churn-40-20000-30 | base | 0.03, 0.03, 0.03 | 0.02 / 0.03 / 1.02 / 2.03 | 0 | 0 | **FAIL** |
| churn-40-20000-30 | narrow | 0.22, 0.08, 0.08, 0.08, 0.08 | 0.07 / 0.08 / 1.07 / 1.08 | 0 | 0 | PASS |
| churn-40-20000-30 | nobudget | 16.81, 9.17, 18.66, 16.39, 6.20 | 3.35 / 14.44 / 17.90 / 18.66 | 60 | 0 | **FAIL** |
| churn-40-20000-120 | head | 1.10, 3.04, 0.78, 1.14, 2.34 | 0.01 / 1.01 / 4.02 / 4.03 | 0 | 0 | **FAIL** |
| churn-40-20000-120 | base | 0.03, 0.03, 0.03 | 0.02 / 0.03 / 1.02 / 4.03 | 0 | 0 | **FAIL** |
| churn-40-20000-120 | narrow | 0.07, 0.07, 0.08, 0.08, 0.07 | 0.07 / 0.08 / 1.07 / 1.09 | 0 | 0 | PASS |
| churn-40-20000-120 | nobudget | 59.36, 44.63, 56.84, 48.45, lost | 41.77 / 55.49 / lost / lost | 80 | 20 | **FAIL** |
| churn-40-100000-0 | head | 1.80, 3.10, 3.46, 0.28, 7.21 | 0.01 / 2.02 / 15.63 / 17.33 | 19 | 0 | **FAIL** |
| churn-40-100000-0 | base | 0.18, 0.63, 0.48 | 0.02 / 2.04 / lost / lost | 10 | 14 | **FAIL** |
| churn-40-100000-0 | narrow | 0.05, 0.06, 1.25, 0.05, 0.10 | 0.05 / 2.11 / lost / lost | 26 | 15 | **FAIL** |
| churn-40-100000-0 | nobudget | 0.13, 1.01, 0.14, 0.15, 0.11 | 0.01 / 0.02 / 1.02 / 1.04 | 0 | 0 | **FAIL** |
| churn-40-100000-5 | head | 8.69, 13.53, 34.23, 4.80, 1.89 | 0.01 / 13.83 / 39.66 / 44.78 | 66 | 0 | **FAIL** |
| churn-40-100000-5 | base | 0.18, 0.18, 0.34 | 0.02 / 4.02 / lost / lost | 17 | 7 | **FAIL** |
| churn-40-100000-5 | narrow | 0.23, 1.14, 0.10, 0.09, 0.71 | 0.07 / 2.11 / lost / lost | 32 | 12 | **FAIL** |
| churn-40-100000-5 | nobudget | 0.37, 1.06, 1.57, 0.97, 0.06 | 0.01 / 0.02 / 1.03 / 2.02 | 0 | 0 | **FAIL** |
| churn-40-100000-30 | head | 2.85, 6.23, 1.49, 3.34, 48.72 | 0.01 / 4.02 / 54.17 / 58.08 | 34 | 0 | **FAIL** |
| churn-40-100000-30 | base | 0.62, 0.78, 2.34 | 0.02 / 4.03 / lost / lost | 12 | 14 | **FAIL** |
| churn-40-100000-30 | narrow | 0.08, 0.08, 1.00, 0.54, 1.14 | 0.08 / 11.18 / lost / lost | 35 | 15 | **FAIL** |
| churn-40-100000-30 | nobudget | 1.86, 0.39, 1.42, 0.06, 0.37 | 0.01 / 0.03 / 2.02 / 2.04 | 0 | 0 | **FAIL** |
| churn-40-100000-120 | head | 2.88, 0.90, 6.77, 30.34, 2.79 | 0.01 / 4.01 / 35.80 / 40.69 | 38 | 0 | **FAIL** |
| churn-40-100000-120 | base | 0.93, 0.18, 0.18 | 0.02 / 4.03 / lost / lost | 17 | 8 | **FAIL** |
| churn-40-100000-120 | narrow | 0.99, 0.38, 0.69, 0.23, 1.04 | 0.07 / 2.11 / lost / lost | 23 | 10 | **FAIL** |
| churn-40-100000-120 | nobudget | 0.06, 1.07, 0.06, 0.67, 0.51 | 0.01 / 0.02 / 1.03 / 1.07 | 0 | 0 | **FAIL** |

What they say:

- **Head.** Every late item is a late first frame: of the 290 items sung after the first valid frame was heard, none was later than 27 ms, against
  345 of 800 missed over the cells. The delay is in getting the first one verified (below), not in what comes after.
- **Base** hears the first frame within a second in all but one of 24 runs, and at 100 000/s misses 156 of 240 items and loses 43: nothing protects a station that has
  been heard, so every later copy draws in the same lottery.
- **`narrow`** is base here, and its two failing cells at 20 000/s fail by one and two items (2.08-2.09 s). **`nobudget`** is
  its own finding, below.

## Gate 1: an established station is protected

#171's flood rows scaled down, with the tests' bounds: 57 of 57 during the flood, p50 at most 250 ms, none later than 4.5 s, the kernel's drops
reported. Pinned runtime; `established.json` ran before row 0, `nobudget-wake`'s rows after it.

| row | tree | runs | quiet items during the flood, per run, of 57 | latency ms over the runs: p50, max | offered /s | socket drops: kernel (reported) | refused, by reason (median) | checks that failed (median) | verdict |
|---|---|---|---|---|---|---|---|---|---|
| R1-valid-other-key | head | 5 | 57, 57, 57, 57, 57 | 10–10, 17–18 | 73,423–73,840 | 0 (0) | over_rate 995,298, backlog 1,780 | 0 | PASS (5 of 5 runs) |
| R1-valid-other-key | base | 3 | 0, 0, 0 | – | 76,879–77,649 | 1,040,268–1,050,812 (–) | – | 0 | **FAIL** (0 of 3 runs) |
| R1-valid-other-key | narrow | 5 | 0, 1, 0, 0, 1 | 857–5,546, 857–5,546 | 73,797–74,674 | 0 (0) | backlog 990,853 | 0 | **FAIL** (0 of 5 runs) |
| R1-valid-other-key | nobudget | 5 | 57, 57, 57, 57, 57 | 8–10, 16–20 | 72,531–73,942 | 0 (0) | over_rate 993,922, backlog 1,658 | 0 | PASS (5 of 5 runs) |
| R1-valid-other-key | nobudget-wake | 5 | 57, 57, 57, 57, 57 | 9–10, 18–20 | 72,412–73,456 | 0 (0) | over_rate 986,419, backlog 2,122 | 0 | PASS (5 of 5 runs) |
| R2-same-station | head | 5 | 57, 57, 57, 57, 57 | 9–11, 128–142 | 36,524–37,090 | 0 (0) | over_rate 498,023, backlog 797 | 0 | PASS (5 of 5 runs) |
| R2-same-station | base | 3 | 1, 2, 1 | 25–30, 25–2,401 | 37,934–38,203 | 512,564–516,203 (–) | – | 0 | **FAIL** (0 of 3 runs) |
| R2-same-station | narrow | 5 | 5, 4, 9, 4, 6 | 1,222–3,709, 1,640–6,048 | 36,747–37,774 | 0 (0) | backlog 495,395 | 0 | **FAIL** (0 of 5 runs) |
| R2-same-station | nobudget | 5 | 57, 57, 57, 57, 57 | 9–11, 128–145 | 36,479–37,032 | 0 (0) | over_rate 497,590, backlog 837 | 0 | PASS (5 of 5 runs) |
| R2-same-station | nobudget-wake | 5 | 57, 57, 57, 57, 57 | 10–12, 127–143 | 35,010–36,780 | 0 (0) | over_rate 491,007, backlog 832 | 0 | PASS (5 of 5 runs) |
| R3-forged-claiming-quiet | head | 5 | 57, 57, 57, 57, 57 | 19–20, 22–25 | 100,006–100,007 | 0 (0) | unverified 1,339,829, backlog 1,384 | 13,889 | PASS (5 of 5 runs) |
| R3-forged-claiming-quiet | base | 3 | 29, 41, 40 | 1,028–1,035, 4,035–4,039 | 100,006–100,007 | 1,128,949–1,130,560 (–) | – | 225,878 | **FAIL** (0 of 3 runs) |
| R3-forged-claiming-quiet | narrow | 5 | 25, 30, 28, 33, 28 | 1,090–2,094, 4,098–4,107 | 100,005–100,007 | 0 (0) | backlog 1,161,431 | 193,820 | **FAIL** (0 of 5 runs) |
| R3-forged-claiming-quiet | nobudget | 5 | 57, 57, 57, 57, 57 | 21–22, 25–28 | 100,006–100,007 | 0 (0) | backlog 1,183,842 | 171,258 | PASS (5 of 5 runs) |
| R3-forged-claiming-quiet | nobudget-wake | 5 | 57, 57, 57, 57, 57 | 21–22, 23–26 | 100,006–100,007 | 0 (0) | backlog 1,181,995 | 173,105 | PASS (5 of 5 runs) |
| R3c-forged-churned-sources | head | 5 | 57, 57, 57, 57, 57 | 20–21, 23–28 | 100,006–100,007 | 0 (0) | unverified 1,341,081, backlog 49 | 13,965 | PASS (5 of 5 runs) |
| R3c-forged-churned-sources | base | 3 | 29, 30, 22 | 1,029–1,043, 4,034–4,038 | 100,007 | 1,124,150–1,126,234 (–) | – | 229,500 | **FAIL** (0 of 3 runs) |
| R3c-forged-churned-sources | narrow | 5 | 30, 27, 26, 23, 31 | 1,081–1,121, 4,093–4,121 | 100,006–100,007 | 0 (0) | backlog 1,161,544 | 193,717 | **FAIL** (0 of 5 runs) |
| R3c-forged-churned-sources | nobudget | 5 | 57, 57, 57, 57, 57 | 24–26, 54–155 | 100,006–100,007 | 0 (0) | backlog 1,199,978 | 155,122 | PASS (5 of 5 runs) |
| R3c-forged-churned-sources | nobudget-wake | 5 | 57, 57, 57, 57, 57 | 22–24, 26–29 | 100,006–100,007 | 0 (0) | backlog 1,193,282 | 161,818 | PASS (5 of 5 runs) |
| R4-replay-own-frames | head | 5 | 57, 57, 57, 57, 57 | 18–19, 19–23 | 100,006 | 0 (0) | none | 0 | PASS (5 of 5 runs) |
| R4-replay-own-frames | base | 3 | 21, 30, 32 | 1,036–2,031, 4,036–4,038 | 100,006 | 1,148,055–1,149,277 (–) | – | 0 | **FAIL** (0 of 3 runs) |
| R4-replay-own-frames | narrow | 5 | 57, 57, 57, 57, 57 | 18–19, 19–21 | 100,006–100,007 | 0 (0) | none | 0 | PASS (5 of 5 runs) |
| R4-replay-own-frames | nobudget | 5 | 57, 57, 57, 57, 57 | 17–18, 19–21 | 100,006–100,007 | 0 (0) | none | 0 | PASS (5 of 5 runs) |
| R4-replay-own-frames | nobudget-wake | 5 | 57, 57, 57, 57, 57 | 17–19, 18–21 | 100,006 | 0 (0) | none | 0 | PASS (5 of 5 runs) |

At full length (#171's harness, 570 s for R rows, 300 s for F rows) the head's rows are not re-run here: its R rows are pass 2's, on identical daemon code (`e2d331d0`); its F rows are pass 1's, on an earlier `intake.py` (`0d8fafe4`). The
runtime is not recorded in any of those files. The candidates' are in "The split candidate".


## The recovery argument

The question: what bounds the time until a new legitimate source gets a verified frame, in a sustained churned flood? **Nothing in the
code does, at any rate above the strangers' budget.** What follows from it is a distribution, and the runs fit it. Line numbers are
`intake.py`'s at `ab61baf2`.

**Assumptions.** One listed key is flooded; its station is heard from no known source yet. Forgeries fail their check (one token each); a frame that verifies and is refused costs ten (`NO_OP_COST`, L87), so a flood of those makes *C* about 100/s. The flood sends *R* distinct forged frames a
second that reach the signature check, from a newly opened port each, on the newcomer's own host. A check costs 35 µs on ronan, so
a core does at most 28 000/s (`vbench.py`, see Limits); the loop around it made 12 500-17 800/s of the trees that spend what they can (base, `narrow`, `nobudget`, measured here). *C* is what the head spends on
strangers of a key.

1. **Where a copy goes.** `KeyQueue.source` (L271): the newcomer is not among the 4 known sources, which only a *verified* new frame
   opens (`know`, L301). The strangers' table takes 64 addresses, 16 a host (`_room`, L284), and is searched for idle places at most
   every 0.1 s (`RECLAIM_S`, L98); the flood's next 16 ports take what that frees. Everything else shares 64 lanes by a hash
   salted per run (L281). The newcomer keeps that lane while the stranger table is full (`source` looks again at each copy). The salt stops an attacker aiming at it. Filling all 64 needs no aim.
2. **Where it waits.** 256 datagrams a stream, for all strangers together (`STRANGER_POOL`, L96). Full, `put` (L176) places a
   copy only in a lane that has nothing waiting or is below its share (256 over at most 80 open lanes: 3), at the cost of the newest of the longest lane
   (`_shed`, L201). Otherwise it is refused. A place that a check frees goes to whichever stranger's datagram comes next.
3. **What is checked.** All strangers of a key pay from one bucket: 1 000 a second, 100 at once (`SOURCE_RATE`, L86; L265). The daemon's
   bucket for the checks of all keys is 2 000 a second (`CHECK_RATE`, L88). The key's streams with something waiting take turns, so a
   flood that keeps *m* of them full leaves *C/m* each. Here *m* = 2 (the stream's items and the beacons) and *R* is split evenly.
4. **Nothing in 1-3 tells the newcomer's copy from a forgery.** What is read before the signature is the key, stream, source, bytes and
   order of arrival, and the attacker writes all of them. Of *R* arrivals *C* are checked. So a copy that comes independently
   of the flood's timing is checked with chance **p = C/R**, and a refused one leaves nothing behind: the next starts over.
   With *n(t)* copies sent by *t*, **P(nothing heard by *t*) = (1 − C/R)ⁿ⁽ᵗ⁾**. That is positive for every *t* and goes to 1 as *R*
   grows: no deadline can be promised, and no number of runs would show one.
5. **After the first one it is over.** The source becomes known, has a queue and a budget of its own, and is served within 2 × `KNOWN_MAX`
   = 8 turns of its stream.

**It fits.** Copies sent until one was heard, on the head (`copies.py`, row 0 without offset 0, where the buckets' first 100 checks help; p with its 95 % interval):

| tree | flood | R, /s | runs | heard at all | copies sent before the first was heard, per run | p, estimated (95 %) | 1 in | C, checks/s that failed (median) | C/R | first frame > 1.0 s: seen |
|---|---|---|---|---|---|---|---|---|---|---|
| head | churn-40, offsets > 0, pooled | 20,000 | 15 | 15 | 4–45 | 5.2% (2.9%–8.4%) | 19 | 1,000 | 5.0% | 10 of 15 |
| head | churn-40, offsets > 0, pooled | 100,000 | 15 | 15 | 8–206 | 1.3% (0.7%–2.1%) | 77 | 1,000 | 1.0% | 14 of 15 |

*C/R* is inside the interval at both rates. (At 100 000/s the estimate is 1.3 % against 1.0 %, inside its interval. An even sender, row 1s, gives 1.0 %, where the paced ones send in bursts of a millisecond; five runs can't separate them.) The newcomer of these rows sends 8 or 9 copies in its first second, so *C/R* predicts a first frame later than 1.0 s in 63-66 % of the runs at 20 000/s and 91-92 % at 100 000/s. Seen: 10 of 15 and 14 of 15.

**A pass of the 1.0 s deadline in 99 % of runs would need p ≥ 40-44 %** (8 or 9 copies in the first second): C ≥ 8 000-8 800 checks/s against 20 000/s, and 40 000-44 000/s, three to four cores, against 100 000/s. At about 700 000/s
(fixed sources, what two producers of distinct forgeries reached in the flood rows) p would be 0.14 %, and 70 % of newcomers unheard after 64 s. That is the model's, not a measurement.

**And step 5 too** (`after_first.py`): on the head not one of the 290 items that were sung after the first valid frame was late, and the slowest took 27 ms. No head run with an on-time first frame missed an item. The missed items are late by the first frame's
delay, and, when a loop of the carousel has to bring the next copy, by its own time too (140 of the 345 were delivered more than 2 s after the first frame, up to 13.3 s).

| tree | R, /s | items sung before its first valid frame was heard | later than 2.0 s or lost | items sung after it | latency, s: median, max | later than 2.0 s or lost |
|---|---|---|---|---|---|---|
| head | 20,000 | 168 | 66 | 232 | 0.018, 0.024 | 0 |
| head | 100,000 | 342 | 279 | 58 | 0.012, 0.027 | 0 |
| base | 20,000 | 12 | 0 | 228 | 0.027, 4.032 | 4 |
| base | 100,000 | 56 | 37 | 184 | 2.039, lost | 119 |
| narrow | 20,000 | 21 | 0 | 379 | 0.076, 2.093 | 3 |
| narrow | 100,000 | 75 | 47 | 325 | 4.079, lost | 218 |
| nobudget | 20,000 | 265 | 216 | 135 | 0.379, 3.672 | 14 |
| nobudget | 100,000 | 90 | 13 | 310 | 0.023, 0.048 | 0 |

### What the code estimates, and its conditions

Not bounds: what one round of the lanes costs while the assumptions hold, of which none is the newcomer's. *m* is the number of the key's stream queues the flood keeps full (the listed stream, other, beacons: at most 3 here; the
flood of these rows fills 2).

| situation | estimate | from, and what it depends on |
|---|---|---|
| fewer than about 1 000/s of forgeries claim the key | 256 · m / 1 000 s: 0.5 s at *m* = 2 | the pool empties faster than it fills. Not measured here |
| the newcomer's host is not among the flood's, which comes from *h* ≤ 3 others | (16·*h* + 64 + 1) · *m* / 1 000 s + 20 ms: 0.18 s for one host, 0.25 s for three, at *m* = 2 (0.24 s and 0.36 s at *m* = 3) | it has a place of its own (`_room`), and its first copy is never the one shed (256 places over at most 113 lanes leave one with 3 or more). **Seen, row 1h: 0.155-0.185 s at the client, 3 of 10 above 0.18; one other host only.** Not in it: the kernel's drop of the copy, a spoofed address, replays (below), a flood of other listed keys |
| at most 15 other ports of its host claim the key | one round of the lanes | 16 places for 15 and it: `fixed-12` (12 ports) passes at 0.04-0.06 s |
| its first copy comes while the first 100 checks or the pool are unspent | none in general | offset 0. A station that starts when a flood does is lucky |
| a newcomer on the flood's host, or a flood from four hosts or more | **none: (1 − C/R)ⁿ** | this section |

A bound on *C* itself: 1 000/s is the key's, 2 000/s is the daemon's for all keys, so a flood over *k* ≥ 2 listed keys leaves less. Captured frames that verify and are refused cost ten tokens each (`NO_OP_COST`, L87), so a flood of them cuts *C* to about 100/s and every estimate above
grows tenfold. Not measured.

[`DESIGN-NOTE.md`](DESIGN-NOTE.md) says what mechanism would give one. It is input to the separate newcomer-recovery change, no part of #173.

## Saturation (row 1)

`churn-12`, `-40` and `-200` at offset 1 s, and three that ask what hid the rate in row 0 (PLAN.md): an evenly spaced sender (1s), 200 000/s from four producers (1r), and the newcomer on
another address than the flood's (1h). Each is one miss to fail.

| row (sources-ports-rate-offset) | head | base |
|---|---|---|
| churn-12-20000-1 | **FAIL**: worst first 2.81 s; first 4/5, items 24/100 | PASS: worst first 0.03 s; first 0/3, items 0/60 |
| churn-40-20000-1 | **FAIL**: worst first 1.45 s; first 1/5, items 2/100 | PASS: worst first 0.03 s; first 0/3, items 0/60 |
| churn-200-20000-1 | **FAIL**: worst first 2.10 s; first 3/5, items 6/100 | **FAIL**: worst first 0.33 s; first 0/3, items 1/60 |
| churn-12-100000-1 | **FAIL**: worst first lost; first 5/5, items 84/100 (lost 20, > 10 s 9) | **FAIL**: worst first 0.64 s; first 0/3, items 43/60 (lost 12, > 10 s 18) |
| churn-40-100000-1 | **FAIL**: worst first 11.51 s; first 5/5, items 69/100 (lost 0, > 10 s 34) | **FAIL**: worst first 0.64 s; first 0/3, items 42/60 (lost 10, > 10 s 20) |
| churn-200-100000-1 | **FAIL**: worst first 27.39 s; first 5/5, items 49/100 (lost 0, > 10 s 22) | **FAIL**: worst first 0.34 s; first 0/3, items 38/60 (lost 7, > 10 s 23) |
| churn-40-200000-1 | **FAIL**: worst first 30.34 s; first 5/5, items 79/100 (lost 0, > 10 s 40) | – |
| otherhost-40-20000-1 | PASS: worst first 0.18 s; first 0/5, items 0/100 | **FAIL**: worst first 0.18 s; first 0/3, items 1/60 |
| otherhost-40-100000-1 | PASS: worst first 0.19 s; first 0/5, items 0/100 | **FAIL**: worst first 1.03 s; first 2/3, items 36/60 (lost 5, > 10 s 21) |
| smooth-40-20000-1 | **FAIL**: worst first 3.24 s; first 1/5, items 15/100 | – |
| smooth-40-100000-1 | **FAIL**: worst first 40.04 s; first 5/5, items 90/100 (lost 0, > 10 s 63) | – |
| **cells passed** | **2 of 11** | **2 of 8** |

**There is no bound to give: #173's README says "unbounded" for a churned flood from the station's own host. The number of churned ports makes no difference these runs can show. A flat median is not a bound.**

Every row's full table (per-run first frames, the item distribution, drops, refusals, the flood's lowest second), for the rows here and for 0, 0c, 1c, 1h, 2 and 2w, is [`TABLES.md`](TABLES.md), generated by [`newcomer_table.py`](newcomer_table.py).

- **It grows from 20 000/s to 100 000/s, and the runs can't tell 100 000/s from 200 000/s.** The median first valid frame on the head is 1.0 s at 20 000/s (15 runs, worst 2.8 s, 8 later than 1.0 s), 3.6 s at 100 000/s (15 runs, all later
  than 1.0 s, one not heard in the 64 s) and 3.8 s at 200 000/s (5 runs, worst 30.3 s, all later than 1.0 s). The lottery says *C/R* is 5, 1 and 0.5 %, and the estimate of p at 200 000/s (1.3 %, 95 %: 0.4-3.1 %) is too wide to use.
  That is why the argument from the code decides this, not the medians.
- **The number of ports makes no difference** that these runs can show: 12, 40 and 200 sockets give medians of 1.6, 0.5 and 1.0 s at 20 000/s, and 3.6, 3.1 and 1.8 s at 100 000/s: no consistent order across the rates. It can't: every datagram comes from a port
  of its own, so *N* sets only how many sockets are open.
- **An even sender is not better.** At 100 000/s its median first frame is 13.6 s against 3.1 s for the burst cell, every run is late, and p is 1.0 % (0.3-2.2 %) against 1.8 %: the intervals overlap, so this doesn't show the bursts' silence helping. At 20 000/s it is 0.5 s, as the burst.
- **Row 1h, PASS at both rates, and close to the code's estimate.** The newcomer on 127.0.0.2, the flood from 127.0.0.1: first frames 0.155-0.185 s at 20 000/s and at 100 000/s alike, five runs each, every item on time. The estimate of one round of at most 16 + 64 + 1 lanes at 500 checks a second and
  a 20 ms retry is 0.18 s; three of the ten runs are above it, by up to 4 ms (the client's side of it). **It is an estimate for this flood from one host, not a bound**: see "What the code estimates". Base fails both cells of 1h (2 of 3 first frames late at 100 000/s).

## The companion reading: ports held open (rows 0c and 1c)

The companion reading (0c, 1c): N sockets held open and used in turn, `fixed-N`. Where the flood's ports are few, the outcome is in two parts, and it follows from the code.

| row (sources-ports-rate-offset) | head | base |
|---|---|---|
| fixed-12-20000-1 | PASS: worst first 0.06 s; first 0/5, items 0/100 | **FAIL**: worst first 0.03 s; first 0/3, items 1/60 |
| fixed-40-20000-0 | PASS: worst first 0.04 s; first 0/5, items 0/100 | **FAIL**: worst first 0.02 s; first 0/3, items 1/60 |
| fixed-40-20000-1 | **FAIL**: worst first 2.64 s; first 1/5, items 10/100 | **FAIL**: worst first 0.03 s; first 0/3, items 1/60 |
| fixed-40-20000-5 | **FAIL**: worst first 1.01 s; first 1/5, items 1/100 | PASS: worst first 0.33 s; first 0/3, items 0/60 |
| fixed-40-20000-30 | **FAIL**: worst first 13.75 s; first 1/5, items 20/100 (lost 0, > 10 s 20) | **FAIL**: worst first 0.03 s; first 0/3, items 1/60 |
| fixed-40-20000-120 | **FAIL**: worst first 1.54 s; first 1/5, items 4/100 | PASS: worst first 0.03 s; first 0/3, items 0/60 |
| fixed-200-20000-1 | **FAIL**: worst first 1.90 s; first 4/5, items 13/100 | PASS: worst first 0.03 s; first 0/3, items 0/60 |
| fixed-12-100000-1 | PASS: worst first 0.06 s; first 0/5, items 0/100 | **FAIL**: worst first 1.08 s; first 1/3, items 35/60 (lost 7, > 10 s 12) |
| fixed-40-100000-0 | PASS: worst first 0.42 s; first 0/5, items 0/100 | **FAIL**: worst first 1.03 s; first 1/3, items 39/60 (lost 12, > 10 s 16) |
| fixed-40-100000-1 | **FAIL**: worst first 49.62 s; first 3/5, items 41/100 (lost 0, > 10 s 20) | **FAIL**: worst first 0.78 s; first 0/3, items 38/60 (lost 9, > 10 s 17) |
| fixed-40-100000-5 | **FAIL**: worst first 2.94 s; first 2/5, items 23/100 | **FAIL**: worst first 1.08 s; first 1/3, items 34/60 (lost 6, > 10 s 14) |
| fixed-40-100000-30 | **FAIL**: worst first 13.36 s; first 1/5, items 20/100 (lost 0, > 10 s 20) | **FAIL**: worst first 0.49 s; first 0/3, items 35/60 (lost 9, > 10 s 14) |
| fixed-40-100000-120 | PASS: worst first 0.09 s; first 0/5, items 0/100 | **FAIL**: worst first 0.63 s; first 0/3, items 39/60 (lost 11, > 10 s 13) |
| fixed-200-100000-1 | **FAIL**: worst first 2.79 s; first 3/5, items 19/100 | **FAIL**: worst first 0.33 s; first 0/3, items 37/60 (lost 11, > 10 s 10) |
| **cells passed** | **5 of 14** | **3 of 14** |

- **12 ports: PASS at both rates**, first frames 0.04-0.06 s. The flood's 12 ports and the newcomer's one are within the 16 places a host has, so it queues apart.
- **40 ports: FAIL in 7 of 10 cells, by the hash's chance.** 16 ports take the host's places and 24 share the 64 lanes; the newcomer's own lane is shared with at least one of them in 1 − (63/64)²⁴ = 31 % of runs. Of the 40 head runs (offset > 0 of row 0c
  and row 1c) 11 had a first frame above 0.2 s, up to 49.6 s, and 10 of them above the 1.0 s deadline. The others came in 0.07-0.11 s. *A first frame of 0.1 s or of 50 s is what a run gets, and neither is the cell's.*
- **200 ports: FAIL** (7 of 10 first frames above 1.0 s, 0.55-2.8 s). 184 ports share 64 lanes, so only one newcomer in 18 has a lane to itself ((63/64)¹⁸⁴ = 5.5 %).
- **Base fails 11 of 14 cells**, nearly all by its items; its first frame came within 1.1 s.

## The model (row 1m)

[`newcomer_model.py`](newcomer_model.py) runs the head's `Intake` in virtual time: no sockets, no signatures, no loop. It is a check of the reading of the code, and no measurement; a copy is counted as verified if the newcomer's own copy reaches a ticket. Four seeds a line, 20 s, [`results/model-head.md`](results/model-head.md):

 flood | arrives | R, /s | copies sent | copies verified | share | C/R with C = 1 000/s 
---|---|---|---|---|---|---
 churn | smooth | 5,000 | 721 | 208 | 28.8% (17%, 36%, 23%, 38%) | 20.0% 
 churn | smooth | 20,000 | 684 | 29 | 4.2% (2%, 2%, 4%, 9%) | 5.0% 
 churn | smooth | 50,000 | 710 | 29 | 4.1% (2%, 3%, 12%, 1%) | 2.0% 
 churn | smooth | 100,000 | 722 | 3 | 0.4% (0%, 0%, 0%, 1%) | 1.0% 
 churn | smooth | 200,000 | 710 | 0 | 0.0% (0%, 0%, 0%, 0%) | 0.5% 
 churn | smooth | 400,000 | 717 | 0 | 0.0% (0%, 0%, 0%, 0%) | 0.2% 
 churn | once a ms | 5,000 | 736 | 273 | 37.1% (53%, 31%, 29%, 34%) | 20.0% 
 churn | once a ms | 20,000 | 727 | 170 | 23.4% (21%, 32%, 20%, 19%) | 5.0% 
 churn | once a ms | 50,000 | 689 | 135 | 19.6% (20%, 17%, 24%, 18%) | 2.0% 
 churn | once a ms | 100,000 | 733 | 147 | 20.1% (15%, 18%, 15%, 33%) | 1.0% 
 churn | once a ms | 200,000 | 753 | 106 | 14.1% (14%, 11%, 13%, 18%) | 0.5% 
 churn | once a ms | 400,000 | 689 | 101 | 14.7% (13%, 16%, 13%, 17%) | 0.2% 

- **Even arrivals, churned:** 4.2 % at 20 000/s (*C/R* 5.0 %) and 0.4 % at 100 000/s (1.0 %); at 200 000/s and 400 000/s none of 1 427 copies was verified (*C/R* 0.5 and 0.2 %). Within what four seeds show at 20 000/s; at 50 000/s it is above *C/R* (4.1 % against 2.0) and at 200 000/s below. The lottery is the shape of it, and it does not stop at any rate.
- **Arrivals once a millisecond (a burst, as the producers pace): 14-37 %**, far above *C/R* and above the runs (1.3 % at 100 000/s). The measured datagrams do not reach the reader as the model's bursts do (an arrival in the silence of an idle millisecond, the newcomer's copy before the burst in half the cases), so this line is **not** relied on for anything; it says the runs are nearer the even arrival than the burst.
- **Fixed ports:** 40 ports, 1-42 % or 99-100 % of copies by seed, as the runs' bimodality and the hash say; 200 ports, 6-53 % by rate, all lanes shared. A share, not a bound.

## Attribution (rows 2 and 2w)

Five toggles of the head, each a patch to its daemon committed before its run, at offset 1 s; five runs each, the head beside them (row 1's
`churn-40` cells). `a` both halves of (a) off; `a-lanes` the per-source lanes; `a-budgets` the two budgets for checks that come to nothing; `b` the key and stream
round-robin; `c` debit-after-verify (a claim spends its key's and stream's buckets).

| row | tree | first valid frame, s, per run | first-frame misses | item latency, s: min / median / p95 / max | item misses | > 10 s late | lost | checks that failed, /s (median) | verdict |
|---|---|---|---|---|---|---|---|---|---|
| churn-40-20000-1 | head | 0.49, 1.45, 0.17, 0.48, 0.73 | 1 of 5 | 0.01 / 0.02 / 1.02 / 2.02 | 2 of 100 | 0 | 0 | 1,001 | **FAIL** |
| churn-40-20000-1 | a | 0.05, 0.05, 0.05, 0.05, 0.05 | 0 of 5 | 0.04 / 0.05 / 1.05 / 2.05 | 3 of 100 | 0 | 0 | 16,762 | **FAIL** |
| churn-40-20000-1 | a-lanes | 0.53, 3.12, 0.86, 0.83, 2.29 | 2 of 5 | 0.51 / 47.93 / lost / lost | 80 of 100 | 23 | 42 | 1,001 | **FAIL** |
| churn-40-20000-1 | a-budgets | 2.18, 1.12, 1.59, 2.37, 0.37 | 4 of 5 | 0.04 / 0.82 / 2.50 / 3.13 | 14 of 100 | 0 | 0 | 15,780 | **FAIL** |
| churn-40-20000-1 | b | 1.09, 0.24, 0.55, 1.09, 1.23 | 3 of 5 | 0.01 / 0.02 / 1.03 / 2.02 | 2 of 100 | 0 | 0 | 998 | **FAIL** |
| churn-40-20000-1 | c | 35.69, 21.36, 53.60, 25.77, lost | 5 of 5 | 19.86 / 38.77 / lost / lost | 100 of 100 | 77 | 23 | 20 | **FAIL** |
| churn-40-100000-1 | head | 1.68, 11.51, 3.10, 6.12, 2.46 | 5 of 5 | 0.01 / 4.01 / 16.47 / 20.44 | 69 of 100 | 34 | 0 | 1,001 | **FAIL** |
| churn-40-100000-1 | a | 1.21, 0.81, 0.65, 0.20, 0.05 | 1 of 5 | 0.04 / 12.45 / lost / lost | 74 of 100 | 30 | 23 | 14,191 | **FAIL** |
| churn-40-100000-1 | a-lanes | 1.28, 2.90, 1.59, 2.18, 2.64 | 5 of 5 | 0.52 / lost / lost / lost | 93 of 100 | 17 | 71 | 1,002 | **FAIL** |
| churn-40-100000-1 | a-budgets | 0.07, 0.51, 0.97, 0.06, 1.03 | 1 of 5 | 0.01 / 0.02 / 1.02 / 2.02 | 1 of 100 | 0 | 0 | 12,727 | **FAIL** |
| churn-40-100000-1 | b | 54.62, 6.04, 20.64, 1.25, 2.84 | 5 of 5 | 0.01 / 12.27 / lost / lost | 74 of 100 | 46 | 7 | 998 | **FAIL** |
| churn-40-100000-1 | c | lost, 56.86, lost, lost, lost | 5 of 5 | 55.33 / lost / lost / lost | 100 of 100 | 9 | 91 | 21 | **FAIL** |

- **The runs are consistent with the budget half of (a) causing the delay.** Every tree that keeps the budgets checks 1 000 strangers' datagrams a second (column "checks that failed"; `c` 20, of `STREAM_RATE` 12 and `BEACON_RATE` 8), every one that
  lifts them 12 500-17 000. The newcomer's chance of being checked moves with it: `a`'s first frame is 0.05 s at 20 000/s in every run and at 100 000/s late in 1 of 5
  (head: 1 and 5 of 5), though `a` loses items later, because nothing protects a station that has been heard. What is not separated: `a-budgets` with the wake collapsed (2w) changes two things, and "the head plus the wake" alone was not run (the head posts 81 turns in 3 s, so it has nothing to collapse).
- **No other toggle passes, and lanes off and debit-after-verify off are far worse**: 113 and 114 of 200 items lost (`c`'s claims spend the stream's and beacon's buckets). `b` (key and stream round-robin off) can't be separated from the head with 5 runs: at 100 000/s its median first frame is 6.0 s against 3.1, worst 54.6 against 11.5,
  and 7 items lost against 0. There is no evidence that it helps.
- **No toggle passes a cell.** `a-budgets` at 20 000/s is worse than `a`, with about the same checks: the second defect (next section). At 100 000/s it misses one of five first frames and one item of 100, and `nobudget-wake` still fails 2 of 4 cells there: that is the lottery, not the defect.
- **The earlier attribution is withdrawn.** The provisional one (02:09Z, on cryptography 41.0.7) said that lifting only the budgets gives no miss in ten runs at
  offset 1 s. On the pinned runtime it misses 4 of 5 first frames at 20 000/s and 1 of 5 at 100 000/s. Those runs led to `nobudget` as a candidate (PLAN.md) and feed no verdict.

`nobudget-wake` (2w) is `a-budgets` with the reader's wake collapsed, on row 0's eight cells. It is a diagnostic of whether the budgets own the delay at
every offset, **not a candidate**: it decides no gate, and spends more than a core.

| row (sources-ports-rate-offset) | head | nobudget | nobudget-wake |
|---|---|---|---|
| churn-40-20000-0 | PASS: worst first 0.04 s; first 0/5, items 0/100 | PASS: worst first 0.16 s; first 0/5, items 0/100 | PASS: worst first 0.03 s; first 0/5, items 0/100 |
| churn-40-20000-5 | **FAIL**: worst first 1.78 s; first 2/5, items 7/100 | **FAIL**: worst first 3.74 s; first 4/5, items 30/100 | PASS: worst first 0.07 s; first 0/5, items 0/100 |
| churn-40-20000-30 | **FAIL**: worst first 3.05 s; first 4/5, items 35/100 | **FAIL**: worst first 18.66 s; first 5/5, items 100/100 (lost 0, > 10 s 60) | PASS: worst first 0.05 s; first 0/5, items 0/100 |
| churn-40-20000-120 | **FAIL**: worst first 3.04 s; first 4/5, items 24/100 | **FAIL**: worst first lost; first 5/5, items 100/100 (lost 20, > 10 s 80) | PASS: worst first 0.05 s; first 0/5, items 0/100 |
| churn-40-100000-0 | **FAIL**: worst first 7.21 s; first 4/5, items 57/100 (lost 0, > 10 s 19) | **FAIL**: worst first 1.01 s; first 1/5, items 0/100 | PASS: worst first 0.52 s; first 0/5, items 0/100 |
| churn-40-100000-5 | **FAIL**: worst first 34.23 s; first 5/5, items 86/100 (lost 0, > 10 s 66) | **FAIL**: worst first 1.57 s; first 2/5, items 4/100 | **FAIL**: worst first 1.12 s; first 1/5, items 1/100 |
| churn-40-100000-30 | **FAIL**: worst first 48.72 s; first 5/5, items 71/100 (lost 0, > 10 s 34) | **FAIL**: worst first 1.86 s; first 2/5, items 9/100 | PASS: worst first 0.96 s; first 0/5, items 0/100 |
| churn-40-100000-120 | **FAIL**: worst first 30.34 s; first 4/5, items 65/100 (lost 0, > 10 s 38) | **FAIL**: worst first 1.07 s; first 1/5, items 0/100 | **FAIL**: worst first 1.42 s; first 2/5, items 4/100 |
| **cells passed** | **1 of 8** | **1 of 8** | **6 of 8** |

- **It passes all four cells at 20 000/s, and at 100 000/s two of four.** The delay at the offsets 0, 5, 30 and 120 s moves with the budgets, not only at 1 s. The chance per copy with the budgets lifted, beside the head's (`copies.py`):

| tree | flood | R, /s | runs | heard at all | copies sent before the first was heard, per run | p, estimated (95 %) | 1 in | C, checks/s that failed (median) | C/R | first frame > 1.0 s: seen |
|---|---|---|---|---|---|---|---|---|---|---|
| head | churn-40, offsets > 0, pooled | 20,000 | 15 | 15 | 4–45 | 5.2% (2.9%–8.4%) | 19 | 1,000 | 5.0% | 10 of 15 |
| head | churn-40, offsets > 0, pooled | 100,000 | 15 | 15 | 8–206 | 1.3% (0.7%–2.1%) | 77 | 1,000 | 1.0% | 14 of 15 |
| nobudget-wake | churn-40, offsets > 0, pooled | 20,000 | 15 | 15 | 2–2 | 50.0% (31.3%–68.7%) | 2 | 16,010 | 80.1% | 0 of 15 |
| nobudget-wake | churn-40, offsets > 0, pooled | 100,000 | 15 | 15 | 2–15 | 16.1% (9.3%–25.2%) | 6 | 12,839 | 12.8% | 3 of 15 |

- **At 100 000/s *C/R* is inside p's interval for both the head's and `nobudget-wake`'s *C*** (1 000/s and 13 000/s): the lottery is consistent with both. It is not at 20 000/s: *C/R* = 80 % is outside p's 31-69 %, where every newcomer of `nobudget-wake` is first heard after two copies had been
  sent, which is a counting limit and says nothing either way.
- **It bounds nothing**, and its gate 1 rows pass 25 of 25 (above).

## Finding: `nobudget` publishes late, in proportion to the flood's age

The second candidate, `nobudget`, is the head with the two budgets lifted and nothing else. At 20 000/s its first valid frame came 0.12, 1.8, 16.4 and 56.8 s after its send at
offsets 0, 5, 30 and 120 s (medians of 5 runs; the fifth run at 120 s was not heard in 64 s at all, and that newcomer lost all 20 items). **At 20 000/s the delay grows with the age of the flood.** It does not at 100 000/s (medians 0.14, 0.97, 0.39 and 0.51 s at offsets 0, 5, 30 and 120): the pool stays full there, so few batches open a lane (not measured as the reason). Found by pass 3b; row 2w (above) carries the confirmation.

- **It was verified, and published late.** In all 20 of its 20 000/s runs the daemon's own counts cover every copy the newcomer sent, to the last one in flight: 84-85 verified and 160-162 exact repeats of the 245-247 sent, in the run where the client read nothing too. Those are end-of-run totals, so they place no copy in time; that each
  first copy is verified before its +1 s repeat is, is what 160-162 repeats of 84-85 items mean. The kernel dropped nothing at the socket.
- **Cause, read from the code.** `Intake.offer` (`intake.py` L559) calls `wake` once **for every batch that opens a lane** (L588-589); `wake` is `call_soon_threadsafe`
  (`daemon.py` L440, L535-537), and posts don't collapse. Every posted turn is `_hear_queued`, up to 32 checks (`HEAR_BATCH`), about 2 ms at 16 000/s. A record wakes its connection's writer by appending it behind everything posted
  before (`asyncio`'s `_ready`), and the loop runs them in order. With no budget a turn is never empty, so the queue grows with the flood's age.
- **Counted** (`wakes.py`, the trees' own `Intake` in virtual time, 3 s at 20 000/s): `nobudget` posts 3 000 turns and a loop of 1.6 ms turns runs 1 875; the head posts about 80, `narrow` 375 ([`results/wakes.txt`](results/wakes.txt); its own rng moves the head's count between 80 and 83). The head's budgets keep its turns
  cheap and its lanes full, so nothing piles up.
- **Confirmed by 2w, at 20 000/s.** One change, the wake collapsed to one posted turn at a time ([`toggles/a-budgets-wake.patch`](toggles/a-budgets-wake.patch)), takes it from 1 of 8 cells to 6 of 8: first frames 0.02-0.07 s at every offset at 20 000/s (the two cells it still fails are at 100 000/s).
- **In the head it is latent, not seen.** Nothing measured there shows it. It needs turns that cost more than the reader takes to post another, which the budgets prevent.
  Any change that gives strangers more checks (design note, D) has to collapse the wake first. **It is reported here, not fixed:** no code of #173 or of `narrow` changed in this pass.

## The split candidate

The split was to be taken only if attribution supported it. What it asked for is the parts that don't cause the delay: the fast drain, the exact-repeat check before verify,
the kernel's drop count, the accounting, and one durable save per turn. `narrow` (`codeagent/bc-173-narrow`, `f8a91c1f`, one commit over `main`) is those, with their tests
(`test_intake.py`, `test_intake_floods.py`). The repo's own CI on it, hosted: run 45338423871, all four jobs (station, harness, and plugin on Node 24 and 26).
Its negative control and its patch-reverts are in the commit message. No PR was opened.

- **What it does:** every datagram is read, exact repeats cost nothing, and every loss is counted and reported. It answers R4 (replays of the quiet station's own frames): 57 of 57 in 5 of 5 scaled runs, as the head and unlike base.
- **What it doesn't:** it protects nobody. Gate 1's R1, R2, R3 and R3c fail on it as on base (0-33 of 57, in no run 57). Gate 2 fails 6 of 8, and at 20 000/s its two failures are 1 and 2 items of 100 at 2.08-2.09 s.
- **So attribution supports the split only as a split, not as a landing.** The separable part is accounting without protection. The part that protects (gate 1) is the scheduling, and the delay (gate 2) is in the budgets that go with it.
  Neither passes both gates. The PR stays held, and the newcomer-recovery change ([`DESIGN-NOTE.md`](DESIGN-NOTE.md)) is what would move it.
- **The rest of #171's suite, pass 2's scaled rows** (5 runs each, the head beside them, by pass 2's own bounds, which are 4.5 s and not pass 3's deadline):

| row | head | narrow | nobudget |
|---|---|---|---|
| spoof-exact-source-100000 | **FAIL** (outside the supported guarantee); 5, 1, 3, 3, 3 of 20; max 4,089 ms | **FAIL** (outside the supported guarantee); 8, 8, 10, 10, 12 of 20; max 4,106 ms | **FAIL** (outside the supported guarantee); 8, 7, 7, 5, 12 of 20; max 4,033 ms |
| spoof-exact-source-500 | PASS; 20, 20, 20, 20, 20 of 20; max 30 ms | PASS; 20, 20, 20, 20, 20 of 20; max 30 ms | PASS; 20, 20, 20, 20, 20 of 20; max 32 ms |
| churn-established-100000 | PASS; 57, 57, 57, 57, 57 of 57; max 40 ms | **FAIL**; 24, 30, 33, 31, 27 of 57; max 4,122 ms | PASS; 57, 57, 57, 57, 57 of 57; max 130 ms |
| relay-first-then-churn-100000 | **FAIL** (outside the supported guarantee); 15, 20, 2, 20, 20 of 20; max 16,761 ms | **FAIL** (outside the supported guarantee); 14, 13, 14, 15, 9 of 20; max 17,216 ms | **FAIL** (outside the supported guarantee); 20, 20, 20, 20, 20 of 20; max 2,046 ms |
| relay-after-then-churn-100000 | PASS; 20, 20, 20, 20, 20 of 20; max 38 ms | **FAIL**; 13, 9, 10, 18, 13 of 20; max 17,189 ms | PASS; 20, 20, 20, 20, 20 of 20; max 78 ms |
| cold-start-12-ports-20000 | PASS; 20, 20, 20, 20, 20 of 20; max 44 ms; first 30-55 ms | PASS; 20, 20, 20, 20, 20 of 20; max 4,085 ms; first 79-87 ms | PASS; 20, 20, 20, 20, 20 of 20; max 25 ms; first 29-33 ms |
| cold-start-40-ports-20000 | **FAIL**; 20, 20, 20, 20, 20 of 20; max 2,019 ms; first 84-1,754 ms | PASS; 20, 20, 20, 20, 20 of 20; max 2,091 ms; first 67-81 ms | PASS; 20, 20, 20, 20, 20 of 20; max 1,023 ms; first 28-223 ms |
| cold-start-200-ports-20000 | **FAIL**; 20, 20, 20, 20, 20 of 20; max 2,018 ms; first 836-1,454 ms | PASS; 20, 20, 20, 20, 20 of 20; max 2,085 ms; first 72-90 ms | **FAIL**; 20, 20, 20, 20, 20 of 20; max 5,312 ms; first 4,532-5,323 ms |
| cold-start-churn-own-host-20000 | **FAIL**; 20, 20, 20, 20, 20 of 20; max 4,024 ms; first 170-3,520 ms | PASS; 20, 20, 20, 20, 20 of 20; max 1,081 ms; first 65-79 ms | **FAIL**; 20, 20, 20, 20, 20 of 20; max 2,760 ms; first 566-2,085 ms |
| cold-start-churn-60000-hosts-20000 | **FAIL**; 20, 20, 20, 20, 20 of 20; max 17,336 ms; first 1,781-6,974 ms | PASS; 20, 20, 20, 20, 20 of 20; max 2,085 ms; first 75-77 ms | **FAIL**; 20, 20, 20, 20, 20 of 20; max 4,631 ms; first 2,309-3,436 ms |

  `narrow` fails the established rows of the churned flood (24-33 of 57) and both relay rows; it passes the five cold starts by the 4.5 s bound (first frame 65-90 ms, items up to 4.1 s; base's items arrive in pass 2's runs too, but its drops are not reported, so those rows are FAIL there).
  `nobudget` passes the established rows, and gets every item of the relays (20 of 20 in all runs; relay-first is a FAIL on its p50, 1.0 s in 2 of 5 runs), and fails three cold starts. The exact-source spoof is a FAIL for all three, outside the guarantee. The head fails four of five
  cold starts here, 40 fixed ports (a lane shared by chance, above) among them, where pass 2's five runs passed.
- **Full length** (#171's harness, 570 s for R rows, 300 s for F rows): judged by 🌫's comparator (at the daemon within 4.5 s during the flood, the kernel's drops reported, and pushed to the ear). One run of each, then four more of every row whose first run passed (PLAN.md): a first-run failure decides its row. 82 runs, 0 INVALID; the 75 passing ones and the 7 failing ones are the comparator's.

| row | narrow | nobudget |
|---|---|---|
| R1-valid-other-key-4x-max | **FAIL**: 0 of 1 runs; on time 0 of 57 | PASS: 5 of 5 runs; on time 57 of 57, 57 of 57, 57 of 57, 57 of 57, 57 of 57 |
| R2-same-station | **FAIL**: 0 of 1 runs; on time 3 of 57 | PASS: 5 of 5 runs; on time 57 of 57, 57 of 57, 57 of 57, 57 of 57, 57 of 57 |
| R3-forged-claiming-quiet-2x-max | **FAIL**: 0 of 1 runs; on time 3 of 57 | PASS: 5 of 5 runs; on time 57 of 57, 57 of 57, 57 of 57, 57 of 57, 57 of 57 |
| R3c-forged-churned-sources-2x-max | **FAIL**: 0 of 1 runs; on time 21 of 57 | PASS: 5 of 5 runs; on time 57 of 57, 57 of 57, 57 of 57, 57 of 57, 57 of 57 |
| R4a-replay-earlier-frames-2x-max | PASS: 5 of 5 runs; on time 57 of 57, 57 of 57, 57 of 57, 57 of 57, 57 of 57 | **FAIL**: 0 of 1 runs; on time 11 of 57 |
| R4b-replay-latest-item-2x-max | PASS: 5 of 5 runs; on time 57 of 57, 57 of 57, 57 of 57, 57 of 57, 57 of 57 | PASS: 5 of 5 runs; on time 57 of 57, 57 of 57, 57 of 57, 57 of 57, 57 of 57 |
| F0-quiet-only | PASS: 5 of 5 runs; on time 30 of 30, 30 of 30, 30 of 30, 30 of 30, 30 of 30 | PASS: 5 of 5 runs; on time 30 of 30, 30 of 30, 30 of 30, 30 of 30, 30 of 30 |
| F2b-forged-own-key-2x-max | PASS: 5 of 5 runs; on time 30 of 30, 30 of 30, 30 of 30, 30 of 30, 30 of 30 | PASS: 5 of 5 runs; on time 30 of 30, 30 of 30, 30 of 30, 30 of 30, 30 of 30 |
| F3b-unknown-key-2x-max | **FAIL**: 0 of 1 runs; on time 25 of 30 | PASS: 5 of 5 runs; on time 30 of 30, 30 of 30, 30 of 30, 30 of 30, 30 of 30 |
| F4-replay-other-key-2x-max | PASS: 5 of 5 runs; on time 30 of 30, 30 of 30, 30 of 30, 30 of 30, 30 of 30 | PASS: 5 of 5 runs; on time 30 of 30, 30 of 30, 30 of 30, 30 of 30, 30 of 30 |
| F5-real-station-flood | **FAIL**: 0 of 1 runs; on time 3 of 30 | PASS: 5 of 5 runs; on time 30 of 30, 30 of 30, 30 of 30, 30 of 30, 30 of 30 |
| **rows passed** | **5 of 11** | **10 of 11** |

  `narrow` fails R1, R2, R3, R3c, F3b and F5; it answers the replays (R4a, R4b, F4) and the quiet and forged-own rows (F0, F2b). **`nobudget` fails R4a at full length, which the head passed in pass 2** (11 of 57 on time; 46 late, by up to 132 s, 11 of them only after the flood ended; 26 of 57 pushed; the kernel dropped 156 817 and said so; daemon CPU 142 % mean, the head's 104 %): without the budgets the replays of old beacons are checked
  and served at the loop's speed (4.8 M replays verified of 409 M read, 145 M repeats and 173 M copies). That the wake's backlog is the reason is a hypothesis: `nobudget-wake` has no full-length run. So `nobudget` fails gate 1 at full length (R4a), though it passes the scaled rows, and gate 2 as above.


## 🌫's comparator

[`comparator/oracle.py`](comparator/oracle.py) and its 17 tests are 🌫's (#173, issuecomment-7119143235), verbatim; [`judge_rows.py`](comparator/judge_rows.py) feeds it these runs. The 20 items of PLAN.md are the denominator
(never what was admitted). A run on another cryptography, or whose flood fell under 95 % of its rate in its lowest whole second, is INVALID; none was. The two thresholds are judged
apart, first frame (1.0 s) and items (2.0 s), and the flood must cover every deadline. **It and the harness give the same verdict in all 97 cells** of the newcomer rows (0 INVALID), by `comparator/judge_rows.py`.

`established_rows.py` and `scaled_rows.py` keep counts and percentiles per run, not items, so it can't judge them: they are gated on their 57-of-57 counts and their maximum, as PLAN.md declares.

## Limits

- **One host, one loopback.** The producers' pace is a millisecond burst with silence between; row 1s asks what an even sender does. The figures for a LAN, a 1 Gbit interface or a 212 992 B `rmem_max` host are not here.
- **It is a lottery measured with 3-5 runs a cell.** Two cells at the same rate can differ by a factor of ten by luck alone (`copies.py`'s intervals). A PASS is a run of luck too: nothing in it is a bound.
- **Nothing is called superseded.** A late item may still be current: an unchanged item is, and a carousel repeat doesn't prove supersession.
- **A shared host.** The newcomer rows record the load before each run, at most 6.5 on 20 cores (`established*.json` and `scaled-*.json` don't). `wakes.py` (one process, about ten seconds, counting only) ran beside run 0 of `smooth-40-100000-1`, and this lane's table scripts (seconds of one core each) beside rows from 06:10Z on. No measurement ran beside another.
- **`established.json`'s R1-R4 are the tests' scale** (13.6 s; offered 73-77 000/s in R1 and 35-38 000/s in R2, 100 000/s in the others), not #171's 570 s.
- **PLAN.md's addenda were edited after they were written** (2723c45 → d75cd98 changed a count, a5a897a and fc0c103 corrected times), not the predeclared body and not after a run whose row they changed; git has every version.
- **35 µs a check (a bad signature, 34.9 µs; 39.3 µs for a good one) and 28 000/s a core** are `vbench.py`'s, [`results/vbench.txt`](results/vbench.txt), measured alone after the queue.

## Rerun

```sh
# a tree is a git archive of prototype/canticle-station; the toggles are patches over ab61baf2
cd reports/measurement/2026-11-23-cold-start-recovery
nice -n 19 ionice -c3 python newcomer_rows.py out.json head=/scratch/head/prototype/canticle-station:5 churn-40-20000-30   # alone on the host
python newcomer_table.py out.json; python verdict_table.py out.json head; python copies.py out.json head; python after_first.py out.json
cd comparator && python -m unittest test_oracle && python judge_rows.py ../results/recovery-churn.json
```
`cryptography` must be 50.0.1 (`.github/ci/requirements-station.txt`); the rows refuse any other.
