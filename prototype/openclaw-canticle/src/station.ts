// A client of the station's control socket (prototype/canticle-station/canticle/runner.py): one JSON line in, one
// JSON line out, on a unix socket the station keeps to its own uid. The station holds the key (D35: never this
// process), assigns epoch and seq, signs, and runs the carousel; this client only asks it to.
//
// What the answer means for the request is the whole point of the three outcomes below. A request that was never
// written did not happen. A request that was written and got no complete reply may have happened, so it is never
// sent again: the outbox marks its row `unknown` and waits for evidence.

import { lstatSync } from "node:fs";
import net from "node:net";
import { type Obj, isObj } from "./records.ts";

export type StationAnswer =
  | { kind: "reply"; reply: Obj }
  | { kind: "unreachable"; reason: string }
  | { kind: "unknown"; reason: string };

const REPLY_MAX = 64 * 1024;

export type StationClient = (req: Obj) => Promise<StationAnswer>;

/** A client for the control socket at ``path``, which must be a socket owned by ``uid`` (default: this process). */
export function stationClient(path: string, opts: { uid?: number | undefined; timeoutMs?: number } = {}): StationClient {
  return (req) => request(path, req, opts.uid ?? process.getuid?.(), opts.timeoutMs ?? 5_000);
}

function request(path: string, req: Obj, uid: number | undefined, timeoutMs: number): Promise<StationAnswer> {
  try {
    const st = lstatSync(path);
    if (!st.isSocket()) {
      return Promise.resolve({ kind: "unreachable", reason: "not_a_socket" });
    }
    if (uid !== undefined && st.uid !== uid) {
      return Promise.resolve({ kind: "unreachable", reason: "socket_owner" });
    }
  } catch (e) {
    return Promise.resolve({ kind: "unreachable", reason: reasonOf(e as NodeJS.ErrnoException) });
  }
  return new Promise((resolve) => {
    let sent = false;
    let done = false;
    const parts: Buffer[] = [];
    let size = 0;
    const sock = net.createConnection({ path });
    const finish = (a: StationAnswer): void => {
      if (!done) {
        done = true;
        sock.destroy();
        resolve(a);
      }
    };
    const lostAs = (reason: string): StationAnswer => (sent ? { kind: "unknown", reason } : { kind: "unreachable", reason });
    sock.setTimeout(timeoutMs, () => finish(lostAs("timeout")));
    sock.once("connect", () => {
      sent = true;
      sock.write(`${JSON.stringify(req)}\n`);
    });
    sock.on("data", (chunk: Buffer) => {
      const nl = chunk.indexOf(0x0a);
      parts.push(nl === -1 ? chunk : chunk.subarray(0, nl));
      size += nl === -1 ? chunk.length : nl;
      if (size > REPLY_MAX) {
        finish({ kind: "unknown", reason: "reply_too_long" });
      } else if (nl !== -1) {
        let reply: unknown = null;
        try {
          reply = JSON.parse(Buffer.concat(parts).toString("utf8")) as unknown;
        } catch {
          // handled below
        }
        finish(isObj(reply) && typeof reply.ok === "boolean" ? { kind: "reply", reply } : { kind: "unknown", reason: "bad_reply" });
      }
    });
    sock.once("end", () => finish(lostAs("no_reply")));
    sock.once("error", (e: NodeJS.ErrnoException) => finish(lostAs(reasonOf(e))));
    sock.once("close", () => finish(lostAs("closed")));
  });
}

function reasonOf(e: NodeJS.ErrnoException): string {
  switch (e.code) {
    case "ENOENT":
    case "ECONNREFUSED":
      return "no_station";
    case "EACCES":
    case "EPERM":
      return "permission_denied";
    default:
      return `socket_error:${e.code ?? "unknown"}`;
  }
}
