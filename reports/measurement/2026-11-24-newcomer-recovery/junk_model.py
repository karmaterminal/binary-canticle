"""Established stations and newcomers in a flood of junk and forgeries: the real ``Intake`` of any tree in virtual time, with no sockets and no
signatures. Usage: junk_model.py <prototype/canticle-station> [K,...]      (runs on a0862c3 as it does on this lane's head)

K stations. Four are established (a new frame of each was verified from its source) and sing seven items a second for 28 s; newcomers start on
keys that nobody forges (a quarter of the keys), one every 52 ms. 20 000 datagrams a second: a share of junk (no frames), the rest forged frames from 40 ports
held open, of ``others`` (every key but the established ones' and the newcomers') or of ``all`` (the established ones' too). The event loop
runs at most one turn of 32 a millisecond, 140 µs a check, and what arrives while a turn is verified is placed before its verdicts. Printed: frames
that were never served, and the longest wait."""

import random
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from canticle import intake, runner, wire                                  # noqa: E402
from canticle.ids import stream_id                                         # noqa: E402
from canticle.manifest import Manifest, StationEntry                       # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey    # noqa: E402

RATE, E, HZ, SECONDS, CHECK_S, RETRY_S = 20_000, 4, 7.0, 30.0, 0.00014, 0.02


def udp(port, host=1):
    return int.from_bytes((2).to_bytes(2, sys.byteorder) + port.to_bytes(2, "big") + bytes((127, 0, 0, host)), sys.byteorder)


def item(sk, seq):
    now = runner.now_ms()
    return wire.encode_item(sk, wire.Item(epoch=5, stream=stream_id("chatter"), seq=seq, issued_at=now, body=b"x", scope=1, cls=1, ctype=1,
                                          expires_at=now + 60_000))


def run(keys, junk, whose, seed):
    clock, rng, woken = [1_000.0], random.Random(seed), [0]
    intake.time.monotonic = lambda: clock[0]
    sks = [Ed25519PrivateKey.generate() for _ in range(keys)]
    frames = [item(sk, 1) for sk in sks]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    i = intake.Intake(sock, Manifest([StationEntry(f"s{n}", wire.public_key_bytes(sk), frozenset({1}), ("chatter",)) for n, sk in enumerate(sks)]),
                      now_ms=runner.now_ms, wake=lambda: woken.__setitem__(0, woken[0] + 1))
    sock.close()
    est = [keys * n // E for n in range(E)]
    new = [k for k in range(keys) if k not in est and k % 4 == 3]
    forged = [k for k in range(keys) if k not in new and (whose == "all" or k not in est)]
    good, waits, todo, n = set(), {}, [], 0
    for k in est:
        i.offer([(frames[k], udp(60_000 + k))])
        for t in i.take(32):
            i.settle(t, True, True)
    for m in range(int((SECONDS - 2) / 0.0517)):
        todo.append((1.05 + 0.0517 * m, "new", item(sks[new[m % len(new)]], 2 + m), udp(50_000 + m, 99)))
    for k in est:
        todo += [(1.0 + 0.01 * (k % 7) + m / HZ, "est", item(sks[k], 2 + m), udp(60_000 + k)) for m in range(int((SECONDS - 2) * HZ))]
    todo.sort(key=lambda c: c[0])
    kind = {f: what for _, what, f, _ in todo}
    busy = due = clock[0]
    flight, start = [], clock[0]
    for ms in range(int((SECONDS + 1) * 1000)):
        batch = []
        for _ in range(RATE // 1000):
            n += 1
            if n % 100 < junk * 100:
                batch.append((b"CN" + bytes([n & 255]) * 40, udp(5)))
            else:
                f = frames[forged[n % len(forged)]]
                batch.append((f[:-64] + n.to_bytes(32, "big") + f[-32:], udp(40_000 + n // len(forged) % 40)))
        while todo and todo[0][0] * 1000 <= ms:
            _, _, f, src = todo.pop(0)
            good.add(f)
            waits[f] = -clock[0]
            batch.insert(rng.randrange(len(batch) + 1), (f, src))
        w = woken[0]
        i.offer(batch)
        if woken[0] != w:
            due = min(due, clock[0])
        if flight and clock[0] >= busy:
            for t in flight:
                ok = t.data in good
                if ok and waits[t.data] < 0:
                    waits[t.data] += clock[0]
                if ok:
                    i.remember(t, (t.data[4:12], 5, 0, 1), runner.now_ms() + 600_000)
                i.settle(t, ok, ok)
            flight, due = [], clock[0] if i.waiting() else float("inf")
        if not flight and clock[0] >= due:
            flight = i.take(32)
            busy = clock[0] + len(flight) * CHECK_S
            if not flight:
                due = float("inf") if not i.waiting() else clock[0] + RETRY_S
        clock[0] = start + (ms + 1) / 1000
    return {what: [x for f, x in waits.items() if kind[f] == what] for what in ("est", "new")}


print("| K | junk | the forgeries claim | established: never served, longest wait | newcomers: never served, longest wait |")
print("|---|---|---|---|---|")
for keys in [int(k) for k in (sys.argv[2] if len(sys.argv) > 2 else "16,64").split(",")]:
    for junk in (0.0, 0.5):
        for whose in ("others", "all"):
            got = run(keys, junk, whose, seed=7)
            cell = lambda xs: f"{sum(x < 0 for x in xs)} of {len(xs)}, {1000 * max(xs):.0f} ms"
            print(f"| {keys} | {junk:.0%} | {'other keys' if whose == 'others' else "all but the newcomers'"} | {cell(got['est'])} | {cell(got['new'])} |", flush=True)
