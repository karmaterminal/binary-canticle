// Receptor record v1 (RFC-0001 §14.18.3) as this binding reads it: constants, identifiers and the field checks
// a binding applies before it keeps or shows a record. Fields a record carries beyond these are ignored.

import { createHash } from "node:crypto";

export const RECORD_V = "canticle-receptor-record/1";
const RECORD_V_PREFIX = "canticle-receptor-record/";

/** The join-snapshot request, sent as a connection's first line (§14.18.3, *Join snapshot*). */
export const JOIN_SNAPSHOT_REQUEST = `${JSON.stringify({ op: "join_snapshot", v: RECORD_V })}\n`;

const HEX16 = /^[0-9a-f]{16}$/;
const IDEM = /^canticle:[0-9a-f]{16}:\d+:[0-9a-f]{8}:\d+$/;
const NAME_SEGMENT = "[a-z][a-z0-9-]{0,30}";
export const STATION_NAME = new RegExp(`^${NAME_SEGMENT}$`);
export const STREAM_NAME = new RegExp(`^${NAME_SEGMENT}(\\.${NAME_SEGMENT}){0,3}$`);

export type Obj = Record<string, unknown>;

export function isObj(v: unknown): v is Obj {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isInt(v: unknown): v is number {
  return typeof v === "number" && Number.isSafeInteger(v);
}

function optString(v: unknown): string | null | undefined {
  if (v === undefined || v === null) {
    return null;
  }
  return typeof v === "string" ? v : undefined;
}

/** `v` of a record: v1, another major version (the binding stops: `record_version`), or not a record. */
export function versionOf(rec: Obj): "v1" | "other_major" | "invalid" {
  const v = rec.v;
  if (v === RECORD_V) {
    return "v1";
  }
  return typeof v === "string" && v.startsWith(RECORD_V_PREFIX) ? "other_major" : "invalid";
}

/** First 4 bytes, big-endian, of SHA-256("canticle-stream/v2" ‖ 0x00 ‖ name) (RFC-0001 §5.4). */
export function streamIdOf(name: string): number {
  const digest = createHash("sha256").update("canticle-stream/v2\u0000").update(name, "utf8").digest();
  return digest.readUInt32BE(0);
}

/** `canticle:<key_id>:<epoch>:<stream_id as 8 hex digits>:<seq>`, the record v1 `idem` (§14.18.3). */
export function idemOf(keyId: string, epoch: number, streamId: number, seq: number | string): string {
  return `canticle:${keyId}:${epoch}:${streamId.toString(16).padStart(8, "0")}:${seq}`;
}

export type Tuple = { key_id: string; epoch: number; stream_id: number; seq: number | string };

function tupleOf(v: unknown): Tuple | null | undefined {
  if (v === null || v === undefined) {
    return null;
  }
  if (!isObj(v) || typeof v.key_id !== "string" || !HEX16.test(v.key_id) || !isInt(v.epoch) || !isInt(v.stream_id)) {
    return undefined;
  }
  const seq = v.seq;
  if (!isInt(seq) && !(typeof seq === "string" && /^\d+$/.test(seq))) {
    return undefined;
  }
  return { key_id: v.key_id, epoch: v.epoch, stream_id: v.stream_id, seq };
}

export type Body = { ctype: string; size: number; sha256: string; text?: string; base64?: string };
export type BodyRef = { url: string; sha256: string; size: number };

/** A deliverable `frame` record (admission `verified`, disposition `surface`), checked field by field. */
export type HeardFrame = {
  idem: string;
  key_id: string;
  epoch: number;
  stream_id: number;
  seq: number | string;
  station: string;
  principal: string | null;
  stream: string;
  class: string;
  scope: string | null;
  hop: number;
  state_key: string | null;
  purpose: string | null;
  flags: { refresh: boolean; wake_derived: boolean | null; exercise: boolean };
  root: Tuple | null;
  times: {
    issued_at: number;
    expires_at: number;
    received_at: number | null;
    heard_at: number;
    offset_ms: number;
    local_expiry_at: number;
  };
  dedup: "first" | "resurfaced";
  bytes: number | null;
  body: Body | null;
  body_ref: BodyRef | null;
};

export function isDeliverable(rec: Obj): boolean {
  return rec.admission === "verified" && rec.disposition === "surface";
}

function bodyOf(v: unknown): Body | null | undefined {
  if (v === undefined || v === null) {
    return null;
  }
  if (!isObj(v) || typeof v.ctype !== "string" || !isInt(v.size) || typeof v.sha256 !== "string") {
    return undefined;
  }
  const out: Body = { ctype: v.ctype, size: v.size, sha256: v.sha256 };
  if (typeof v.text === "string") {
    out.text = v.text;
  } else if (typeof v.base64 === "string") {
    out.base64 = v.base64;
  } else {
    return undefined;
  }
  return out;
}

function bodyRefOf(v: unknown): BodyRef | null | undefined {
  if (v === undefined || v === null) {
    return null;
  }
  if (!isObj(v) || typeof v.url !== "string" || typeof v.sha256 !== "string" || !isInt(v.size)) {
    return undefined;
  }
  return { url: v.url, sha256: v.sha256, size: v.size };
}

/** A deliverable frame's fields, or null when a field a binding needs is missing or of the wrong type
 * (`malformed_record`: dropped, counted, never delivered; §14.18.3 *Fail-closed rules*). */
export function heardFrameOf(rec: Obj): HeardFrame | null {
  const fr = rec.frame;
  const st = rec.station;
  const times = rec.times;
  if (typeof rec.idem !== "string" || !IDEM.test(rec.idem) || !isObj(fr) || !isObj(st) || !isObj(times)) {
    return null;
  }
  const t = tupleOf(fr);
  if (!t || fr.kind !== "item" || rec.idem !== idemOf(t.key_id, t.epoch, t.stream_id, t.seq)) {
    return null;
  }
  const principal = optString(st.principal);
  const scope = optString(rec.scope);
  const stateKey = optString(rec.state_key);
  const purpose = optString(rec.purpose);
  if (typeof st.name !== "string" || principal === undefined || typeof rec.stream !== "string") {
    return null;
  }
  if (typeof rec.class !== "string" || !isInt(rec.hop) || scope === undefined || stateKey === undefined) {
    return null;
  }
  if (purpose === undefined || (rec.dedup !== "first" && rec.dedup !== "resurfaced")) {
    return null;
  }
  const { issued_at, expires_at, heard_at, local_expiry_at } = times;
  if (!isInt(issued_at) || !isInt(expires_at) || !isInt(heard_at) || !isInt(local_expiry_at)) {
    return null;
  }
  const receivedAt = times.received_at;
  const offset = times.offset_ms;
  if ((receivedAt !== undefined && receivedAt !== null && !isInt(receivedAt)) || (offset !== undefined && !isInt(offset))) {
    return null;
  }
  const body = bodyOf(rec.body);
  const bodyRef = bodyRefOf(rec.body_ref);
  const root = isObj(rec.lineage) ? tupleOf(rec.lineage.root) : null;
  if (body === undefined || bodyRef === undefined || root === undefined || (body === null && bodyRef === null)) {
    return null;
  }
  const flags = isObj(rec.flags) ? rec.flags : {};
  const bytes = fr.bytes;
  return {
    idem: rec.idem,
    key_id: t.key_id,
    epoch: t.epoch,
    stream_id: t.stream_id,
    seq: t.seq,
    station: st.name,
    principal,
    stream: rec.stream,
    class: rec.class,
    scope,
    hop: rec.hop,
    state_key: stateKey,
    purpose,
    // A frame whose wake_derived flag is not stated is not known to be free of it (frond-ear#66's rule).
    flags: {
      refresh: flags.refresh === true,
      wake_derived: typeof flags.wake_derived === "boolean" ? flags.wake_derived : null,
      exercise: flags.exercise === true,
    },
    root,
    times: {
      issued_at,
      expires_at,
      received_at: isInt(receivedAt) ? receivedAt : null,
      heard_at,
      offset_ms: isInt(offset) ? offset : 0,
      local_expiry_at,
    },
    dedup: rec.dedup,
    bytes: isInt(bytes) ? bytes : null,
    body,
    body_ref: bodyRef,
  };
}

export type Presence = {
  key_id: string;
  station: string | null;
  principal: string | null;
  state: string;
  last_beacon_at: number | null;
};

/** A §8.6 presence state (EQUIPPED_SPEAKING, UNOBSERVABLE:signed_off, ...), or "other" for anything unrecognised. */
export function presenceState(v: unknown): string {
  return typeof v === "string" && /^[A-Z][A-Z_]{0,39}(:[a-z_]{1,20})?$/.test(v) ? v : "other";
}

export function presenceOf(rec: Obj): Presence | null {
  const st = rec.station;
  if (typeof rec.key_id !== "string" || !HEX16.test(rec.key_id) || typeof rec.state !== "string" || !isObj(st)) {
    return null;
  }
  const name = optString(st.name);
  const principal = optString(st.principal);
  const lastBeacon = rec.last_beacon_at;
  if (name === undefined || principal === undefined || (lastBeacon !== null && lastBeacon !== undefined && !isInt(lastBeacon))) {
    return null;
  }
  return {
    key_id: rec.key_id,
    station: name,
    principal,
    state: presenceState(rec.state),
    last_beacon_at: isInt(lastBeacon) ? lastBeacon : null,
  };
}

export type Retract = { idem: string; reason: string; target: Tuple; by: Tuple | null };

export function retractOf(rec: Obj): Retract | null {
  const target = tupleOf(rec.target);
  const by = tupleOf(rec.by);
  if (typeof rec.idem !== "string" || !IDEM.test(rec.idem) || typeof rec.reason !== "string" || !target || by === undefined) {
    return null;
  }
  if (rec.idem !== idemOf(target.key_id, target.epoch, target.stream_id, target.seq)) {
    return null;
  }
  return { idem: rec.idem, reason: reasonCode(rec.reason), target, by };
}

export type DaemonHealth = { state: string; reasons: string[]; beacon_age_ms: Record<string, number> };

/** A daemon-written reason code as shown on status surfaces: a short token, or "other". */
export function reasonCode(v: unknown): string {
  return typeof v === "string" && /^[a-z][a-z0-9_.:-]{0,59}$/.test(v) ? v : "other";
}

export function healthOf(rec: Obj): DaemonHealth | null {
  if (typeof rec.state !== "string" || !Array.isArray(rec.reasons) || !rec.reasons.every((r) => typeof r === "string")) {
    return null;
  }
  const ages: Record<string, number> = {};
  if (isObj(rec.beacon_age_ms)) {
    for (const [k, v] of Object.entries(rec.beacon_age_ms)) {
      if (HEX16.test(k) && isInt(v)) {
        ages[k] = v;
      }
    }
  }
  return { state: reasonCode(rec.state), reasons: rec.reasons.slice(0, 8).map(reasonCode), beacon_age_ms: ages };
}

export type Landing = { mute: unknown; breaker: string | null; until: number | null };

export function landingOf(rec: Obj): Landing {
  return {
    mute: rec.mute ?? null,
    breaker: typeof rec.breaker === "string" ? rec.breaker : null,
    until: isInt(rec.until) ? rec.until : null,
  };
}
