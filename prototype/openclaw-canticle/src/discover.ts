// RFC-0001 §13: DNS-SD supplies locator hints only. The operator's exact catalog alone names keys and public streams.
import { createHash } from "node:crypto";
import { Resolver } from "node:dns/promises";
import type { BindingConfig } from "./config.ts";

type RecordHint = { type: string; ttl?: number; value?: string; target?: string; name?: string; port?: number; priority?: number; weight?: number; entries?: string[] };
type RecordKind = "PTR" | "SRV" | "TXT";
type TypedResolver = Pick<Resolver, "resolvePtr" | "resolveSrv" | "resolveTxt" | "cancel">;
export type DnsReader = (name: string, kind: RecordKind) => Promise<RecordHint[]>;
const MAX_INSTANCES = 32;
const MAX_RESULTS = 8;
const MAX_RECORDS = 8;
const MAX_CACHE = 128;
const MAX_TTL = 300;
const NEGATIVE_TTL = 60;

export function createSystemDns(makeResolver: () => TypedResolver = () => new Resolver()): DnsReader {
  return async (name, kind) => {
    const resolver = makeResolver();
    let timer: NodeJS.Timeout | undefined;
    try {
      const lookup = kind === "PTR"
        ? resolver.resolvePtr(name).then((rows) => rows.slice(0, MAX_INSTANCES + 1).map((value) => ({ type: kind, value })))
        : kind === "SRV"
          ? resolver.resolveSrv(name).then((rows) => rows.slice(0, MAX_RECORDS).map((row) => ({ type: kind, ...row })))
          : resolver.resolveTxt(name).then((rows) => rows.slice(0, MAX_RECORDS).map((entries) => ({ type: kind, entries })));
      return await Promise.race([
        lookup,
        new Promise<never>((_, reject) => { timer = setTimeout(() => { resolver.cancel(); reject(new Error("DNS timeout")); }, 2000); }),
      ]);
    } catch (e) {
      if (["ENOTFOUND", "ENODATA"].includes((e as NodeJS.ErrnoException).code ?? "")) return [];
      throw e;
    } finally {
      if (timer) clearTimeout(timer);
    }
  };
}

export const systemDns: DnsReader = createSystemDns();

export class Discoverer {
  private cache = new Map<string, { until: number; records: RecordHint[] }>();
  private cfg: BindingConfig["discovery"];
  private dns: DnsReader;
  private now: () => number;
  constructor(cfg: BindingConfig["discovery"], dns: DnsReader = systemDns, now: () => number = Date.now) {
    this.cfg = cfg; this.dns = dns; this.now = now;
  }

  private async query(name: string, kind: RecordKind): Promise<RecordHint[]> {
    const key = `${kind}:${name}`;
    const cached = this.cache.get(key);
    if (cached && cached.until > this.now()) return cached.records;
    const response = await this.dns(name, kind);
    const records = response.filter((r) => r?.type === kind).slice(0, kind === "PTR" ? MAX_INSTANCES + 1 : MAX_RECORDS);
    const ttl = Math.max(1, Math.min(records.length ? MAX_TTL : NEGATIVE_TTL,
      ...records.map((r) => Number.isSafeInteger(r.ttl) && (r.ttl as number) > 0 ? r.ttl as number : NEGATIVE_TTL),
      ...(records.length ? [] : [NEGATIVE_TTL])));
    if (this.cache.size >= MAX_CACHE) this.cache.delete(this.cache.keys().next().value!);
    this.cache.set(key, { until: this.now() + ttl * 1000, records });
    return records;
  }

  async browse(domain: string, stream?: string): Promise<object> {
    if (!this.cfg.domains.includes(domain)) throw new Error("domain is not explicitly configured");
    if (!this.cfg.catalog.length) return { domain, stations: [], truncated: false, authority: "operator catalog; DNS locator hints only" };
    const service = `_canticle._udp.${domain}.`;
    const ptr = await this.query(service, "PTR");
    const stations: object[] = [];
    let outputTruncated = false;
    const seen = new Set<string>();
    for (const row of ptr.slice(0, MAX_INSTANCES)) {
      const instance = String(row.value ?? row.name ?? "").toLowerCase();
      const suffix = `.${service}`;
      if (!instance.endsWith(suffix) || seen.has(instance)) continue;
      seen.add(instance);
      const label = instance.slice(0, -suffix.length);
      if (!/^[a-z][a-z0-9-]{0,30}$/.test(label)) continue;
      const grant = this.cfg.catalog.find((e) => e.name === label);
      if (!grant || !grant.publicStreams.length || (stream && !grant.publicStreams.includes(stream))) continue;
      if (stations.length >= MAX_RESULTS) { outputTruncated = true; break; }
      const [srv, txt] = await Promise.all([this.query(instance, "SRV"), this.query(instance, "TXT")]);
      const hints = new Map<string, string>();
      let invalid = false;
      for (const r of txt) {
        const entries = r.entries;
        if (!Array.isArray(entries) || entries.length > 32 || entries.some((x) => typeof x !== "string") ||
            entries.reduce((n, x) => n + Buffer.byteLength(x), 0) > 4096) { invalid = true; continue; }
        for (const entry of entries) {
          const i = entry.indexOf("=");
          if (i > 0 && i <= 9 && !hints.has(entry.slice(0, i))) hints.set(entry.slice(0, i), entry.slice(i + 1));
        }
      }
      const key = Buffer.from(grant.publicKey, "base64");
      const keyId = createHash("sha256").update(key).digest("hex").slice(0, 16);
      const mismatches: string[] = [];
      if (invalid) mismatches.push("txt-invalid");
      if (hints.has("sid") && hints.get("sid") !== keyId) mismatches.push("sid");
      if (hints.has("k") && hints.get("k") !== `ed25519:${grant.publicKey}`) mismatches.push("k");
      if (hints.has("streams") && hints.get("streams") !== grant.publicStreams.join(",")) mismatches.push("streams");
      const locators: object[] = [];
      for (const r of srv) {
        const target = String(r.target ?? r.name ?? "").toLowerCase();
        if (target.length > 254 || !/^[a-z0-9.-]+\.$/.test(target) || !target.endsWith(`.${domain}.`) ||
            !Number.isInteger(r.port) || r.port! < 1 || r.port! > 65535) {
          mismatches.push("srv-target"); continue;
        }
        locators.push({ target, port: r.port, priority: r.priority ?? 0, weight: r.weight ?? 0 });
      }
      stations.push({ station: grant.name, key_id: keyId,
        public_streams: stream ? [stream] : grant.publicStreams, locators,
        mismatches: [...new Set(mismatches)].sort(),
        ttl: Math.min(row.ttl ?? NEGATIVE_TTL, ...srv.map((x) => x.ttl ?? NEGATIVE_TTL), ...txt.map((x) => x.ttl ?? NEGATIVE_TTL)) });
    }
    return { domain, stations, truncated: ptr.length > MAX_INSTANCES || outputTruncated, authority: "operator catalog; DNS locator hints only" };
  }
}
