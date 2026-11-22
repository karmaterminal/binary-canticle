#!/usr/bin/env node
// Offline source-composition receipt. No network, model, live session or deployment.
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const plugin = join(root, "prototype/openclaw-canticle");
const args = process.argv.slice(2);
if (args.length !== 2 || args[0] !== "--output" || !args[1]) {
  console.error("Usage: node prototype/openclaw-canticle/proofs/core-reader.mjs --output /tmp/canticle-reader-receipt.json");
  process.exit(2);
}
const output = resolve(args[1]);
// Temporary local receipts must not become a secret/state artifact in the checkout.
const inside = relative(root, output);
if (!(inside === ".." || inside.startsWith(`..${sep}`) || isAbsolute(inside))) {
  throw new Error("Write the receipt outside the repository, for example /tmp/canticle-reader-receipt.json");
}
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const inputFiles = [];
function walk(path) {
  for (const item of readdirSync(path, { withFileTypes: true })) {
    const file = join(path, item.name);
    if (item.isDirectory()) walk(file);
    else if (item.isFile() && /\.(ts|source|json)$/.test(item.name)) inputFiles.push(file);
  }
}
walk(join(plugin, "src")); walk(join(plugin, "test"));
inputFiles.push(join(plugin, "index.ts"), join(plugin, "openclaw.plugin.json"), fileURLToPath(import.meta.url));
const source = inputFiles.sort().map((file) => ({ path: relative(root, file), sha256: sha(readFileSync(file)) }));
const head = spawnSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8", timeout: 5000 });
if (head.status !== 0) throw new Error("Cannot identify the checked-out Git commit");
const dirty = spawnSync("git", ["status", "--porcelain", "--untracked-files=all"], { cwd: root, encoding: "utf8", timeout: 5000 });
if (dirty.status !== 0) throw new Error("Cannot inspect the worktree state");
const start = new Date().toISOString();
const files = ["test/local-reader.test.ts", "test/core-wrapper-reader.test.ts"];
const run = spawnSync(process.execPath, ["--test", "--test-reporter=tap", ...files], {
  cwd: plugin, encoding: "utf8", timeout: 60_000, maxBuffer: 2_000_000,
});
const tap = run.stdout ?? "";
const count = (field) => Number(tap.match(new RegExp(`^# ${field} (\\d+)$`, "m"))?.[1] ?? NaN);
const counts = { tests: count("tests"), pass: count("pass"), fail: count("fail"), cancelled: count("cancelled"), skipped: count("skipped"), todo: count("todo") };
const passed = run.status === 0 && counts.tests >= 20 && counts.pass === counts.tests &&
  counts.fail === 0 && counts.cancelled === 0 && counts.skipped === 0 && counts.todo === 0;
const receipt = {
  version: "canticle-core-reader-source-proof/1", result: passed ? "pass" : "fail",
  evidence: "offline-source-composition", issue: 145,
  started_at: start, finished_at: new Date().toISOString(), node: process.version,
  binary_canticle_head: head.stdout.trim(), worktree_dirty: dirty.stdout.trim().length > 0,
  openclaw_source: "21660b2182062a9a98eb28d46341283100c082e6",
  input_sha256: source, tests: counts, tap_sha256: sha(tap),
  synthetic_payload_sha256: sha("the brass QUIET sign is bolted to a bell"),
  exercised: ["production plugin registration", "core factory context and factory resolver", "core callback wrapper before and after await", "core registry and plugin-instance ownership checks", "core exact local route decision", "plugin callerOf, Binding, Receiver, persisted taint and mute", "host-bound pre-return exposure fence and exact selected source metadata", "pending exposure surviving SQLite reopen after withheld result"],
  fixtures: ["session row, placement and binding storage adapters", "admitted-run producer and sandbox selection", "plugin runtime scope and non-policy environmental services", "lease acquisition and daemon startup", "synthetic receptor records", "host exposure port backed by a disposable SQLite ledger; no production history origin or confirmation"],
  not_proved: ["installed Gateway or fleet configuration", "host tool-policy allowlist and sandbox enforcement", "parent-result or non-tool egress containment", "live station signature or transport", "model encounter", "derived publication", "room egress", "launch readiness"],
  exit_status: run.status, signal: run.signal ?? null, error: run.error?.message ?? null,
};
mkdirSync(dirname(output), { recursive: true, mode: 0o700 });
writeFileSync(`${output}.tap`, tap + (run.stderr ?? ""), { mode: 0o600, flag: "wx" });
writeFileSync(output, JSON.stringify(receipt, null, 2) + "\n", { mode: 0o600, flag: "wx" });
console.log(`${receipt.result}: ${counts.pass}/${counts.tests} source-composition tests; receipt ${output}`);
if (!passed) process.exitCode = 1;
