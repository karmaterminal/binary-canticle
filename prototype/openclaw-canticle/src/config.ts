// The plugin's configuration (`plugins.entries.canticle.config`). The manifest's JSON Schema checks shape and bounds
// only, so a bad value can never refuse Gateway boot (RFC-0001 §14.18.7). Everything else is checked here, when the
// service starts; a failure fails the canticle service with a reason, never the Gateway.

import { isAbsolute, join } from "node:path";
import { type Obj, STATION_NAME, isObj } from "./records.ts";

export type Tune = { station: string; stream: string };

export type BindingConfig = {
  /** This binding's name: unique among the bindings on one host, and part of every id it issues. */
  binding: string;
  daemon: { socket: string; uid: number | null };
  stateDir: string | null;
  /** This binding's own station, when it has one: its frames are `self` and confirm outbox rows. */
  station: { name: string; keyId: string } | null;
  /** payloadSessions: the session keys that may read heard text (patterns: "*", an exact key, or a prefix ending in
   * "*"). Every other session reads digests only. */
  listen: { tune: Tune[]; includeSelf: boolean; payloadSessions: string[] };
  journal: { maxEntries: number; maxBytes: number; maxAgeMs: number };
  publish: {
    enabled: boolean;
    socket: string | null;
    uid: number | null;
    classes: string[];
    perMinute: number;
    perHour: number;
    maxLive: number;
  };
  delivery: { mode: "explicit" };
};

export class ConfigError extends Error {}

/** Classes a session may ask for. alarm, regulatory and control are never offered to sessions (§15.1, §10.4). */
export const SESSION_CLASSES = ["chatter", "ambient", "live-state", "advisory", "finding-ref", "root"] as const;

const KEY_ID = /^[0-9a-f]{16}$/;
const STREAM_PATTERN = /^(\*|[a-z][a-z0-9-]{0,30}(\.[a-z][a-z0-9-]{0,30}){0,3}(\.\*)?)$/;

export function parseConfig(raw: unknown): BindingConfig {
  const c = obj(raw ?? {}, "config");
  const binding = str(c.binding, "binding");
  if (!STATION_NAME.test(binding)) {
    throw new ConfigError("binding: lowercase letters, digits and -, starting with a letter, at most 31 characters");
  }
  const d = obj(c.daemon, "daemon");
  const socket = absPath(d.socket, "daemon.socket");
  const stationRaw = c.station === undefined ? null : obj(c.station, "station");
  let station: BindingConfig["station"] = null;
  if (stationRaw !== null) {
    const name = str(stationRaw.name, "station.name");
    const keyId = str(stationRaw.keyId, "station.keyId");
    if (!STATION_NAME.test(name)) {
      throw new ConfigError("station.name: not a station name");
    }
    if (!KEY_ID.test(keyId)) {
      throw new ConfigError("station.keyId: 16 lowercase hex digits (the key id `canticle keygen` prints)");
    }
    station = { name, keyId };
  }
  const l = c.listen === undefined ? {} : obj(c.listen, "listen");
  const tune = (l.tune === undefined ? ["*:*"] : strList(l.tune, "listen.tune")).map(parseTune);
  const j = c.journal === undefined ? {} : obj(c.journal, "journal");
  const p = c.publish === undefined ? {} : obj(c.publish, "publish");
  const enabled = p.enabled === undefined ? false : bool(p.enabled, "publish.enabled");
  if (enabled && station === null) {
    throw new ConfigError("publish.enabled needs station.name and station.keyId: a binding sings only as its own pinned key");
  }
  const classes = p.classes === undefined ? ["chatter"] : strList(p.classes, "publish.classes");
  for (const k of classes) {
    if (!(SESSION_CLASSES as readonly string[]).includes(k)) {
      throw new ConfigError(`publish.classes: ${k} is not offered to sessions (${SESSION_CLASSES.join(", ")})`);
    }
  }
  const delivery = c.delivery === undefined ? {} : obj(c.delivery, "delivery");
  if (delivery.mode !== undefined && delivery.mode !== "explicit") {
    throw new ConfigError("delivery.mode: only \"explicit\" exists in this version; push and wake delivery are a separate opt-in");
  }
  return {
    binding,
    daemon: { socket, uid: d.uid === undefined ? null : int(d.uid, "daemon.uid", 0, 2 ** 31) },
    stateDir: c.stateDir === undefined ? null : absPath(c.stateDir, "stateDir"),
    station,
    listen: {
      tune,
      includeSelf: l.includeSelf === undefined ? false : bool(l.includeSelf, "listen.includeSelf"),
      payloadSessions: l.payloadSessions === undefined ? [] : sessionPatterns(l.payloadSessions, "listen.payloadSessions"),
    },
    journal: {
      maxEntries: j.maxEntries === undefined ? 5_000 : int(j.maxEntries, "journal.maxEntries", 100, 100_000),
      maxBytes: j.maxBytes === undefined ? 8 * 1024 * 1024 : int(j.maxBytes, "journal.maxBytes", 65_536, 256 * 1024 * 1024),
      maxAgeMs: (j.maxAgeHours === undefined ? 24 : int(j.maxAgeHours, "journal.maxAgeHours", 1, 24 * 30)) * 3_600_000,
    },
    publish: {
      enabled,
      socket: enabled ? absPath(p.socket, "publish.socket") : null,
      uid: p.uid === undefined ? null : int(p.uid, "publish.uid", 0, 2 ** 31),
      classes,
      perMinute: p.perMinute === undefined ? 5 : int(p.perMinute, "publish.perMinute", 1, 5),
      perHour: p.perHour === undefined ? 60 : int(p.perHour, "publish.perHour", 1, 60),
      maxLive: p.maxLive === undefined ? 16 : int(p.maxLive, "publish.maxLive", 1, 64),
    },
    delivery: { mode: "explicit" },
  };
}

/** Where this binding keeps its files: the configured directory, or `<OpenClaw state dir>/canticle/<binding>`. */
export function stateRootOf(cfg: BindingConfig, hostStateDir: string): string {
  return cfg.stateDir ?? join(hostStateDir, "canticle", cfg.binding);
}

export function parseTune(text: string): Tune {
  const i = text.indexOf(":");
  const station = i === -1 ? "" : text.slice(0, i);
  const stream = i === -1 ? "" : text.slice(i + 1);
  if ((station !== "*" && !STATION_NAME.test(station)) || !STREAM_PATTERN.test(stream)) {
    throw new ConfigError(`listen.tune: ${JSON.stringify(text)} is not station:stream (either side may be *, a stream may end in .*)`);
  }
  return { station, stream };
}

/** Whether a session key matches one of the patterns: "*", an exact key, or a prefix ending in "*". */
export function sessionMatches(patterns: string[], sessionKey: string): boolean {
  const k = sessionKey.toLowerCase();
  return patterns.some((p) => p === "*" || p === k || (p.endsWith("*") && k.startsWith(p.slice(0, -1))));
}

function sessionPatterns(v: unknown, at: string): string[] {
  const list = strList(v, at);
  if (list.length > 64) {
    throw new ConfigError(`${at}: at most 64 patterns`);
  }
  for (const p of list) {
    if (!/^(\*|[^\s*]{1,200}\*?)$/.test(p)) {
      throw new ConfigError(`${at}: ${JSON.stringify(p)} is not a session key, a prefix ending in *, or *`);
    }
  }
  return list.map((p) => p.toLowerCase());
}

export function tuned(tune: Tune[], station: string, stream: string): boolean {
  return tune.some(
    (t) =>
      (t.station === "*" || t.station === station) &&
      (t.stream === "*" || t.stream === stream || (t.stream.endsWith(".*") && stream.startsWith(t.stream.slice(0, -1)))),
  );
}

function obj(v: unknown, at: string): Obj {
  if (!isObj(v)) {
    throw new ConfigError(`${at}: expected an object`);
  }
  return v;
}

function str(v: unknown, at: string): string {
  if (typeof v !== "string" || v === "") {
    throw new ConfigError(`${at}: expected a string`);
  }
  return v;
}

function strList(v: unknown, at: string): string[] {
  if (!Array.isArray(v) || !v.every((x) => typeof x === "string")) {
    throw new ConfigError(`${at}: expected a list of strings`);
  }
  return v as string[];
}

function bool(v: unknown, at: string): boolean {
  if (typeof v !== "boolean") {
    throw new ConfigError(`${at}: expected true or false`);
  }
  return v;
}

function int(v: unknown, at: string, min: number, max: number): number {
  if (typeof v !== "number" || !Number.isSafeInteger(v) || v < min || v > max) {
    throw new ConfigError(`${at}: expected an integer from ${min} to ${max}`);
  }
  return v;
}

function absPath(v: unknown, at: string): string {
  const s = str(v, at);
  if (!isAbsolute(s)) {
    throw new ConfigError(`${at}: expected an absolute path (no ~ expansion)`);
  }
  return s;
}
