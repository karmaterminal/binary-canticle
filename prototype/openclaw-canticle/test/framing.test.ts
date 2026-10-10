// Record v1 framing (RFC-0001 §14.18.2): line limit, nesting depth, partial line at the end of a stream.

import assert from "node:assert/strict";
import { test } from "node:test";
import { LineFramer, MAX_LINE, nestsDeeperThan, newFramingCounts, parseLine } from "../src/framing.ts";

const LIMIT = 64 * 1024; // §14.18.2 [PROPOSED DEFAULT], newline included

test("lines split across chunks are joined; a line of exactly 64 KiB with its newline is kept", () => {
  const f = new LineFramer();
  assert.deepEqual(f.push(Buffer.from('{"a":')), []);
  assert.deepEqual(f.push(Buffer.from('1}\n{"b"')), ['{"a":1}']);
  assert.deepEqual(f.push(Buffer.from(":2}\n")), ['{"b":2}']);
  assert.equal(MAX_LINE, LIMIT);
  const max = `"${"x".repeat(LIMIT - 3)}"`; // LIMIT - 1 bytes before the newline
  assert.deepEqual(f.push(Buffer.from(`${max}\n`)), [max]);
  assert.equal(f.counts.overlong, 0);
});

test("an over-long line is discarded up to its newline and counted; the next line is read", () => {
  const f = new LineFramer();
  const long = "y".repeat(LIMIT); // LIMIT bytes before the newline: one too many
  const lines = [...f.push(Buffer.from(long.slice(0, 40_000))), ...f.push(Buffer.from(`${long.slice(40_000)}\n{"ok":1}\n`))];
  assert.deepEqual(lines, ['{"ok":1}']);
  assert.equal(f.counts.overlong, 1);
});

test("a partial line at the end of the stream is never a record", () => {
  const f = new LineFramer();
  assert.deepEqual(f.push(Buffer.from('{"a":1}\n{"b":')), ['{"a":1}']);
  f.end();
  assert.equal(f.counts.partial_at_end, 1);
  assert.deepEqual(f.push(Buffer.from('{"c":3}\n')), ['{"c":3}']);
});

test("nesting deeper than 8 is refused before parsing; brackets inside strings do not count", () => {
  const counts = newFramingCounts();
  const deep = `${"[".repeat(9)}${"]".repeat(9)}`;
  assert.equal(nestsDeeperThan(deep, 8), true);
  assert.equal(parseLine(deep, counts), null);
  assert.equal(counts.too_deep, 1);
  const eight = `${"[".repeat(8)}${"]".repeat(8)}`;
  assert.deepEqual(parseLine(eight, counts), JSON.parse(eight));
  const quoted = JSON.stringify({ s: "[[[[[[[[[[[[ \\\" {{{{{{{{{{" });
  assert.equal(nestsDeeperThan(quoted, 8), false);
  assert.equal(parseLine("not json", counts), null);
  assert.equal(counts.not_json, 1);
});
