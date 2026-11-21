#!/usr/bin/env node
// No daemon, plugin config, session logs, timers or network: bounded JSON fixture in, metadata out.
import { pathToFileURL } from "node:url";
import { previewShadow } from "./receptor-shadow.ts";

export async function runShadowCli(): Promise<void> {
  if (process.argv.length !== 2) throw new Error("usage: node src/receptor-shadow-cli.ts < fixture.json");
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk as string);
    size += bytes.length;
    if (size > 1_048_576) throw new Error("fixture exceeds 1 MiB input limit");
    chunks.push(bytes);
  }
  let raw: unknown;
  try { raw = JSON.parse(Buffer.concat(chunks).toString("utf8")); }
  catch { throw new Error("fixture is not valid JSON"); } // never quote a payload in an error
  process.stdout.write(`${JSON.stringify(previewShadow(raw), null, 2)}\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  runShadowCli().catch((error: unknown) => {
    process.stderr.write(`receptor-shadow: ${error instanceof Error ? error.message : "invalid fixture"}\n`);
    process.exitCode = 1;
  });
}
