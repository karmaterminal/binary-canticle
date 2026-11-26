// Host-owned exposure custody for an explicitly prepared isolated reader. This port fences possible
// exposure; it deliberately cannot confirm a model encounter or grant publication/room authority.
import { createHash } from "node:crypto";
import type { LocalReader } from "./config.ts";
import type { HeardFrame, Tuple } from "./records.ts";

export const EXPOSURE_TOOL_BINDING = "canticle.exposure";
export const EXPOSURE_PORT_VERSION = "canticle-exposure-port/1";

export type PayloadSource = {
  item: Tuple;
  idem: string;
  root: Tuple | null;
  hop: number;
  class: string;
  scope: string | null;
  lens: number | null;
  station: string;
  principal: string | null;
  stream: string;
  stateKey: string | null;
  flags: HeardFrame["flags"];
  times: HeardFrame["times"];
  sourceBody: { ctype: string | number; size: number; sha256: string; textSha256: string | null } | null;
  bodyRef: HeardFrame["body_ref"];
  /** Hash the exact rendered entry, including its host banner and defanged payload. */
  renderedSha256: string;
  renderedBytes: number;
  receiver: { run: string; source: "live" | "snapshot"; journalSequence: number | null; recordSequence: number | null };
};

export type PayloadExposure = {
  version: "canticle-payload-exposure/1";
  binding: string;
  reader: LocalReader;
  toolCallId: string;
  /** This is the complete text returned by the plugin, before any host wrapping or transformation. */
  resultSha256: string;
  resultBytes: number;
  /** Actual output order, not selected-parent-only lineage or a deduplicated maximum-hop summary. */
  sources: readonly PayloadSource[];
};

/** Supplied only through the host's out-of-band toolBindings. No tool argument can create this port.
 * begin must durably fence every source before resolving. Confirmation and recovery belong to the host
 * that can observe actual result custody; successful begin is never a confirmed receipt. */
export type ExposurePort = {
  version: typeof EXPOSURE_PORT_VERSION;
  reader: LocalReader;
  assertCurrent: () => void;
  begin: (exposure: PayloadExposure) => Promise<{ pendingId: string }>;
};

export type ExposureContext = {
  sessionKey?: string;
  sessionId?: string;
  assertInvocationCurrent?: () => void;
  toolBindings?: Readonly<Record<string, unknown>>;
};

export function sha256(text: string): string {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

/** Take provenance from the verified frame owner at selection, never from rendered text. */
export function payloadSource(
  frame: HeardFrame,
  rendered: string,
  receiver: PayloadSource["receiver"],
): PayloadSource {
  return {
    item: { key_id: frame.key_id, epoch: frame.epoch, stream_id: frame.stream_id, seq: frame.seq },
    idem: frame.idem,
    root: frame.root === null ? null : { ...frame.root },
    hop: frame.hop,
    class: frame.class,
    scope: frame.scope,
    lens: frame.lens,
    station: frame.station,
    principal: frame.principal,
    stream: frame.stream,
    stateKey: frame.state_key,
    flags: { ...frame.flags },
    times: { ...frame.times },
    sourceBody: frame.body === null ? null : {
      ctype: frame.body.ctype, size: frame.body.size, sha256: frame.body.sha256,
      textSha256: frame.body.text === undefined ? null : sha256(frame.body.text),
    },
    bodyRef: frame.body_ref === null ? null : { ...frame.body_ref },
    renderedSha256: sha256(rendered),
    renderedBytes: Buffer.byteLength(rendered),
    receiver: { ...receiver },
  };
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Presence is opt-in; malformed or mismatched supplied authority never falls back to legacy reads. */
function portOf(ctx: ExposureContext, reader: LocalReader | null): ExposurePort | null {
  const raw = ctx.toolBindings?.[EXPOSURE_TOOL_BINDING];
  if (raw === undefined) return null;
  if (!reader || !record(raw) || raw.version !== EXPOSURE_PORT_VERSION || !record(raw.reader) ||
      raw.reader.sessionKey !== reader.sessionKey || raw.reader.sessionId !== reader.sessionId ||
      raw.reader.lifecycleRevision !== reader.lifecycleRevision ||
      ctx.sessionKey !== reader.sessionKey || ctx.sessionId !== reader.sessionId ||
      typeof ctx.assertInvocationCurrent !== "function" || typeof raw.assertCurrent !== "function" ||
      typeof raw.begin !== "function") {
    throw new Error("Canticle exposure authority is unavailable for this reader");
  }
  return raw as ExposurePort;
}

/** Called before the tool releases payload. Rejection may follow a durable begin: never clear that fence.
 * The host must reject reads without this binding when its selected mode requires complete history.
 * Legacy taint-only reads remain incapable of asserting complete history for a later publisher. */
export async function fencePayloadExposure(
  ctx: ExposureContext,
  reader: LocalReader | null,
  binding: string,
  toolCallId: string,
  resultText: string,
  sources: readonly PayloadSource[],
): Promise<void> {
  const port = portOf(ctx, reader);
  if (port === null) return;
  if (!toolCallId || sources.length === 0 || !reader) {
    throw new Error("Canticle payload has no attributable exposure source");
  }
  ctx.assertInvocationCurrent!();
  port.assertCurrent();
  const receipt = await port.begin({
    version: "canticle-payload-exposure/1",
    binding,
    reader: { ...reader },
    toolCallId,
    resultSha256: sha256(resultText),
    resultBytes: Buffer.byteLength(resultText),
    sources,
  });
  ctx.assertInvocationCurrent!();
  port.assertCurrent();
  if (!record(receipt) || typeof receipt.pendingId !== "string" || !receipt.pendingId || receipt.pendingId.length > 512) {
    throw new Error("Canticle exposure fence was not acknowledged");
  }
  // No confirmation here: core can still withhold this result after this promise resolves.
}
