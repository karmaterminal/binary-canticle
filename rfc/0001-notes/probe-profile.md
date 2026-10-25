# Probe profile: findings sung live

> Non-normative. RFC-0001 §6.7 (amendment FP-1, #112; D37, proposed) is the authority, and this note defers to
> it. Code: `prototype/canticle-station/canticle/finding.py`. Tests: `prototype/canticle-station/tests/test_finding.py`.

How a fleet probe or a distress watcher (#111) says what it checked and saw, with classes that already exist.
It is for whoever builds one or hears one: the distress watcher (#113), the Thornfield probe workflow
(temporal-thornfield-frond#27), the fleet-probe skill (scribe-prince-shared#78) and the ear (frond-ear#85).

Contents: rules at a glance · streams and incident keys · the finding body · lifecycle · classes · what it does
not do · the prototype · choices for review.

## Rules at a glance

**Singer**

1. Sing through your own station and key, granted `advisory` and `finding-ref` on the profile's streams, never
   through the subject's station. A watcher or probe says `voice: observer`; only a seat about itself says `self`.
2. A finding is one `advisory` with content type 11, keyed by its incident: `state_key` = `incident`. Let the
   station build it (`canticle sing --finding`); don't encode it yourself.
3. Write the receipt and hash it before you sing, then give it as the advisory's own `body_ref`. A receipt never
   changes once its digest has been sung.
4. While open, give a severity in CAP's words. Missing data never yields a calm word: when a check did not run or
   could not read, `minor` becomes `unknown`, while `moderate`, `severe` or `extreme` stand when the checks that
   did run show them, and the summary names what was not read.
5. Close explicitly, with a newer item on the same key and stream: `resolved` when you saw it clear, `ended` when
   you stopped watching without seeing it clear. Never leave it to silence or expiry.
6. Announce changes, not scans (Silas, #111): the open, a new view when the finding changes materially, the
   close, and at most one reminder, an hour or more after the last change (Lifecycle). New counts alone are not
   a change.
7. Never sing `alarm` or hold a key granted it, never give severity as a number, and never put a credential, a
   pre-signed URL or a local path in a `body_ref` or a text field.

**Receiver**

1. The signer is the speaker. Attribute a finding to its signing station and that station's principal, from the
   manifest. Present it as the subject's own voice only when `voice` is `self` and `subject` names the signer.
2. Words, not numbers: never map `status` or `severity` to a number, `intensity`, salience or wake. `advisory`
   does not wake in v1 (§6.2).
3. A content type 11 body that is not a finding (malformed, on another class, or with an `incident` that differs
   from the `state_key`) is opaque. Never show a status or severity for it.
4. Only a newer `resolved` item from the same key, on the same stream and incident, resolves a finding. Silence,
   expiry, a pluck, a gap and another station's item never do. A finding past its local expiry has lapsed: show it
   as lapsed, never as resolved.
5. Never fetch a `body_ref` on landing (§9.6, §14.12).
6. You may group findings by incident. Count signers, never items or repeats (§10.7 R-ACC-1).

## Streams and incident keys

| Stream | Who sings there | Incident key | Voice |
|---|---|---|---|
| `distress` | a distress watcher on the seat's host (#113), or the seat itself while it can still run tools (#97) | `SEAT:distress` | `observer` for a watcher, `self` for the seat |
| `alerts` | a fleet probe: a short-lived worker that checks the fleet and announces one finding (#111) | `SEAT:SIGNAL` | `observer` |

- Both streams carry the finding and its receipt's doorbell. The names are conventions: a receiver knows a
  finding by its content type, class and key, never by its stream (§6.7).
- Each stream's configuration raises the keep-on-air ceiling for `advisory` from one TTL (§7.9) to at least
  1800 s, the watch window the examples use; a watcher that watches longer needs a stream configured for its
  window. Without that, a conforming station keeps a finding on air for one TTL only, and receivers then read it
  as lapsed.
- An incident key is the item's `state_key`: 1-32 bytes of UTF-8, one line. Lowercase ASCII is easiest to match.
  `SIGNAL` comes from the probe's own list (scribe-prince-shared#78 keeps the fleet probes' list). Leave room for
  the seat: beside the 17-byte `heartbeat-crowded`, `SEAT` has 14 bytes.
- Stations that see the same condition use the same incident key, so that N sentries make one chorus with N
  observations (Elliott, #111). A Temporal probe can use the incident key as its workflow ID, so that
  signal-with-start joins the run already watching it (#111).
- Name the `subject` by its station name in the manifest when it has one. A seat speaking for itself must, since
  `self` shows only when `subject` names the signer.
- Scan chatter, progress and answers to a hold stay on the probe's own stream, never on `alerts` (Silas, #111).

## The finding body

Content type 11, `application/vnd.canticle.finding+cbor` (§9.9): a deterministic CBOR map with integer keys
(§9.4). The JSON projection uses the names (§9.10).

| Key | Name | Value | Required |
|---|---|---|---|
| 1 | `incident` | text, 1-32 bytes, equal to the item's `state_key` | yes |
| 2 | `subject` | text, 1-64 bytes: the seat or host the finding is about | yes |
| 3 | `voice` | `self` or `observer` | yes |
| 4 | `status` | `open`, `resolved` or `ended` | yes |
| 5 | `severity` | `extreme`, `severe`, `moderate`, `minor` or `unknown`: the words of CAP's `severity` | exactly when `status` is `open` |
| 6 | `summary` | text, 1-280 bytes: what was checked and seen, in plain operational words | yes |
| 7 | `not_proved` | text, 1-160 bytes: what this finding does not establish | yes |

- Every text field is one line: no Unicode Cc character, and no U+2028 or U+2029. Lengths count UTF-8 bytes.
- A publisher refuses names it does not know. Receivers ignore unsigned integer keys other than 1-7; a change that
  old receivers must not misread takes a new content type.
- In record v1 (§14.18.3), `body.ctype` is the media type's name, or 11 from a daemon that predates the
  registration. Accept both.
- No word means "fine", and a missing severity is not a value (I-9). A probe that finds nothing to report sings
  no finding; its receipt is the record.
- Sizes: the largest body is 576 bytes. With a 200-byte URL in `body_ref`, the frame is at most 985 bytes, which
  leaves room for a `purpose` of about 100 bytes and the flag a refresh adds. The station refuses any frame over
  1 100 bytes (§9.1).

Worked examples. `test_worked_examples_are_the_profiles_bytes` checks both against the codec, byte for byte.

The open finding, 131 bytes:

```json
{"incident": "seat-a:distress", "subject": "seat-a", "voice": "observer", "status": "open",
 "severity": "moderate", "summary": "gateway not ready for 6 min; 3 claimed turns waiting",
 "not_proved": "that any turn was lost"}
```

```
a7016f736561742d613a64697374726573730266736561742d6103686f6273657276657204646f70656e05686d6f6465
7261746506783467617465776179206e6f7420726561647920666f722036206d696e3b203320636c61696d6564207475
726e732077616974696e6707767468617420616e79207475726e20776173206c6f7374
```

The resolution that supersedes it, 134 bytes:

```json
{"incident": "seat-a:distress", "subject": "seat-a", "voice": "observer", "status": "resolved",
 "summary": "gateway ready again; claimed turns draining",
 "not_proved": "that the 3 waiting turns were delivered"}
```

```
a6016f736561742d613a64697374726573730266736561742d6103686f6273657276657204687265736f6c7665640678
2b6761746577617920726561647920616761696e3b20636c61696d6564207475726e7320647261696e696e6707782774
6861742074686520332077616974696e67207475726e7320776572652064656c697665726564
```

## Lifecycle

1. **Receipt.** Write the receipt where receipts live, and take its SHA-256 and size. Never rewrite it after its
   digest is sung: a later receipt gets its own path. Leave `body_ref` out when the receipt has no location a
   receiver could reach.
2. **Open.** Sing the advisory with `status: open`, a severity, the receipt as `body_ref`, and `--keep-on-air` for
   the watch window. The station re-issues it before each expiry with the same body (§7.9), so a summary states
   what the check saw, not a running count.
3. **A new view.** When the finding changes materially, sing a new item on the same key: a new severity, or a
   change in what it asserts (for a watcher, which of its checks fail). New counts alone are not a change: every
   scan re-counts, and a sing per scan is the chatter rule 6 keeps off the air, so the item keeps the counts it
   was sung with. A new view supersedes the old item at once (§7.8), and a late joiner hears only the newest
   within about one loop (§7.10).
4. **Reminder.** At most one per incident, an hour or more after the open or the last new view, while it is
   still open: the current body sung again, with the same `canticle sing --finding`. It is a new item, so every
   receiver hears it as new. A keep-on-air re-issue is not a reminder: it carries `refresh = 1` and an equal
   digest, and receivers take it as the same lineage, never as new (§7.9).
5. **Close.** Sing `resolved` or `ended`, with no severity, the final receipt as `body_ref`, and about 15 minutes
   of keep-on-air (`--keep-on-air 900`), so late joiners hear the close. A probe's conversational presence ends
   with its close, so no listener sees an apparent responder silently swallowing questions (Silas, #111).
6. **Doorbell.** Ring the final receipt once: a `finding-ref` with only a `body_ref` (content type 8) and no
   `state_key`. An unkeyed item cannot be kept on air (§7.9), so it lives one stream TTL.
7. **Sung in error.** Correct it with a newer item on the same key: `ended`, with a summary that says what was
   wrong. Pluck it (`canticle hush`) only when the item itself must stop being shown; a pluck withdraws a
   statement and never resolves one (§7.7).

Two lifetimes (Silas, #111): the incident outlives the probe as an expiring keyed item, and the probe's
conversational presence ends. A frame lives one TTL, at most the stream's `max_ttl` (300 s by default, D3).
Keep-on-air is a series of re-issued frames, which the station keeps up after the probe has exited. If the
station stops, the item lapses within one TTL, and receivers read that as lapsed, never as resolved.

Keep-on-air past one TTL needs the stream's configuration to allow it (§7.9), which is why both streams raise it
to at least 1800 s. The spike does not model per-stream ceilings: it caps any keyed item at the 24 h station hard
cap (D3).

## Classes

| Class | When | `state_key` | Body |
|---|---|---|---|
| `advisory` (4) | the finding, from open to close | the incident | the finding body (content type 11), optionally with `body_ref` |
| `finding-ref` (5) | the receipt's doorbell, rung once per receipt | none | none: content type 8, `body_ref` only |
| `alarm` (7) | never from a probe or watcher. Alarms need a human-held key (D14); a single automated keeper raising fleet alarms is not v1 (§19.6) | | |

The doorbell needs no key. A receipt never changes, so nothing supersedes it, and the advisory's own `body_ref`
already carries the current receipt. A doorbell keyed by the incident would change that key's class within the
epoch (§7.8). A background emitter (`canticle ambient`, §15.8) sings only `ambient` and `chatter`, so it can sing
neither class.

## What this profile does not do

- Wake anyone, promote a finding to an alarm, bridge to Discord, or remediate (#112; §19.6, §21).
- Carry replies or commands. "Hold" and "show me detail" go through the probe's own control plane, never as
  canticle frames (#111). Talking to a probe grants no restart or shell authority (#111).
- Prove delivery. A finding may go unheard; the receipt, and a distress watcher's spool, are the record (#111,
  #113).
- Make `subject` or `voice` trust inputs (I-11). The spike's manifest is unsigned, so the station name a receiver
  shows is only as good as the manifest file.
- Say where receipts live. `body_ref` only names one.

## The prototype

```sh
# The open finding, with its receipt, kept on air for 30 minutes.
URL=https://ledger.example/receipts/seat-a-distress-1.json
SHA256=$(sha256sum receipt-1.json | cut -d' ' -f1); SIZE=$(stat -c %s receipt-1.json)
canticle sing --control ./watch.sock --stream distress --scope fleet --keep-on-air 1800 \
  --finding '{"incident": "seat-a:distress", "subject": "seat-a", "voice": "observer", "status": "open",
    "severity": "moderate", "summary": "gateway not ready for 6 min; 3 claimed turns waiting",
    "not_proved": "that any turn was lost"}' \
  --body-ref "$URL" "$SHA256" "$SIZE"

# The close, then the final receipt's doorbell.
URL=https://ledger.example/receipts/seat-a-distress-2.json
SHA256=$(sha256sum receipt-2.json | cut -d' ' -f1); SIZE=$(stat -c %s receipt-2.json)
canticle sing --control ./watch.sock --stream distress --scope fleet --keep-on-air 900 \
  --finding '{"incident": "seat-a:distress", "subject": "seat-a", "voice": "observer", "status": "resolved",
    "summary": "gateway ready again; claimed turns draining",
    "not_proved": "that the 3 waiting turns were delivered"}' \
  --body-ref "$URL" "$SHA256" "$SIZE"
canticle sing --control ./watch.sock --stream distress --scope fleet --class finding-ref \
  --body-ref "$URL" "$SHA256" "$SIZE"
```

- `--finding JSON` sends `"finding": {named fields}` on the control socket's `sing` op (§11.1). The station checks
  it, builds the body, sets content type 11 and the `state_key`, and refuses any class but `advisory` (the
  default with `--finding`). Neither the CLI nor the socket takes another body or content type beside it.
- `--body-ref URL SHA256 SIZE` sends `"body_ref": {"url", "sha256", "size"}`: a one-line URL of 1-200 bytes, 64
  hex digits and a byte count. Alone it makes a doorbell, and `sing` reads nothing from stdin. Beside a body, the
  body is its summary (§9.6).
- A refusal comes back as `{"ok": false, "error": ...}`, naming the field, before a `seq` is used; so does one
  for a frame over 1 100 bytes. An empty `SHA256`, after a failed `sha256sum`, is refused, and nothing goes on air.
- The key needs classes `advisory,finding-ref`, the streams, and `fleet` scope in the manifest
  (`canticle keygen --classes advisory,finding-ref --streams alerts,distress --scopes lan,fleet`), and its station
  runs them as `--stream distress:advisory --stream alerts:advisory`. Creating keys and running stations on a host
  is that host owner's work.

`canticle tap` shows a finding field by field inside the untrusted-content wrapper, and adds one host-authored
banner line outside it, holding only words from the closed sets:

```
finding status=open severity=moderate voice=observer: the station's own observation of the subject it names below, not words from that subject
```

`voice=self` appears only when the subject names the signer; a `self` body that names another subject shows as
`voice=self-unmatched`. A content type 11 body that is not a finding shows `finding=unreadable (reason)` and
stays opaque. `--json` adds `finding`, with its text fields defanged, and `finding_voice`, or `finding_error`.

## Choices for review

Each choice, with the alternative it turned down. The open questions are RFC §23.2 question 30.

1. Integer keys and a named JSON projection, the RFC's style for typed bodies. Not text keys in an
   `application/cbor` body, which every receiver would read as opaque CBOR.
2. Evidence in the advisory's own `body_ref`, not a `receipt` field in the body.
3. An unkeyed doorbell for a receipt that never changes. Not a doorbell keyed `SEAT:SIGNAL/r` and superseded by
   the final receipt, which temporal-thornfield-frond#27 first planned.
4. `ended` for a watcher that stops without seeing a resolution. Not "expired", which reads as TTL expiry.
5. CAP's severity words, present only while open. Not `critical`, `warning` and `info`.
6. `self` shown only when `subject` names the signer's manifest station name.
7. A malformed body fails quiet as opaque. Nothing is shown half-parsed.
8. A new view only on a material change, and one reminder, sung as a new item. Not a sing per scan, and not a
   reminder sent as a refresh, which no receiver shows as new.
