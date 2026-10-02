# `stations.toml`

`~/.binary-canticle/stations.toml` is the static locator file RFC-0001 §13.6 requires: it tells this
host's tools where the fleet manifest is and where the listener hears, without DNS-SD. It holds
**locators only**. Names, keys and grants come from the manifest (§5.3, §10.3), never from here.

`canticle listen`, `canticle doctor` and `canticle manifest verify|show` read it when they are not
given a manifest on the command line. The loader is `canticle/stations.py`.

## Example

```toml
version = 1

[manifest]
path = "fleet.json"            # relative to this file: ~/.binary-canticle/fleet.json

[listen]
bind = "0.0.0.0:9999"          # IPv4 address and UDP port the listener binds
multicast = false              # join 239.255.13.13 (provisional, D22); off unless you set it
```

## Keys

| Key | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `version` | integer | yes | | Schema version. Must be `1`. |
| `manifest.path` | string | yes | | The fleet manifest. A relative path is relative to the directory holding `stations.toml`, not the working directory; `~` expands to your home. |
| `listen.bind` | string | no | `"0.0.0.0:9999"` | `IPv4-address:port` the listener binds, port 1-65535. `0.0.0.0` hears every interface; `127.0.0.1` hears only this host. IPv6 is not supported. |
| `listen.multicast` | boolean | no | `false` | Join the LAN multicast group. A listener bound to an address other than `0.0.0.0` does not hear the group; `canticle doctor` says so. |

The whole `[listen]` table is optional.

## Strictness

Every key is checked, and an **unknown key is an error** that names the key and the keys allowed
there. A misspelt `multicats = true` fails loudly instead of leaving multicast off. A wrong type
(`multicast = "yes"`, `version = "1"`), a missing `[manifest]` table, an empty path or a bind that is
not `IPv4:port` is an error too. Every message names the file.

## Precedence

- `--manifest PATH` on the command line: `stations.toml` is not read at all. `--bind` and
  `--multicast` then default as they always have (`0.0.0.0:9999`, off).
- Otherwise the file is read (`--stations PATH` names another one). `--bind`, `--multicast` and
  `--no-multicast`, when given, win over the file.
- `canticle manifest verify|show` with no path reads the manifest the file names.

## Not supported (yet)

- **`[trust]`, the genesis pin.** RFC §10.3 says `stations.toml` MAY carry the genesis root set or
  genesis-manifest digest. This spike's manifest is unsigned, so a pin could not be enforced, and a
  pin that is silently ignored is worse than none: a `[trust]` table is refused with that reason.
  It belongs here once signed manifests land (§10.3, D15).
- **Per-station entries** (`[[station]]` with a name and an address). Stations are found from the
  manifest and their beacons, and unicast destinations are a station's `--to`, so the listener does
  not need them. DNS-SD (§13) is not implemented either.
- **Station settings** (key, streams, control socket). A station is configured on its command
  line; see `docs/systemd/canticle-station@.service` and `docs/state-layout.md`.

Bump `version` for any change that would make an old reader misread a new file.
