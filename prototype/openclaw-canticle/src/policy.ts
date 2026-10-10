// Content policy for what a session asks to sing (RFC-0001 §15.4 item 6): refuse text that carries a credential or a
// long high-entropy string. A refusal names the kind of finding and never the matched text.

const PATTERNS: [string, RegExp][] = [
  ["github_token", /\bgh[pousr]_[A-Za-z0-9]{30,}/],
  ["github_token", /\bgithub_pat_[A-Za-z0-9_]{40,}/],
  ["api_key", /\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}/],
  ["slack_token", /\bxox[abposr]-[A-Za-z0-9-]{10,}/],
  ["aws_key", /\b(?:AKIA|ASIA)[0-9A-Z]{16}\b/],
  ["google_key", /\bAIza[0-9A-Za-z_-]{35}\b/],
  ["private_key", /-----BEGIN [A-Z ]*PRIVATE KEY-----/],
  ["discord_token", /\b[MNO][A-Za-z\d_-]{23,27}\.[A-Za-z\d_-]{6}\.[A-Za-z\d_-]{27,}/],
  ["jwt", /\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}/],
];

const TOKEN = /[A-Za-z0-9+/=_-]{32,}/g;
const ENTROPY_BITS = 4.2; // per character; a hex digest (at most 4.0) passes, random base64 does not

/** The kinds of secret-like content in ``text`` (empty when there is none). */
export function secretFindings(text: string): string[] {
  const found = new Set<string>();
  for (const [kind, re] of PATTERNS) {
    if (re.test(text)) {
      found.add(kind);
    }
  }
  for (const m of text.matchAll(TOKEN)) {
    if (entropy(m[0]) > ENTROPY_BITS) {
      found.add("high_entropy");
      break;
    }
  }
  return [...found].sort();
}

function entropy(s: string): number {
  const counts = new Map<string, number>();
  for (const c of s) {
    counts.set(c, (counts.get(c) ?? 0) + 1);
  }
  let h = 0;
  for (const n of counts.values()) {
    const p = n / s.length;
    h -= p * Math.log2(p);
  }
  return h;
}
