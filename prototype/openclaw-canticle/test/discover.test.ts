import assert from "node:assert/strict";
import { test } from "node:test";
import { parseConfig } from "../src/config.ts";
import { Discoverer } from "../src/discover.ts";

const key = Buffer.alloc(32, 7).toString("base64");
const domain = "example.org";
const service = `_canticle._udp.${domain}.`;
const instance = `cael.${service}`;
const config = () => parseConfig({ binding: "rune", daemon: { socket: "/tmp/none" }, discovery: {
  domains: [domain], catalog: [{ name: "cael", publicKey: key, publicStreams: ["hymn"] }],
} }).discovery;

test("untuned domain and empty catalog never query DNS", async () => {
  let calls = 0;
  const dns = async () => { calls++; return []; };
  const d = new Discoverer({ domains: [domain], catalog: [] }, dns);
  assert.deepEqual((await d.browse(domain) as {stations: unknown[]}).stations, []);
  await assert.rejects(d.browse("other.org"), /explicitly configured/);
  assert.equal(calls, 0);
});

test("only catalog public streams surface; DNS mismatches never confer identity", async () => {
  const seen: string[] = [];
  const dns = async (name: string) => {
    seen.push(name);
    if (name === service) return [{ type: "PTR", value: instance, ttl: 300 }, { type: "PTR", value: `outsider.${service}` }];
    if (name === instance) return [
      { type: "SRV", target: "relay.example.org.", port: 47113, ttl: 120 },
      { type: "TXT", entries: ["sid=0000000000000000", "k=ed25519:bogus", "streams=hymn,private"], ttl: 120 },
    ];
    return [];
  };
  const d = new Discoverer(config(), dns);
  const result = await d.browse(domain) as {stations: { public_streams: string[]; mismatches: string[] }[]};
  assert.deepEqual(result.stations[0]?.public_streams, ["hymn"]);
  assert.deepEqual(result.stations[0]?.mismatches, ["k", "sid", "streams"]);
  assert.equal(result.stations.length, 1);
  assert.equal(JSON.stringify(result).includes("private"), false);
  assert.equal(seen.length, 3);
  assert.deepEqual((await d.browse(domain, "private") as {stations: unknown[]}).stations, []);
});

test("TTL refresh, negative cache, out-of-zone target, and instance bound", async () => {
  let now = 0;
  let calls = 0;
  const dns = async (name: string) => {
    calls++;
    if (name === service) return [{ type: "PTR", value: instance, ttl: 3 }];
    if (name === instance) return [{ type: "SRV", target: "evil.other.org.", port: 47113, ttl: 2 }];
    return [];
  };
  const d = new Discoverer(config(), dns, () => now);
  const r = await d.browse(domain) as {stations: {locators: unknown[]; mismatches: string[]}[]};
  assert.deepEqual(r.stations[0]?.locators, []);
  assert.deepEqual(r.stations[0]?.mismatches, ["srv-target"]);
  await d.browse(domain);
  assert.equal(calls, 3);
  now = 2000;
  await d.browse(domain);
  assert.equal(calls, 4); // SRV expired; PTR and negative TXT still cached.
  const many = async (name: string) => name === service
    ? Array.from({ length: 40 }, (_, i) => ({ type: "PTR", value: `cael${i}.${service}`, ttl: 100 })) : [];
  assert.equal((await new Discoverer(config(), many).browse(domain) as {truncated: boolean}).truncated, true);
});

test("catalog validation refuses malformed identity or public stream", () => {
  assert.throws(() => parseConfig({ binding: "rune", daemon: { socket: "/tmp/none" }, discovery: {
    domains: [domain], catalog: [{ name: "cael", publicKey: key, publicStreams: ["*"] }],
  } }), /discovery.catalog/);
});

test("negative PTR cache expires and out-of-zone PTR cannot trigger more queries", async () => {
  let now = 0;
  let calls = 0;
  const dns = async () => { calls++; return [{ type: "PTR", value: "cael._canticle._udp.evil.org.", ttl: 600 }]; };
  const d = new Discoverer(config(), dns, () => now);
  assert.deepEqual((await d.browse(domain) as {stations: unknown[]}).stations, []);
  await d.browse(domain);
  assert.equal(calls, 1);
  now = 300_000;
  await d.browse(domain);
  assert.equal(calls, 2);
});

test("output caps eight rows even when PTR names many cataloged stations", async () => {
  const catalog = Array.from({length: 12}, (_, i) => ({ name: `cael${i}`, publicKey: key, publicStreams: ["hymn"] }));
  const dns = async (name: string) => name === service
    ? catalog.map((c) => ({ type: "PTR", value: `${c.name}.${service}`, ttl: 300 }))
    : [{ type: "SRV", name: "relay.example.org.", port: 47113, ttl: 120 }];
  const result = await new Discoverer({ domains: [domain], catalog }, dns).browse(domain) as {stations: unknown[]; truncated: boolean};
  assert.equal(result.stations.length, 8);
  assert.equal(result.truncated, true);
});
