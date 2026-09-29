"""JetStream probes for canticle semantics (nats-server 2.14.x).
J1 late-joiner snapshot via DeliverLastPerSubject (a carousel substitute with zero loop traffic)
J2 does Nats-TTL restart when a message is copied to another stream (Sources = relay hop)?
J3 server-side carousel via message schedules (@every + Nats-Schedule-Source + TTL on the schedule)
J4 granularity limits: sub-second Nats-TTL and @every < 1s
"""
import asyncio, json, os, time
import nats
from nats.js.api import ConsumerConfig, DeliverPolicy
from nacl.signing import SigningKey
import frame

URL = os.environ.get("NATS", "nats://127.0.0.1:4333")
sk = SigningKey(b"station-seed-000000000000000000".ljust(32, b"0"))


async def api(nc, subj, body):
    r = await nc.request(subj, json.dumps(body).encode(), timeout=5)
    return json.loads(r.data)


async def stream(nc, name, **cfg):
    await api(nc, f"$JS.API.STREAM.DELETE.{name}", {})
    r = await api(nc, f"$JS.API.STREAM.CREATE.{name}", {"name": name, "storage": "memory", **cfg})
    assert "error" not in r, r
    return r


async def last(nc, name, subj):
    r = await api(nc, f"$JS.API.STREAM.MSG.GET.{name}", {"last_by_subj": subj})
    return None if "error" in r else r["message"]


async def main():
    nc = await nats.connect(URL); js = nc.jetstream(); out = {}

    # J1: 20 live items published once each (Nats-TTL = remaining life), late joiner snapshot.
    await stream(nc, "CANT", subjects=["canticle.js.>"], allow_msg_ttl=True, max_msgs_per_subject=1)
    for seq in range(1, 21):
        b = frame.encode(sk, 1, 7, seq, ttl_s=30, body=os.urandom(600))
        await js.publish(f"canticle.js.st1.7.{seq}", b, headers={"Nats-TTL": "30s"})
    await asyncio.sleep(2)
    got, t0, done = [], time.time(), asyncio.Event()
    async def cb(m):
        got.append(time.time() - t0)
        if len(got) == 20: done.set()
    sub = await js.subscribe("canticle.js.>", cb=cb, ordered_consumer=True,
                             config=ConsumerConfig(deliver_policy=DeliverPolicy.LAST_PER_SUBJECT))
    await asyncio.wait_for(done.wait(), 5)
    out["J1_snapshot_all20_s"] = round(max(got), 4)
    await sub.unsubscribe()

    # J2: TTL across a Sources hop.
    await stream(nc, "SRC", subjects=["src.>"], allow_msg_ttl=True)
    await js.publish("src.item", b"x", headers={"Nats-TTL": "6s"}); t_pub = time.time()
    await asyncio.sleep(3)
    await stream(nc, "DST", allow_msg_ttl=True, sources=[{"name": "SRC"}])
    gone_src = gone_dst = seen_dst = None; dst_hdrs = None
    while time.time() - t_pub < 16 and (gone_src is None or gone_dst is None):
        if gone_src is None and await last(nc, "SRC", "src.item") is None: gone_src = time.time() - t_pub
        m = await last(nc, "DST", "src.item")
        if m is not None and seen_dst is None: seen_dst = time.time() - t_pub; dst_hdrs = m.get("hdrs")
        if seen_dst is not None and gone_dst is None and m is None: gone_dst = time.time() - t_pub
        await asyncio.sleep(0.25)
    out["J2_ttl6_src_gone_s"] = gone_src and round(gone_src, 2)
    out["J2_dst_created_at3_first_seen_s"] = seen_dst and round(seen_dst, 2)
    out["J2_dst_gone_s"] = gone_dst and round(gone_dst, 2)
    import base64
    out["J2_dst_hdrs"] = dst_hdrs and base64.b64decode(dst_hdrs).decode(errors="replace")
    # J3b: can plain core subscribers hear scheduled output if the stream republishes it?
    await stream(nc, "SCHEDR", subjects=["rsched.>", "ritems.>", "ronair.>"], allow_msg_ttl=True,
                 allow_msg_schedules=True, republish={"src": "ronair.>", "dest": "live.>"})
    heard_r = []
    async def rcb(m): heard_r.append(m.data)
    await nc.subscribe("live.>", cb=rcb)
    await js.publish("ritems.x", b"payload-x")
    await js.publish("rsched.x", b"", headers={"Nats-Schedule": "@every 1s", "Nats-Schedule-Source": "ritems.x",
                                               "Nats-Schedule-Target": "ronair.x", "Nats-TTL": "4s"})
    await asyncio.sleep(6)
    out["J3b_core_heard_via_republish"] = len(heard_r)

    # J3: server-side carousel via schedules.
    await stream(nc, "SCHED", subjects=["sched.>", "items.>", "onair.>"], allow_msg_ttl=True,
                 allow_msg_schedules=True, allow_rollup_hdrs=True)
    item = frame.encode(sk, 1, 7, 99, ttl_s=5, body=os.urandom(600))
    await js.publish("items.st1.7.99", item)
    core_heard, js_heard = [], []
    async def ccb(m): core_heard.append((time.time(), m.data))
    await nc.subscribe("onair.>", cb=ccb)
    t0 = time.time()
    ack = await js.publish("sched.st1.7.99", b"", headers={
        "Nats-Schedule": "@every 1s", "Nats-Schedule-Source": "items.st1.7.99",
        "Nats-Schedule-Target": "onair.st1.7.99", "Nats-TTL": "5s"})
    async def jcb(m): js_heard.append((time.time(), m.data, m.metadata.sequence.stream, dict(m.headers or {})))
    s3 = await js.subscribe("onair.>", cb=jcb, ordered_consumer=True)
    await asyncio.sleep(9)
    out["J3_core_sub_heard"] = len(core_heard)
    out["J3_js_fires"] = len(js_heard)
    out["J3_fire_times_s"] = [round(t - t0, 2) for t, *_ in js_heard]
    out["J3_bytes_identical_to_item"] = all(d == item for _, d, *_ in js_heard)
    out["J3_stream_seqs"] = [s for *_, s, _ in js_heard]
    out["J3_headers_first"] = js_heard[0][3] if js_heard else None
    await s3.unsubscribe()

    # J4: granularity limits.
    try:
        await js.publish("src.sub", b"x", headers={"Nats-TTL": "500ms"}); out["J4_ttl_500ms"] = "accepted"
    except Exception as e:
        out["J4_ttl_500ms"] = f"rejected: {e}"
    try:
        await js.publish("sched.fast", b"", headers={"Nats-Schedule": "@every 500ms", "Nats-Schedule-Target": "onair.fast"})
        out["J4_every_500ms"] = "accepted"
    except Exception as e:
        out["J4_every_500ms"] = f"rejected: {e}"
    print(json.dumps(out, indent=1, default=str)); await nc.close()

asyncio.run(main())
