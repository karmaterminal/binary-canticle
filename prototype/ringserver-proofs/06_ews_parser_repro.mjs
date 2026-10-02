// Proof 06: reproduce ews-concept-new's "Error parsing miniSEED data: Not enought bytes for
// header, need 47, found 6" and show the correct path.
//
// ews (src/routes/realtime/+page.svelte ~598-627 + src/lib/services/WaveformService.ts:129)
// treats ONE WebSocket message as ONE SeedLink packet: it drops the 8-byte "SL" header with
// slice(8) and hands the rest to seisplotjs' miniSEED2 parser. The third-party
// bagusindrayana/seedlink-websocket proxy forwards raw TCP chunks as WS messages, so a message
// can be a coalesced "OK\r\n" reply, a packet plus 6 bytes of the next, two packets, or
// "ERROR\r\n...". ringserver's own /seedlink WebSocket sends exactly one packet per message.
//
// This script captures two real 520-byte SeedLink 3.1 packets from ringserver's /seedlink
// WebSocket, then feeds ews-style messages to the seisplotjs parser.
// Usage: SLPORT=18000 PYTHON=python3 node 06_ews_parser_repro.mjs
globalThis.HTMLElement = class {};
globalThis.customElements = { define() {}, get() {} };
globalThis.window = globalThis;
// seisplotjs' package "exports" hide this subpath, so import the file directly.
const mseed = await import("./node_modules/seisplotjs/dist/miniseed.mjs");
import WebSocket from "ws";
import { execFileSync } from "child_process";

const HOST = process.env.RS_HOST || "127.0.0.1";
const SLPORT = process.env.SLPORT || "18000";
const PYTHON = process.env.PYTHON || "python3";

const packets = [];
const ws = new WebSocket(`ws://${HOST}:${SLPORT}/seedlink`, "SeedLink3.1");
ws.binaryType = "arraybuffer";
ws.on("open", () => {
  for (const c of ["HELLO", "STATION CANT XX", "SELECT LHZ", "DATA", "END"]) ws.send(c + "\r");
  setTimeout(() => execFileSync(PYTHON, ["03_carrier_writer.py", "2"]), 500);
});
ws.on("message", (d) => {
  if (d.byteLength === 520) packets.push(new Uint8Array(d));
  if (packets.length === 2) {
    ws.close();
    run();
  }
});
setTimeout(() => {
  console.error("timed out waiting for packets; is ringserver running with SeedLink+HTTP on", SLPORT, "?");
  process.exit(1);
}, 8000);

function ews(u8) {
  try {
    const recs = mseed.parseDataRecords(u8.buffer.slice(u8.byteOffset, u8.byteOffset + u8.byteLength).slice(8));
    return "ok " + recs.length + " record(s)";
  } catch (e) {
    return String(e);
  }
}
function cat(...parts) {
  const out = new Uint8Array(parts.reduce((s, x) => s + x.length, 0));
  let i = 0;
  for (const x of parts) {
    out.set(x, i);
    i += x.length;
  }
  return out;
}
function run() {
  const enc = (s) => new TextEncoder().encode(s);
  console.log("520 B  one SL packet (ringserver /seedlink WS) ->", ews(packets[0]));
  console.log("526 B  packet + 6 B of next (raw TCP chunk)    ->", ews(cat(packets[0], packets[1].subarray(0, 6))));
  console.log("14 B   'ERROR\\r\\nERROR\\r\\n'                  ->", ews(enc("ERROR\r\nERROR\r\n")));
  console.log("12 B   'OK\\r\\nOK\\r\\nOK\\r\\n'                  ->", ews(enc("OK\r\nOK\r\nOK\r\n")));
  console.log("514 B  tail of a split packet                  ->", ews(packets[1].subarray(6)));
  console.log("1040 B two packets coalesced                   ->", ews(cat(packets[0], packets[1])));
  process.exit(0);
}
