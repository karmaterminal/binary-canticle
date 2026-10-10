// Against the real spike (binary-canticle#97): the Python host daemon (`canticle daemon`) and two stations
// (`canticle station`) on loopback, with keys and a fleet manifest made in a temporary directory. The binding hears
// another prince's item through the daemon, sings and plucks through its own station's control socket, hears its
// own item come back, restarts into a rejoin, and rides out a daemon restart without journaling anything twice.
//
// It needs Python with the station's requirements (`cryptography`). Without them the test is skipped, unless
// CANTICLE_INTEROP=require (CI sets it), when the missing requirement is a failure.

import assert from "node:assert/strict";
import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { Binding } from "../src/binding.ts";
import { parseConfig } from "../src/config.ts";
import type { Obj } from "../src/records.ts";
import { stationClient } from "../src/station.ts";
import { removeDir, sleep, tempDir, waitFor } from "./helpers.ts";

const PY = process.env.CANTICLE_PYTHON ?? "python3";
const STATION_SRC = join(import.meta.dirname, "..", "..", "canticle-station");
const ENV = { ...process.env, PYTHONPATH: STATION_SRC, PYTHONDONTWRITEBYTECODE: "1" };

function unavailable(): string | null {
  const r = spawnSync(PY, ["-c", "import cryptography, canticle"], { env: ENV, encoding: "utf8" });
  return r.status === 0 ? null : `${PY} cannot import cryptography and canticle: ${(r.stderr ?? String(r.error)).trim().split("\n").at(-1)}`;
}

const missing = unavailable();
if (missing !== null && process.env.CANTICLE_INTEROP === "require") {
  throw new Error(`CANTICLE_INTEROP=require: ${missing}`);
}

/** A child process whose stderr lines are kept, parsed as JSON where they are JSON. */
class Proc {
  readonly child: ChildProcess;
  readonly lines: string[] = [];
  private exited: Promise<number | null>;

  constructor(args: string[]) {
    this.child = spawn(PY, ["-m", "canticle", ...args], { env: ENV, stdio: ["ignore", "ignore", "pipe"] });
    let buf = "";
    this.child.stderr?.setEncoding("utf8");
    this.child.stderr?.on("data", (d: string) => {
      buf += d;
      let i = buf.indexOf("\n");
      while (i !== -1) {
        this.lines.push(buf.slice(0, i));
        buf = buf.slice(i + 1);
        i = buf.indexOf("\n");
      }
    });
    this.exited = new Promise((resolve) => this.child.once("exit", (code) => resolve(code)));
  }

  json(): Obj[] {
    return this.lines.flatMap((l) => {
      try {
        const v = JSON.parse(l) as unknown;
        return typeof v === "object" && v !== null ? [v as Obj] : [];
      } catch {
        return [];
      }
    });
  }

  async line(pred: (o: Obj) => boolean, what: string): Promise<Obj> {
    let hit: Obj | undefined;
    await waitFor(() => {
      hit = this.json().find(pred);
      if (hit === undefined && this.child.exitCode !== null) {
        throw new Error(`${what}: the process exited ${this.child.exitCode}: ${this.lines.join(" | ")}`);
      }
      return hit !== undefined;
    }, what, 15_000);
    return hit as Obj;
  }

  async stop(): Promise<void> {
    if (this.child.exitCode !== null || this.child.signalCode !== null) {
      return;
    }
    this.child.kill("SIGTERM");
    const killer = setTimeout(() => this.child.kill("SIGKILL"), 5_000);
    await this.exited;
    clearTimeout(killer);
  }
}

function keygen(dir: string, name: string): string {
  const r = spawnSync(
    PY,
    ["-m", "canticle", "keygen", "--out", join(dir, `${name}.key`), "--manifest", join(dir, "fleet.json"), "--name", name,
      "--classes", "chatter", "--streams", "chatter", "--scopes", "host,lan"],
    { env: ENV, encoding: "utf8" },
  );
  assert.equal(r.status, 0, r.stderr);
  return (JSON.parse(r.stdout) as { key_id: string }).key_id;
}

test("the binding against the real daemon and stations: hear, sing, hear back, pluck, rejoin, daemon restart", { skip: missing ?? false, timeout: 90_000 }, async () => {
  const dir = tempDir();
  const run = join(dir, "run");
  mkdirSync(run, { mode: 0o700 });
  const procs: Proc[] = [];
  let binding: Binding | null = null;
  try {
    const runeKey = keygen(dir, "rune");
    const caelKey = keygen(dir, "cael");
    const daemonArgs = (bind: string) => [
      "daemon", "--manifest", join(dir, "fleet.json"), "--bind", bind, "--socket", join(run, "daemon.sock"),
      "--state-dir", join(dir, "daemon-state"), "--health-interval", "1",
    ];
    let daemon = new Proc(daemonArgs("127.0.0.1:0"));
    procs.push(daemon);
    const hello = await daemon.line((o) => o.type === "hello", "the daemon's hello");
    const bind = String(hello.bind);
    assert.match(bind, /^127\.0\.0\.1:\d+$/);
    for (const name of ["rune", "cael"]) {
      const station = new Proc([
        "station", "--key", join(dir, `${name}.key`), "--manifest", join(dir, "fleet.json"), "--stream", "chatter",
        "--to", bind, "--control", join(run, `${name}.ctl`), "--beacon-ms", "500",
      ]);
      procs.push(station);
      await station.line((o) => typeof o.station === "string", `the ${name} station`);
      await waitFor(() => existsSync(join(run, `${name}.ctl`)), `the ${name} control socket`, 15_000);
    }
    const cfg = parseConfig({
      binding: "rune",
      daemon: { socket: join(run, "daemon.sock") },
      stateDir: join(dir, "state-rune"),
      listen: { payloadSessions: ["agent:rune:reader"] },
      station: { name: "rune", keyId: runeKey },
      publish: { enabled: true, socket: join(run, "rune.ctl") },
    });
    const up = async (): Promise<Binding> => {
      const b = new Binding({ config: cfg, root: cfg.stateDir as string, tickMs: 200, link: { backoff: { firstMs: 100, maxMs: 500, jitter: 0 } } });
      await b.start();
      await waitFor(() => b.receiver.current(), "the binding to join the daemon", 15_000);
      return b;
    };
    binding = await up();
    const reader = { sessionKey: "agent:rune:reader", sessionId: "r-1", subagent: false, anonymous: false };
    const singer = { sessionKey: "agent:rune:main", sessionId: "m-1", subagent: false, anonymous: false };
    /** The whole journal, page by page. */
    const journal = (b: Binding, p: Obj = {}): { text: string; entries: { kind: string; station?: string }[] } => {
      const out = { text: "", entries: [] as { kind: string; station?: string }[] };
      let since: string | undefined;
      for (;;) {
        const r = b.listen(reader, { what: "journal", limit: 20, view: "items", ...p, ...(since !== undefined ? { since } : {}) });
        out.text += `${r.text}\n`;
        out.entries.push(...(r.details.entries as { kind: string; station?: string }[]));
        if (r.details.truncated !== true) {
          return out;
        }
        since = r.details.next as string;
      }
    };
    const heardOnce = (b: Binding): number =>
      journal(b, { view: "digest" }).entries.filter((e) => e.kind === "heard" && e.station === "cael").length;

    // Another prince sings; the binding hears it through the daemon, under the banner, as untrusted data.
    const cael = await stationClient(join(run, "cael.ctl"))({ op: "sing", stream: "chatter", text: "hello from cael", scope: "lan", loop: "fast" });
    assert.equal(cael.kind, "reply");
    assert.equal((cael as { reply: Obj }).reply.ok, true);
    const b1 = binding;
    await waitFor(() => journal(b1).text.includes("hello from cael"), "cael's item in the journal", 15_000);
    const read = b1.listen(reader, { what: "journal", view: "items" });
    assert.match(read.text, new RegExp(`station="cael" principal="unavailable" key=${caelKey} sig=valid stream=chatter`));
    assert.match(read.text, new RegExp(`From: cael ${caelKey}\n---\nhello from cael\n<<<END_EXTERNAL_UNTRUSTED_CONTENT`));
    assert.match(read.text, /<<<EXTERNAL_UNTRUSTED_CONTENT id=/);
    assert.equal(read.details.untrusted, true);
    assert.match(b1.listen(reader, { what: "on_air", view: "digest" }).text, /cael:chatter/);

    // The binding sings through its own station: a receipt, then its own item heard back through the daemon.
    const sung = (await b1.sing(singer, { stream: "chatter", payload: "from rune", ttlSeconds: 30 })).details.result as Obj;
    assert.equal(sung.status, "on-air", JSON.stringify(sung));
    const item = sung.item as string;
    await waitFor(() => b1.outbox?.get(item)?.heard_at !== null, "rune's item heard back", 15_000);
    assert.equal(b1.outbox?.get(item)?.key_id, runeKey);
    assert.equal(typeof b1.outbox?.get(item)?.receipt?.epoch, "number");
    // Withdraw after emission: the station plucks it, and the daemon's retract reaches the journal.
    const hushed = (await b1.hush(singer, { item })).details.result as Obj;
    assert.equal(hushed.status, "plucked", JSON.stringify(hushed));
    assert.equal(b1.outbox?.get(item)?.state, "withdrawn");
    await waitFor(() => journal(b1, { includeSelf: true }).text.includes("[canticle:withdrawn]"), "the retract", 15_000);

    // Restart the binding: it rejoins the same run from its snapshot and journals nothing twice.
    assert.equal(heardOnce(b1), 1);
    await b1.stop();
    binding = await up();
    const b2 = binding;
    assert.match(journal(b2).text, /\(rejoin\)/);
    assert.match(b2.listen(reader, { what: "on_air", view: "digest" }).text, /cael:chatter/);
    assert.equal(heardOnce(b2), 1);

    // Stop the daemon: the binding's view stops being current and nothing is claimed to be on air.
    await daemon.stop();
    await waitFor(() => !b2.receiver.current(), "the binding to notice the daemon went away", 15_000);
    assert.match(b2.listen(reader, { what: "on_air", view: "digest" }).text, /unknown/);
    // Start it again on the same port: the binding reconnects, takes a complete snapshot, and still journals the
    // looping item once.
    daemon = new Proc(daemonArgs(bind));
    procs.push(daemon);
    await daemon.line((o) => o.type === "hello", "the restarted daemon's hello");
    await waitFor(() => b2.receiver.current(), "the binding to rejoin the restarted daemon", 20_000);
    await waitFor(() => /cael:chatter/.test(b2.listen(reader, { what: "on_air", view: "digest" }).text), "cael's item on air again", 20_000);
    await sleep(200);
    assert.equal(heardOnce(b2), 1);
    const status = b2.status(reader).details as { receive: Obj };
    assert.equal((status.receive as Obj).health, "ok", JSON.stringify(status.receive));
  } finally {
    await binding?.stop();
    for (const p of procs.reverse()) {
      await p.stop();
    }
    removeDir(dir);
  }
});
