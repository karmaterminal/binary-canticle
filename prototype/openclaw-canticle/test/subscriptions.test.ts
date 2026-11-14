import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import type { Binding } from "../src/binding.ts";
import { ConfigError, parseConfig } from "../src/config.ts";
import { Clock, FakeDaemon, KEY_CAEL, SESSION, OTHER_SESSION, configFor, makeBinding, removeDir, tempDir, waitFor } from "./helpers.ts";

let dir: string;
let clock: Clock;
let daemon: FakeDaemon;
let binding: Binding | undefined;
beforeEach(() => { dir = tempDir(); clock = new Clock(); daemon = new FakeDaemon(dir); binding = undefined; });
afterEach(async () => { await binding?.stop(); await daemon.stop(); removeDir(dir); });

test("exact-key subscriptions are bounded, unique, and untuned by default", () => {
  const base = { binding: "rune", daemon: { socket: "/tmp/canticle.sock" } };
  assert.deepEqual(parseConfig(base).listen.subscriptions, []);
  for (const subscriptions of [
    [{ sessionKey: "agent:*", tune: ["*:*"] }],
    [{ sessionKey: "A", tune: ["*:*"] }, { sessionKey: "a", tune: ["*:*"] }],
    [{ sessionKey: "a", tune: [] }],
    [{ sessionKey: "a", tune: Array(17).fill("*:*") }],
    Array.from({ length: 65 }, (_, i) => ({ sessionKey: `s${i}`, tune: ["*:*"] })),
  ]) assert.throws(() => parseConfig({ ...base, listen: { subscriptions } }), ConfigError);
});

test("new, journal, on_air and status only show a session's subscribed items", async () => {
  await daemon.start();
  daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "chatter", seq: 1, issued_at: clock.t, text: "visible-secret" });
  daemon.surface({ station: "cael", key_id: KEY_CAEL, stream: "alerts", seq: 2, issued_at: clock.t, text: "hidden-secret" });
  const cfg = configFor("rune", dir, daemon, { listen: { tune: ["*:*"], payloadSessions: ["*"], subscriptions: [{ sessionKey: SESSION.sessionKey, tune: ["cael:chatter"] }] } });
  binding = makeBinding(cfg, clock);
  await binding.start();
  await waitFor(() => binding!.receiver.items.size === 2, "both items ingested globally");
  for (const what of ["new", "journal", "on_air"]) {
    const r = binding.listen(SESSION, { what, view: "items", station: "cael", includeSelf: true });
    assert.match(r.text, /visible-secret/);
    if (what !== "on_air") assert.equal(r.details.filtered, 0);
    assert.doesNotMatch(JSON.stringify(r), /hidden-secret|alerts/);
    const other = binding.listen(OTHER_SESSION, { what, view: "digest", includeSelf: true });
    assert.doesNotMatch(JSON.stringify(other), /visible-secret|hidden-secret|chatter|alerts/);
  }
  const cursor = binding.listen(SESSION, { what: "journal" }).details.from;
  const replay = binding.listen(OTHER_SESSION, { what: "journal", since: cursor, stream: "alerts", includeSelf: true });
  assert.doesNotMatch(JSON.stringify(replay), /hidden-secret|alerts/);
  assert.equal((binding.status(SESSION).details.on_air as { current: number }).current, 1);
  const status = binding.status(OTHER_SESSION);
  assert.equal((status.details.on_air as { current: number }).current, 0);
  assert.equal((status.details.journal as { new_for_this_session: number }).new_for_this_session, 0);
  assert.doesNotMatch(JSON.stringify(status), /visible-secret|hidden-secret|chatter|alerts/);
});
