// The state lease on its own: one holder per state root, released when its holder stops or dies, whatever the
// length of the root's path. A real OpenClaw Gateway keeps its state in a directory deep enough that a socket file
// under it would not fit in a unix socket address, so on Linux the lease is an abstract socket named after the root.

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { lstatSync, mkdirSync, symlinkSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, test } from "node:test";
import { BindingStartError } from "../src/binding.ts";
import { Lease, LeaseHeld } from "../src/store.ts";
import { Clock, FakeDaemon, configFor, makeBinding, removeDir, tempDir } from "./helpers.ts";

let dir: string;

beforeEach(() => {
  dir = tempDir();
});

afterEach(() => {
  removeDir(dir);
});

/** A state root whose `lease.sock` would be longer than any unix socket address. */
function deepRoot(): string {
  const root = join(dir, "openclaw-state-directory-of-a-prince".repeat(2), "canticle", "a-binding-with-a-long-name");
  mkdirSync(root, { recursive: true });
  assert.ok(Buffer.byteLength(join(root, "lease.sock")) > 108);
  return root;
}

test("on Linux: one holder per root however deep the path, the same root through a symlink, and release frees it", { skip: process.platform !== "linux" }, async () => {
  const root = deepRoot();
  const first = new Lease(root);
  await first.acquire();
  try {
    await assert.rejects(new Lease(root).acquire(), LeaseHeld);
    const link = join(dir, "link");
    symlinkSync(root, link);
    await assert.rejects(new Lease(link).acquire(), LeaseHeld); // the name follows the real path
    const other = join(dir, "other");
    mkdirSync(other);
    const second = new Lease(other);
    await second.acquire(); // another root is another lease
    await second.release();
  } finally {
    await first.release();
  }
  const again = new Lease(root);
  await again.acquire();
  await again.release();
});

test("elsewhere: a socket file in the root; a live one refuses, a stale one is replaced, a deep root is refused", async () => {
  const root = join(dir, "short");
  mkdirSync(root);
  const first = new Lease(root, "darwin");
  await first.acquire();
  await assert.rejects(new Lease(root, "darwin").acquire(), LeaseHeld);
  await first.release();
  // A holder killed outright leaves its socket file behind, answering nothing.
  const path = join(root, "lease.sock");
  const holder = spawn(process.execPath, ["-e", `require("net").createServer().listen(${JSON.stringify(path)}, () => console.log("up"))`]);
  await new Promise<void>((resolve) => holder.stdout.once("data", () => resolve()));
  holder.kill("SIGKILL");
  await new Promise<void>((resolve) => holder.once("exit", () => resolve()));
  assert.ok(lstatSync(path).isSocket());
  const next = new Lease(root, "darwin");
  await next.acquire();
  await next.release();
  await assert.rejects(new Lease(deepRoot(), "darwin").acquire(), /longer than 103 bytes; choose a shorter stateDir/);
});

test("a binding on a deep state root starts, and a second binding on it is refused as state_locked", { skip: process.platform !== "linux" }, async () => {
  const clock = new Clock();
  const daemon = new FakeDaemon(dir);
  await daemon.start();
  const root = deepRoot();
  const a = makeBinding(configFor("rune", dir, daemon, { stateDir: root }), clock);
  try {
    await a.start();
    const b = makeBinding(configFor("rune", dir, daemon, { stateDir: root }), clock);
    await assert.rejects(b.start(), (e: unknown) => e instanceof BindingStartError && e.reason === "state_locked");
  } finally {
    await a.stop();
    await daemon.stop();
  }
});
