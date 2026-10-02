# Where a host keeps canticle's files

The README's onboarding steps and the example units in [`systemd/`](systemd/) assume the layout
below. Only the listener's state directory and the control socket are defaults built into the code.
Everything else is a path you pass on the command line, so another layout works as long as each
process is given the same paths every time it starts.

```text
~/.binary-canticle/                      configuration (RFC §13.6 names this directory)
├── stations.toml                        locators: manifest, listener bind, multicast (stations-toml.md)
├── fleet.json                           the fleet manifest, UNSIGNED in this spike (canticle manifest verify)
├── station-cael.env                     the example station unit's streams: CANTICLE_STATION_ARGS=--stream ...
└── keys/                                mode 0700
    ├── cael.key                         Ed25519 seed, hex; mode 0600, written by canticle keygen, never overwritten
    ├── cael.key.epoch                   the station's epoch counter (§5.2)
    ├── cael.key.epoch.lock              taken while the counter is read and replaced
    └── cael.key.lease                   held while `canticle station` runs: one station per key (§5.1)

$XDG_STATE_HOME/canticle/                listener safety state; ~/.local/state/canticle when XDG_STATE_HOME is unset
├── listener-<tag>.json                  dedup digests, sticky PLUCKs, supersession marks, epochs (§7.4-§7.8)
├── listener-<tag>.json.lease            held while that listener runs; doctor reads it to recognise "this listener"
├── listener-<tag'>.json(.lease)         the same for `canticle tuner`
└── heard.jsonl                          the example listener unit's output: heard events, with their text

$XDG_RUNTIME_DIR/canticle-<name>.sock    a station's control socket (mode 0600, peer uid checked). Without
                                         --control it is canticle-<key_id>.sock, in /tmp if XDG_RUNTIME_DIR is unset

~/.venvs/canticle/                       the venv the package is installed into (README, example units)
```

## Keys

- `canticle keygen --out` refuses to overwrite a file and creates the key with mode 0600. With
  `--manifest` it writes the key only after the manifest has accepted the new entry, so a refused
  command leaves no key behind.
- The seed is plain hex on disk, and nothing else protects it in this spike: keep `keys/` at 0700,
  and out of any repository, backup or sync you would not trust with the key. RFC §15.7's daemon
  key store is not implemented.
- **Never run one key on two hosts, and never restore `<key>.epoch` from an older copy.** The
  counter is what stops a restart from reusing a `seq` (§5.2). An old copy can repeat an epoch
  already used whenever the counter had run ahead of the clock, and two hosts on one key can start
  in the same second. Listeners then see equivocation (§7.4). The lease guards one host only.
- To retire a key, set `"revoked": true` on its manifest entry (by hand: the spike has no command
  for it) and generate a new key. A new key always has a new key-id.

## Listener state

- `canticle listen` and `canticle tuner` keep their safety state by default. The file name comes
  from the manifest and the bind address: `<tag>` is the first 12 hex digits of
  SHA-256(`<absolute manifest path>|<bind>`), and the tuner uses `<bind>|tuner`. Changing either
  starts a new state file; the old one is no longer read.
- The `.lease` file is locked (flock) for the life of the process, and a second listener on the
  same state refuses to start. `canticle doctor` probes the lease without creating it, to tell
  "this listener holds the port" from "something else does".
- `--state PATH` overrides the derived name. Give `canticle doctor` the same `--state PATH` and it
  recognises that listener too.
- Deleting a state file gives up restart safety for what is still on air: the next start can
  surface stale or withdrawn items (§7.4-§7.8). Stop the listener first, and never edit the file.
- `XDG_STATE_HOME` must be the same for the listener and for the shell you run `canticle doctor`
  from, or doctor looks for the lease in the wrong place. The example listener unit pins it to
  `~/.local/state`.

## Logs

The spike keeps no log files of its own. Each command writes status lines to stderr, and `canticle
listen` writes one JSON event per line to stdout.

- **Heard events carry item text.** RFC §19.7 keeps payloads out of observability exports, so the
  example listener unit appends stdout to `heard.jsonl` in the state directory, not to the journal.
  Its `UMask=0077` makes the directory 0700 and the file 0600 when the unit creates them. Nothing
  rotates the file; a harness that tails it can truncate it.
- **Status lines** (a station's start line, `listener_state`, warnings) carry paths, key-ids and
  addresses, but no item text. Under systemd they go to the user journal.
- `canticle ambient --log` and `canticle tuner --log` append to the file you name. Both hold item
  text, as above.
