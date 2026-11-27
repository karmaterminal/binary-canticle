# Newcomer recovery: what was measured, on what, and the verdict

[PLAN.md](PLAN.md) declared every row, bar, bound and change of method before it ran; [TABLES.md](TABLES.md) is generated from the raw files by
`make_tables.sh`. This file reads them. Nothing here replaces a table; where they differ, the table is right.

## The trees

| name | commit | what it is | raw |
|---|---|---|---|
| `fix` | `91d36c608bda8c6efa9f0c602366fdf3491a40ce` (intake.py as `dfa0414`) | this change as it would merge: the slice, the lease, the kept turns, and 🍃's re-tier rule at `72db59f`'s reader cost | results-3/ |
| `new` | `72db59fafb92b9630e1524e0e08b99a21cdda81f` | the same without the re-tier rule (`8495138` dropped it unsaid) | results-2/ |
| `slice` | `d49645b3fb75b46497e3049cbe65424a6c690e34` | the first form: re-tiers, but its reader was outrun in E2 | results/ |
| `base` | `966857bb070a1973e6974d56ed1dd37dcd9409b7` | #173's head `a0862c3` with 🕯's #177 `0f55b1d`, nothing else | results/ |
| `head` | `a0862c3eeb0b84236661451ca5c3d00127536d27` | #173's head (row J only) | results/ |

Every run: ronan, loopback, throwaway keys, `nice -n 19 ionice -c3`, cryptography 50.0.1, one measurement at a time.

## Verdict, on `fix`

| gate | row | `fix` | `new` | `base` |
|---|---|---|---|---|
| established stations | E1 (#171's rows, scaled) | 25 of 25 runs, 57 of 57 | 25 of 25 | 15 of 15 |
| | E2 (#171's rows at full length) | **35 of 35 PASS**: 57 of 57 in every R row of 5 of 5 runs, 30 of 30 in the F rows | 35 of 35 | (not run) |
| | J, J-all (junk and forgeries) | 4 of 4 cells, 20 valid runs | 4 of 4 (one completed) | 4 of 4 (`head` too) |
| | E3 `churn-established-100000` | 57 of 57 in 5 of 5 | the same | the same |
| the guarantee (newcomers) | N1, other keys forged, churned on the newcomer's host (B1) | **8 of 8 cells**, 0 misses | 8 of 8 | 8 of 8 |
| | N1c, the same from 40 ports held open | **8 of 8**, 0 misses | 8 of 8 | 8 of 8 |
| | N0c, its own key from 40 ports held open (B2) | **8 of 8**, 0 misses | 8 of 8 | 4 of 8, 85 misses |
| | N2, every key from 40 ports held open | **2 of 2**, 0 misses | 2 of 2 | 1 of 2, 21 misses |
| | I-a, relays known first, then the station | 5 of 5 | 5 of 5 | 0 of 3 |
| | I-b, a stopped incumbent replaying one beacon | 5 of 5, its lease ended 60.06-60.24 s after | 5 of 5 | 0 of 3 |
| | E3 cold start, 12, 40 and 200 ports | pass | pass | 40 and 200 fail |
| **pass 3's bar** | **N0, its own key, churned** | **1 of 8 cells: 266 misses** (27 first frames late, 239 items late, 0 missing; worst first frame 32.0 s) | 1 of 8: 281 | 1 of 8: 204 (3 runs a cell) |
| #177 (🕯's `0f55b1d`, merged as it is) | W: the check budgets lifted, on `a0862c3` with and without it (results/) | with it 2 of 2 cells, 10 of 10 runs, first frame ≤ 0.07 s | | without it 0 of 2: 22 s late, or 40 of 60 items lost |
| outside the guarantee, every tree | I-a′ (relay-first), E3 `relay-first-then-churn`, `spoof-exact-source-100000`, `cold-start-churn-*` | fail | fail | fail |

A cell is judged by 🌫's comparator, hardened: a run whose flood fell under 95 % of its rate in its lowest whole second is INVALID, stays in
the table, and its cell was completed with more runs (at most twice as many) until it had its five valid ones; a deadline missed in an
INVALID run would fail its cell too. Every `fix`, `new` and `base` cell is complete. `slice`'s cells with underdriven runs stay INVALID:
`d49645b` was superseded before they were completed.

**So:** the per-key guarantee holds on `fix`, every row of it, with the established stations' gates. **The bar as pass 3 declared it is not met**:
a churned flood of the newcomer's own key is still a lottery on every tree (N0: a copy is heard with p ≈ 7.2 % at 20 000/s and 2.2 % at 100 000/s,
pooled over the offsets after 0; `new` 6.5 % and 2.4 %; C/R is 7.5 % and 1.5 %). That is the honest limit the design states, and the room's answer (A) puts it outside.

## The bound

PLAN.md's, unchanged by this change. K = 16, C_eff = 500 checks a second, T = one turn (≤ 47 ms), 20 ms retry, 0.1 s for delivery:

| | first copy checked within | numbers for the rows | measured worst on `fix`, valid runs |
|---|---|---|---|
| (B1) its key isn't forged | K/C_eff + 20 ms + T | 0.22 s | N1 0.127 s, N1c 0.119 s |
| (B2) forged from S ≤ 63 sources that stay | (S + 1) · 4/3 · K_f/C_eff + 20 ms + T | 0.33 s at offset 0 (S = 40), 0.17 s after; N2 0.23 s | N0c 0.099 s, N2 0.036 s |
| (B3) sources used once, more than 256, or turned over faster than retained | none | N0: p ≤ 1 500/R a copy | as above |
| its exact source spoofed | none | | |

One run is outside its bound: N1 `xchurn-40-100000-120` run 4, first frame 0.244 s against 0.22 s, inside the 1.0 s deadline. It is one of the
INVALID runs (54 400 of 100 000 in its lowest second, 290 000 datagrams dropped at the socket) from 19:08Z, when the host's load from other lanes was
20 and the bound's assumption that the loop gets a core when it wants one did not hold. It is reported, not discarded.

## 🍃's finding, and what it changed

[#178, review 6068314339](https://github.com/karmaterminal/binary-canticle/pull/178#pullrequestreview-6068314339): since `8495138` a waiting claim kept the
tier it was made with, however its source's marks changed. Fixed RED first (`a7d65f3`: four tests, red on `72db59f`, the first three green on `d49645b`),
with 🍃's line (`00b44d7`), and then the same rule without its reader cost (`dfa0414`: a claim knows until when its marks give its tier). `offer()` per
datagram, the minimum of 11 runs: 40 ports held open 1.18 µs on `72db59f`, 1.31 with the line, 1.19 now; 4 ports 0.98, 1.09, 0.99. AB at the socket
(R3 flat out): where R3 saturated it, the reader read 652 000 and 650 000 datagrams a second on `fix`, and 653 000 and 658 000 on `new` (612 000 at load 13.6).

From the code it can change only churned floods of a key (a mark forgotten in 0.17 s, an address back within 0.3-1.4 s). Measured, it did not
change their verdicts: N0 1 of 8 on both, E3's churned rows fail on both (`cold-start-churn-own-host-20000`'s worst item 11.1 s on `fix`, 4.0 s on
`new`), and I's rows are the same.

## How it was run, and what departed from the plan

- `new`'s set ran to its end unattended after the lane stopped on 11-25 (23:53Z to 03:35Z); its files were copied as they were written.
- The third set waited for another lane's measurement window on ronan (radio-four-quantities, until 09:55Z on 11-26), and before each step for
  the host's load (declared at 09:40Z; E2 rows at most 5 minutes, declared at 10:35Z).
- From 17:40Z the host's load from other lanes was 12-22 and the nice-19 producers were starved. The queue was stopped between two runs at 19:53Z,
  nothing cut short or discarded, and went on in a declared new order: E2's runs, then N1c and N2 a round at a time, then the completions, each after
  a longer wait for the load (20:00Z). Of `fix`'s 203 newcomer runs, 33 were underdriven; all are in the tables as INVALID.
- AB, the `offer()` benchmark and the gates are diagnostics. They decide nothing.

## Not done here

- Exact-source spoofing, relay-first and per-frame source changers stay outside the guarantee (C needs an authenticated identity first).
- Option B (a larger slice) was not measured.
- The F rows of E2 ran in run 0 only, as declared.
