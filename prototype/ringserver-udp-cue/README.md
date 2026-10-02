# Ringserver UDP-cue receptor prototype

## Native verdict

**Ringserver does not natively accept UDP cues.** This verdict is based on
EarthScope Ringserver **4.5.4**, tag `v4.5.4`, commit
[`2df558c`](https://github.com/EarthScope/ringserver/commit/2df558cdb480489dcdddf740ae8724076db20db3),
inspected 2026-07-25:

- The tagged
  [`README.md:3-5`](https://github.com/EarthScope/ringserver/blob/v4.5.4/README.md#L3-L5)
  says all supported protocols are TCP-based. Its
  [`README.md:73-75`](https://github.com/EarthScope/ringserver/blob/v4.5.4/README.md#L73-L75)
  names only TCP DataLink and the local miniSEED filesystem scanner as packet
  submission mechanisms.
- The tagged protocol enum contains only DataLink, SeedLink, and HTTP
  ([`src/ringserver.h:36-44`](https://github.com/EarthScope/ringserver/blob/v4.5.4/src/ringserver.h#L36-L44)).
  The sole listener initializer sets `SOCK_STREAM` and calls `listen(2)`
  ([`src/config.c:2634-2719`](https://github.com/EarthScope/ringserver/blob/v4.5.4/src/config.c#L2634-L2719)).
- The tagged manual explicitly states that all communications use TCP and
  DataLink is the submission protocol
  ([`doc/ringserver.md:26-33`](https://github.com/EarthScope/ringserver/blob/v4.5.4/doc/ringserver.md#L26-L33)).
- The authoritative FDSN
  [SeedLink v4 protocol](https://docs.fdsn.org/projects/seedlink/en/latest/protocol.html)
  says SeedLink communication and sessions use TCP/IP connections.

Therefore this package implements a **custom Binary Canticle UDP cue**, not
standard SeedLink. Ringserver remains an unmodified, downstream TCP DataLink
target behind a private publisher interface.

## Implemented boundary

The datagram is canonical JSON with a hard 1,200-byte packet limit and a
512-byte notice-object limit. The schema is closed:

```text
version, issuer, key_id, signature,
notice: kind, subject, notice_id, issued_at, expires_at
```

`subject` must be a lowercase `sha256:` digest; no arbitrary payload field
exists. As a result, notices cannot represent raw Tier-1 objects, filesystem
paths, bearer values, retrieval routes, transcripts, graph mutations, or
artifact data. Unknown or extra fields are rejected.

Ed25519 signs the canonical unsigned envelope using `cryptography>=45`.
Missing cryptographic support prevents package startup; there is no insecure
fallback. Active issuer/key policy, a 60-second maximum TTL, five seconds of
future clock skew, persistent bounded replay claims, and persistent subject
tombstones are enforced before the private publisher handoff.

Receipts are typed `accept`, `reject`, or `quarantine` values with closed
reason enums and no notice data. The UDP listener can bind only an IPv4
loopback address. Replay claims are persisted before publication, so the seam
is an at-most-once publication *attempt*: publisher failure is quarantined and
is not retried under the same replay identity. This is deliberately not a
delivery or exactly-once guarantee.

From this directory, run the focused tests:

```bash
python3 -m unittest discover -s tests -v
```

Run the local receptor in receipt-only adapter-test mode:

```bash
python3 -m canticle_receptor \
  --issuer issuer-a \
  --key-id key-a \
  --public-key-hex <64-hex-character-ed25519-public-key> \
  --state ./receptor-state.sqlite3 \
  --host 127.0.0.1 \
  --port 9999
```

The CLI's receipt-only publisher proves receptor operation but does not claim
DataLink publication. A production adapter must implement the private
`DataLinkPublisher.publish(VerifiedNotice)` seam.

## Native runtime proof status

The environment has no `ringserver`, `dalitool`, `slinktool`, or `dlclient`
binary, so no honest Ringserver writer/reader proof was run. The missing
runtime dependencies are EarthScope Ringserver 4.5.4 and a DataLink client
capable of both writing and reading (for example `simpledali` 0.8.3 plus
`dalitool`).

Once those binaries are provisioned, the exact next proof is:

```bash
proof_dir="$(mktemp -d)"
mkdir "$proof_dir/ring"
RS_ACCEPT_IP=127.0.0.1/32 \
RS_WRITE_IP=127.0.0.1/32 \
RS_TRUSTED_IP=127.0.0.1/32 \
ringserver -Rd "$proof_dir/ring" -Rs 1M -Rp 1200 -VOLATILE -DL 16000
```

In a second shell, start a metadata-only reader:

```bash
dalitool -p -m '^BC_CUE/JSON$' 127.0.0.1:16000
```

Then write one non-sensitive JSON smoke packet using the official
`simpledali` socket API:

```bash
python3 -m venv "$proof_dir/venv"
"$proof_dir/venv/bin/pip" install simpledali==0.8.3
"$proof_dir/venv/bin/python" - <<'PY'
import asyncio
import simpledali

async def main():
    async with simpledali.SocketDataLink("127.0.0.1", 16000) as dali:
        await dali.id("canticle-smoke", "local", 0, "python")
        now = simpledali.datetimeToHPTime(simpledali.utcnowWithTz())
        result = await dali.writeJSON(
            "BC_CUE/JSON", now, now, {"kind": "adapter-smoke", "version": 1}
        )
        if result.type != "OK":
            raise RuntimeError("DataLink write failed")

asyncio.run(main())
PY
```

The proof is complete only when `dalitool` observes the `BC_CUE/JSON` packet.
Its ring packet ID is treated solely as a local cursor.
