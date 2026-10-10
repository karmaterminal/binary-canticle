// The binding's connection to the host daemon (RFC-0001 §11.1, §14.18.2, D35): a unix SOCK_STREAM client that asks
// for the join snapshot, frames and checks each line, hands records to the Receiver, and reconnects with jittered
// backoff. It never binds a UDP port: the daemon is the host's one listener. Its first line is the only thing it
// ever writes to the socket.
//
// Node cannot read the daemon's SO_PEERCRED, so before each attempt the link checks what it can: the socket is a
// socket, owned by the expected uid, in a directory nobody else can write. The daemon checks this side's uid.

import { lstatSync } from "node:fs";
import net from "node:net";
import { dirname } from "node:path";
import { type FramingCounts, LineFramer, newFramingCounts, parseLine } from "./framing.ts";
import { ProtocolError, type Receiver } from "./receive.ts";
import { JOIN_SNAPSHOT_REQUEST } from "./records.ts";

export type LinkOptions = {
  socketPath: string;
  receiver: Receiver;
  /** The uid that must own the socket and its directory (default: this process's). */
  uid?: number | undefined;
  /** After records were applied or the connection changed: the binding persists what changed. */
  onChange?: () => void;
  log?: (msg: string) => void;
  random?: () => number;
  /** Reconnect backoff (§14.18.2 [PROPOSED DEFAULT]: 1 s doubling to 60 s, jitter 0.2). */
  backoff?: { firstMs: number; maxMs: number; jitter: number };
  /** No record at all for this long is connection loss: three `health` intervals (§14.18.3, *Connection loss*). */
  silenceMs?: number;
  /** A requested join snapshot that has not completed this long after connecting is connection loss. */
  snapshotMs?: number;
  connectMs?: number;
};

const DEFAULT_BACKOFF = { firstMs: 1_000, maxMs: 60_000, jitter: 0.2 };

export class DaemonLink {
  private readonly o: LinkOptions;
  private sock: net.Socket | null = null;
  private stopped = true;
  private attempt = 0;
  private retry: ReturnType<typeof setTimeout> | null = null;
  private silence: ReturnType<typeof setTimeout> | null = null;
  private snapshot: ReturnType<typeof setTimeout> | null = null;
  readonly framing: FramingCounts = newFramingCounts();
  /** When the next attempt is due, while waiting to reconnect. */
  nextAttemptAt: number | null = null;

  constructor(o: LinkOptions) {
    this.o = o;
  }

  start(): void {
    if (!this.stopped) {
      return;
    }
    this.stopped = false;
    this.open();
  }

  stop(): void {
    this.stopped = true;
    if (this.retry !== null) {
      clearTimeout(this.retry);
      this.retry = null;
    }
    this.nextAttemptAt = null;
    const sock = this.sock;
    if (sock !== null) {
      this.drop(sock, "stopped");
    } else {
      this.o.receiver.lost("stopped");
    }
  }

  private open(): void {
    this.retry = null;
    this.nextAttemptAt = null;
    const r = this.o.receiver;
    r.connecting();
    const refused = this.checkSocket();
    if (refused !== null) {
      r.lost(refused);
      this.changed();
      this.schedule();
      return;
    }
    const framer = new LineFramer(this.framing);
    const sock = net.createConnection({ path: this.o.socketPath });
    this.sock = sock;
    sock.setTimeout(this.o.connectMs ?? 5_000, () => this.drop(sock, "connect_timeout"));
    sock.once("connect", () => {
      sock.setTimeout(0);
      sock.write(JOIN_SNAPSHOT_REQUEST);
      r.connected(true);
      this.arm(sock);
      this.snapshot = setTimeout(() => {
        if (this.sock === sock && r.snapshotPending()) {
          this.drop(sock, "snapshot_timeout");
        }
      }, this.o.snapshotMs ?? 10_000);
      this.snapshot.unref();
      this.changed();
    });
    sock.on("data", (chunk: Buffer) => {
      if (this.sock !== sock) {
        return;
      }
      for (const line of framer.push(chunk)) {
        const raw = parseLine(line, this.framing);
        if (raw === null) {
          continue; // over-long, too deep or not JSON: discarded and counted (§14.18.2)
        }
        try {
          r.apply(raw);
        } catch (e) {
          // A protocol violation ends the connection (§14.18.3). So does anything unexpected: it is logged and the
          // link reconnects, and it never escapes into the Gateway's event loop.
          if (!(e instanceof ProtocolError)) {
            this.o.log?.(`canticle: failed to apply a daemon record: ${(e as Error).message}`);
          }
          this.drop(sock, e instanceof ProtocolError ? e.message : "internal_error");
          return;
        }
      }
      if (r.current()) {
        this.attempt = 0;
      }
      this.arm(sock);
      this.changed();
    });
    sock.on("end", () => {
      framer.end();
      this.drop(sock, r.phase() === "hello" ? "closed_before_hello" : "end_of_stream");
    });
    sock.on("error", (e: NodeJS.ErrnoException) => {
      // A daemon that refuses a connection (a uid it does not allow, full, not ready) closes it before hello; the
      // join request written on connect then fails with EPIPE or ECONNRESET.
      const refused = r.phase() === "hello" && (e.code === "EPIPE" || e.code === "ECONNRESET");
      this.drop(sock, refused ? "closed_before_hello" : errorReason(e));
    });
    sock.on("close", () => this.drop(sock, "closed"));
  }

  /** The checks Node can make on the daemon's side of the boundary, or null when they pass. */
  private checkSocket(): string | null {
    const uid = this.o.uid ?? process.getuid?.();
    try {
      const st = lstatSync(this.o.socketPath);
      const dir = lstatSync(dirname(this.o.socketPath));
      if (!st.isSocket()) {
        return "not_a_socket";
      }
      if (uid !== undefined && (st.uid !== uid || dir.uid !== uid)) {
        return "socket_owner";
      }
      if ((dir.mode & 0o022) !== 0) {
        return "socket_dir_writable";
      }
      return null;
    } catch (e) {
      return errorReason(e as NodeJS.ErrnoException);
    }
  }

  private arm(sock: net.Socket): void {
    if (this.silence !== null) {
      clearTimeout(this.silence);
    }
    this.silence = setTimeout(() => this.drop(sock, "silent"), this.o.silenceMs ?? 30_000);
    this.silence.unref();
  }

  private drop(sock: net.Socket, why: string): void {
    if (this.sock !== sock) {
      return;
    }
    this.sock = null;
    for (const t of [this.silence, this.snapshot]) {
      if (t !== null) {
        clearTimeout(t);
      }
    }
    this.silence = null;
    this.snapshot = null;
    sock.removeAllListeners("data");
    sock.destroy();
    this.o.receiver.lost(why);
    this.o.log?.(`canticle: daemon connection ended (${why})`);
    this.changed();
    this.schedule();
  }

  private schedule(): void {
    if (this.stopped || this.retry !== null) {
      return;
    }
    const b = this.o.backoff ?? DEFAULT_BACKOFF;
    const base = Math.min(b.maxMs, b.firstMs * 2 ** Math.min(this.attempt, 16));
    const jitter = 1 + b.jitter * (2 * (this.o.random ?? Math.random)() - 1);
    const delay = Math.max(0, Math.round(base * jitter));
    this.attempt += 1;
    this.nextAttemptAt = Date.now() + delay;
    this.retry = setTimeout(() => this.open(), delay);
    this.retry.unref();
  }

  private changed(): void {
    try {
      this.o.onChange?.();
    } catch (e) {
      this.o.log?.(`canticle: binding update failed: ${(e as Error).message}`);
    }
  }
}

function errorReason(e: NodeJS.ErrnoException): string {
  switch (e.code) {
    case "ENOENT":
    case "ECONNREFUSED":
      return "no_daemon";
    case "EACCES":
    case "EPERM":
      return "permission_denied";
    default:
      return `socket_error:${e.code ?? "unknown"}`;
  }
}
