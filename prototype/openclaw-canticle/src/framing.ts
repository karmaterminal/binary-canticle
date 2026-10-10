// Record v1 framing on the binding side (RFC-0001 §14.18.2): one JSON object per line, at most 64 KiB per line
// with its newline, and nesting depth 8. An over-long line is discarded up to its newline and counted, a deeper
// object is refused before it is parsed, and a partial line at the end of a stream is discarded.

export const MAX_LINE = 64 * 1024; // bytes, newline included (§14.18.2 [PROPOSED DEFAULT])
export const MAX_DEPTH = 8; // JSON nesting depth (§14.18.2 [PROPOSED DEFAULT])

export type FramingCounts = {
  overlong: number;
  too_deep: number;
  not_json: number;
  partial_at_end: number;
};

export function newFramingCounts(): FramingCounts {
  return { overlong: 0, too_deep: 0, not_json: 0, partial_at_end: 0 };
}

/** Splits a byte stream into lines of at most MAX_LINE bytes (newline included). */
export class LineFramer {
  private parts: Buffer[] = [];
  private size = 0;
  private discarding = false;
  readonly counts: FramingCounts;

  constructor(counts: FramingCounts = newFramingCounts()) {
    this.counts = counts;
  }

  /** The complete lines in ``chunk`` (without their newline). Over-long lines are dropped and counted. */
  push(chunk: Buffer): string[] {
    const lines: string[] = [];
    let start = 0;
    while (start < chunk.length) {
      const nl = chunk.indexOf(0x0a, start);
      const end = nl === -1 ? chunk.length : nl;
      const piece = chunk.subarray(start, end);
      if (!this.discarding) {
        // The limit counts the newline, so a line may hold MAX_LINE - 1 bytes before it.
        if (this.size + piece.length > MAX_LINE - 1) {
          this.discarding = true;
          this.parts = [];
          this.size = 0;
        } else if (piece.length > 0) {
          this.parts.push(piece);
          this.size += piece.length;
        }
      }
      if (nl === -1) {
        break;
      }
      if (this.discarding) {
        this.counts.overlong += 1;
        this.discarding = false;
      } else {
        lines.push(Buffer.concat(this.parts, this.size).toString("utf8"));
      }
      this.parts = [];
      this.size = 0;
      start = nl + 1;
    }
    return lines;
  }

  /** End of stream: a line without its newline is never a record. */
  end(): void {
    if (this.size > 0 || this.discarding) {
      this.counts.partial_at_end += 1;
    }
    this.parts = [];
    this.size = 0;
    this.discarding = false;
  }
}

/** Whether ``text`` nests objects and arrays deeper than ``max``, found without parsing it. */
export function nestsDeeperThan(text: string, max: number): boolean {
  let depth = 0;
  let inString = false;
  for (let i = 0; i < text.length; i += 1) {
    const c = text.charCodeAt(i);
    if (inString) {
      if (c === 0x5c) {
        i += 1; // the escaped character, whatever it is
      } else if (c === 0x22) {
        inString = false;
      }
    } else if (c === 0x22) {
      inString = true;
    } else if (c === 0x7b || c === 0x5b) {
      depth += 1;
      if (depth > max) {
        return true;
      }
    } else if (c === 0x7d || c === 0x5d) {
      depth -= 1;
    }
  }
  return false;
}

/** One line as a JSON value, or null (counted) when it is too deep or not JSON. */
export function parseLine(line: string, counts: FramingCounts): unknown {
  if (nestsDeeperThan(line, MAX_DEPTH)) {
    counts.too_deep += 1;
    return null;
  }
  try {
    return JSON.parse(line) as unknown;
  } catch {
    counts.not_json += 1;
    return null;
  }
}
