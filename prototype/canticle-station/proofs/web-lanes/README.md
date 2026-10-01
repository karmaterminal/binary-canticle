# Same-host proof: ambient emitter (#58) and web tuner (#57)

A bounded run of the two first slices: `canticle ambient` feeding a station, and `canticle tuner` with a
headless browser watching.

**This is same-host evidence.** The station side and the listener side run in two network namespaces on one
kernel, joined by a veth pair, with frames crossing as LAN multicast (`239.255.13.13:9999`, IP TTL 1). They
have separate network stacks but share one machine and one clock. No second host received anything. Hearing
a datagram is not session ingestion either: nothing here lands in any agent session.

## Run

```sh
sudo PYTHON=/path/to/python-with-cryptography ./run.sh            # about 6.5 min; writes results/<UTC stamp>/
python3 analyze.py results/<UTC stamp>                             # checks, and writes summary.json
```

`run.sh` needs root (network namespaces, nftables), and Node with Playwright and Chromium for `browser.cjs`.

| Namespace | Runs |
|---|---|
| `cant-a` (station side) | `canticle station` with `hymn` and `lens.weather`, both `ambient`. Two `canticle ambient` emitters: `hymn` every 2-10 s with breath 0.2, and the topical `lens.weather` every 5-15 s with breath 0.3. Both use a 60 s TTL and run for 300 s from the fixtures `hymn.txt` and `weather.txt`. An nftables counter records every UDP datagram that reaches this namespace. |
| `cant-b` (listener side) | An early `canticle listen` recorder, and `canticle tuner` on `127.0.0.1:8765`. A late `canticle listen` starts at T+150 s. `snapshots.py` reads both rings every 5 s. Headless Chromium runs three sessions: at T+20 s it tunes `hymn`, leaves, retunes `lens.weather` and retunes `hymn`; at T+200 s a late page tunes `hymn`; after the drain it checks both channels again. |

## Result: run `20260930T183722Z`

Run from the clean commit `f7d214f`. `analyze.py` passes all 30 checks. Its later refinement, which splits
the late listener's on-air items from items sung after it started, is analysis only and ran on the same
logs. Figures come from [`results/20260930T183722Z/summary.json`](results/20260930T183722Z/summary.json).

**Emission (#58)**

| | `hymn` | `lens.weather` |
|---|---|---|
| Items sung / breaths / capped / refused | 40 / 10 / 0 / 0 | 22 / 9 / 0 / 0 |
| Tick gap, min-p50-max (s) | 2.38-5.88-9.86 (bound 2-10) | 5.02-10.37-14.77 (bound 5-15) |
| Model calls | 0 | 0 |
| Run ended by | its 300 s bound | its 300 s bound |

**Hearing: distinct signed items and time-to-hear (Silas's receipt)**

| Listener | `hymn` | `lens.weather` | Time to hear, from signed `issued_at` (p50 / max) |
|---|---|---|---|
| Early recorder | 40 of 40 | 22 of 22 | 3 / 5-6 ms |
| Tuner gateway | 40 of 40 | 22 of 22 | 3-4 / 5-6 ms |
| Late recorder (from T+150 s) | 29 heard | 12 heard | 4 / 5-6 ms, for items sung after it started |

The late recorder:

- **Never heard a stale item.** 10 `hymn` items and 9 `lens.weather` items had expired before it started, and it heard none of them.
- **Caught up from the carousel.** Of the items on air when it started, it heard 9 of 10 `hymn` and 2 of 3 `lens.weather`, within 0.8-23.3 s. The bound is one loop × 4/3, about 26.7 s at the 20 s loop.
- **Missed two items, as a carousel should.** `hymn` `seq` 11 had 1.6 s of life left and `lens.weather` `seq` 10 had 5.6 s. Neither had a copy left to send before expiry.
- **Heard everything sung after it started:** 20 of 20 `hymn` and 10 of 10 `lens.weather`.

**Expiry, stop, and a sender that tracks nobody**

- **Natural expiry.** All 62 items expired naturally. Each expiry was reported 14-242 ms after its signed `expires_at`, within the listener's 250 ms tick.
- **Ring snapshots.** 156 snapshots never showed an item past its TTL. The 10 snapshots taken after the emitters stopped plus one TTL were empty.
- **Silent station host.** 0 UDP datagrams reached the station's namespace during the whole run: no subscriber table, no acknowledgement loop, no request from any listener. The station's code opens no receiving path, and the counter confirms it.
- **The station was never restarted.** It kept one PID from start to end.

**The page (#57)**

| Step | Seen |
|---|---|
| Tune `hymn` | live ring `seq` 3, 2, 1, all `hymn` fixture lines ([screenshot](results/20260930T183722Z/01-tuned-hymn.png)) |
| Leave | "Not tuned" ([screenshot](results/20260930T183722Z/02-left.png)) |
| Retune `lens.weather` | `seq` 5-1, all weather lines ([screenshot](results/20260930T183722Z/03-retuned-weather.png)) |
| Retune `hymn` | the `hymn` ring again, with no station restart |
| Late page at T+200 s | `seq` 27-20: exactly the items the emitter log says were on air, and none that had expired ([screenshot](results/20260930T183722Z/04-late-page.png)) |
| After the drain | no live items; `seq` 36-40 listed as "expired … (no longer on air)" ([screenshot](results/20260930T183722Z/05-after-stop.png)) |

No browser console errors in any session.

**Resources over the run**

| | |
|---|---|
| CPU seconds | station 0.79; tuner gateway 1.48; early recorder 1.22; late recorder 0.77 |
| Network into the listener side | 785 canticle datagrams, 145 980 B, about 3.2 kbit/s averaged from T0 to the last expiry |
| Model calls | 0 |

## Acceptance items

| Issue item | Where |
|---|---|
| #57.1 select, leave and retune without restarting the station | the page table; "the station was never restarted" |
| #57.2 a late browser sees the live ring and honest expiry and gaps | the late page, the after-drain page, and the ring-snapshot checks |
| #57.3 a second host, or a same-host label | same-host, labelled here and in `run.sh` |
| #57.4 trust boundary and budget | RFC-0001 §18.9; the station README's "Web tuner" section; `test_tuner.py` |
| #58.1 emission timestamps and listener-side rings, with natural expiry and a late tune-in | `emit-*.jsonl`, `listen-*.jsonl`, `tuner-events.jsonl`, `ring-snapshots.jsonl` |
| #58.2 cross-host, or a same-host label | same-host |
| #58.3 stop and expiry; no subscriber table or acknowledgement loop | stop by duration, natural expiry, and 0 datagrams into the station side |
| #58.4 resource budget | the resources table; fixture emission uses zero model calls |

## Not shown here

- **A second host.** A physical LAN, Wi-Fi or relay path hasn't been tried; those need the doctor checks of RFC §11.2 or the relay lease of §11.3.
- **Session landing.** Landing into agent sessions (S3) is out of scope, as are `trail_seq` in beacons and any session-log source for the emitter.
- **Scale and loss.** One station, two streams and a clean veth: no loss or reordering was injected. The protocol-dynamics spike covers loss.
