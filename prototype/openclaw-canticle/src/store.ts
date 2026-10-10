// Files under one binding's state root: atomic JSON replacement, and the lease that keeps a second binding off
// the same root. Everything this plugin keeps lives under that root and nowhere else (RFC-0001 §14.18.7, *Trust
// tier*: its own state directory, no host stores).

import { createHash } from "node:crypto";
import { closeSync, fsyncSync, mkdirSync, openSync, readFileSync, realpathSync, renameSync, unlinkSync, writeSync } from "node:fs";
import net from "node:net";
import { dirname, join } from "node:path";

/** Replace ``path`` with ``value`` as JSON: write a temporary file, flush it, rename it over, flush the directory. */
export function writeJsonAtomic(path: string, value: unknown): void {
  const tmp = `${path}.tmp`;
  const fd = openSync(tmp, "w", 0o600);
  try {
    writeSync(fd, `${JSON.stringify(value)}\n`);
    fsyncSync(fd);
  } finally {
    closeSync(fd);
  }
  renameSync(tmp, path);
  syncDir(dirname(path));
}

export function syncDir(dir: string): void {
  let fd: number | null = null;
  try {
    fd = openSync(dir, "r");
    fsyncSync(fd);
  } catch {
    // Some filesystems refuse to fsync a directory; the rename is still atomic.
  } finally {
    if (fd !== null) {
      closeSync(fd);
    }
  }
}

/** The parsed JSON at ``path``, or null when there is no such file. Anything else unreadable throws. */
export function readJson(path: string): unknown {
  let text: string;
  try {
    text = readFileSync(path, "utf8");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") {
      return null;
    }
    throw e;
  }
  return JSON.parse(text) as unknown;
}

export function ensureDir(dir: string): void {
  mkdirSync(dir, { recursive: true, mode: 0o700 });
}

export class LeaseHeld extends Error {}

/** The longest socket path every platform takes: macOS's 104-byte sun_path, less its terminating NUL. */
const SOCKET_PATH_MAX = 103;

/** A lease on a state root: a unix socket that listens for as long as the binding runs. A second binding on the
 * same root finds it taken and refuses to start, and the kernel releases it when the process dies, so a crash
 * leaves nothing to clean up.
 *
 * On Linux the socket is abstract, named after the root's real path: binding the name is atomic, and the name fits
 * however long the path is (a socket file in a deep state directory would not). An abstract name has no owner and
 * belongs to a network namespace: any process in the namespace can take it first, which keeps the binding from
 * starting (it fails closed), and Gateways in two namespaces that share one root do not see each other.
 *
 * Elsewhere it is `<root>/lease.sock`: a stale file left by a crashed process answers nothing and is replaced, and
 * two bindings that start on one root in the same instant can both pass that check (Node has no flock); the state
 * file's binding name still refuses a binding of another name. */
export class Lease {
  private server: net.Server | null = null;
  private readonly root: string;
  private readonly platform: NodeJS.Platform;
  /** Where the lease listens, once acquire() has resolved the root. */
  path: string | null = null;
  onError: ((e: Error) => void) | null = null;

  constructor(root: string, platform: NodeJS.Platform = process.platform) {
    this.root = root;
    this.platform = platform;
  }

  async acquire(): Promise<void> {
    const real = realpathSync(this.root);
    const abstract = this.platform === "linux";
    const path = abstract
      ? `\0openclaw-canticle-lease:${createHash("sha256").update(real).digest("hex").slice(0, 32)}`
      : join(real, "lease.sock");
    this.path = path;
    if (!abstract) {
      if (Buffer.byteLength(path) > SOCKET_PATH_MAX) {
        throw new Error(`the lease socket ${path} is longer than ${SOCKET_PATH_MAX} bytes; choose a shorter stateDir`);
      }
      if (await answers(path)) {
        throw new LeaseHeld(`another binding holds ${path}`);
      }
      try {
        unlinkSync(path);
      } catch (e) {
        if ((e as NodeJS.ErrnoException).code !== "ENOENT") {
          throw e;
        }
      }
    }
    const server = net.createServer((c) => c.destroy());
    await new Promise<void>((resolve, reject) => {
      server.once("error", (e: NodeJS.ErrnoException) =>
        reject(e.code === "EADDRINUSE" ? new LeaseHeld(`another binding holds the lease on ${real}`) : e),
      );
      server.listen(path, () => resolve());
    });
    server.on("error", (e: Error) => this.onError?.(e)); // an error after listening must not reach the event loop
    server.unref();
    this.server = server;
  }

  async release(): Promise<void> {
    const server = this.server;
    this.server = null;
    if (server !== null) {
      await new Promise<void>((resolve) => server.close(() => resolve()));
    }
  }
}

function answers(path: string): Promise<boolean> {
  return new Promise((resolve) => {
    const c = net.createConnection({ path });
    c.once("connect", () => {
      c.destroy();
      resolve(true);
    });
    c.once("error", () => resolve(false));
  });
}
