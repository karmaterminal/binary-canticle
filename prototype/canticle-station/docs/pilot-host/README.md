# Pilot-host kit: a LAN daemon that never listens unscoped

The canticle pilot runs one host daemon per host, bound to the host's LAN address, with an nft table that
lets only the pilot peer reach its port (round 1: [#65](https://github.com/karmaterminal/binary-canticle/issues/65);
round 2: [#95](https://github.com/karmaterminal/binary-canticle/issues/95)). On silas and ronan the daemon, the
station and the table were all transient: `systemd-run --user` units and a hand-loaded table, gone after a
reboot. This kit makes them persistent, and keeps the daemon from ever starting without the table
([#103](https://github.com/karmaterminal/binary-canticle/issues/103)).

**Documented only.** Nothing here installs itself. Each host owner applies the kit on their own host, with
their own go: 🌫 Silas for silas, 🌊 Ronan for ronan, and the queue after them (🕯 → 🪨 → 🩸 → 🌻, #95).

| File | What it is | Installed to | By |
|---|---|---|---|
| [`canticle-pilot.nft`](canticle-pilot.nft) | the table: two drops on the daemon's address and port, set by four `define`s | `/etc/canticle/canticle-pilot.nft` | root |
| [`canticle-nft.service`](canticle-nft.service) | a **system** unit that loads the table at boot, before the network and before any user manager | `/etc/systemd/system/` | root |
| [`canticle-pilot-guard.sh`](canticle-pilot-guard.sh) | the daemon's start check: an exact bind, and the table scoping it | `~/.binary-canticle/` | the seat |
| [`canticle-daemon.service.d/pilot.conf`](canticle-daemon.service.d/pilot.conf) | a drop-in for [`../systemd/canticle-daemon.service`](../systemd/canticle-daemon.service): LAN bind, multicast off, the guard first | `~/.config/systemd/user/canticle-daemon.service.d/` | the seat |
| [`../systemd/canticle-station@.service`](../systemd/canticle-station@.service) | the station template; a pilot station sends to its peer | `~/.config/systemd/user/` | the seat |

The daemon and station are **user units** under the seat's uid. The table's unit is a **system unit**, because
loading nft rules needs root. The host owner also writes three small files: `~/.binary-canticle/pilot.env`,
`~/.binary-canticle/station-NAME.env` and, if step 3 needs it, `/etc/sudoers.d/canticle-pilot`.

| You want to | Go to |
|---|---|
| know why the table goes in before the daemon | [Why the firewall comes first](#why-the-firewall-comes-first) |
| apply the kit | [Before you start](#before-you-start), then [Apply, in this order](#apply-in-this-order) |
| look up one host's values | [Worked examples](#worked-examples): silas, ronan |
| check a host | [Receipts](#receipts) |
| read a refusal in the journal | [When the guard refuses](#when-the-guard-refuses) |
| take it all off | [Rollback](#rollback) |
| run the daemon-loss proof | [`../../proofs/pilot/round-2b-daemon-loss.md`](../../proofs/pilot/round-2b-daemon-loss.md) (#104) |

## Why the firewall comes first

The daemon checks each datagram's signature against the fleet manifest. The pilot also agreed a network scope
in round 1 (#65): only the peer host, on the LAN interface, reaches the daemon's port. The table is that scope.
A daemon that comes back after a crash or reboot on a host whose table is gone hears every source (#103). So the
order holds three ways:

- **At boot.** `canticle-nft.service` loads the table before `network-pre.target` and before
  `systemd-logind.service`. logind is what starts each user manager (`user@UID.service`, which runs the
  daemon): a lingering user's as logind itself starts, anyone else's at login. systemd can't order a user unit
  against a system unit directly, so the order goes through logind.
- **At every daemon start.** The guard ([`canticle-pilot-guard.sh`](canticle-pilot-guard.sh)) runs first. It
  refuses unless `CANTICLE_BIND` is one exact IPv4 address and port, and `table inet canticle` drops datagrams
  to exactly that address and port from other interfaces and other sources. A refused start is retried every
  5 s (`Restart=on-failure`), so a daemon that starts too early comes up once the table is in.
- **When you apply the kit.** Steps 1 and 2 load the table and read it back. Only then does step 4 move the
  daemon.

Reading the table needs root, so the guard asks `sudo -n nft list table inet canticle`. That needs a rule
letting the seat run exactly that command (step 3). It also needs the unit line without `NoNewPrivileges`, which
the base unit sets: `pilot.conf` runs the guard as `ExecStartPre=+`, which still runs it as the seat's uid. The
daemon itself keeps `NoNewPrivileges`.

## Before you start

- The commands are POSIX shell. silas's login shell is fish: run them in `bash`.
- Run them from a binary-canticle checkout at the commit you reviewed, in `prototype/canticle-station/docs/`.
- `canticle` below is `~/.venvs/canticle/bin/canticle`: activate the venv, or type the full path.
- Linger is on, so the user units start at boot: `loginctl show-user "$USER" -p Linger` prints `Linger=yes`
  (`sudo loginctl enable-linger "$USER"` if not).
- Round 1's setup is in place: the venv, `~/.binary-canticle/fleet.json`, this host's station key in
  `~/.binary-canticle/keys/`, and `~/.binary-canticle/stations.toml`. Its `[listen] bind` should be the same
  exact address and port as `CANTICLE_BIND`, so `canticle doctor` checks the address the daemon holds.
- Your host's values are in [Worked examples](#worked-examples). Each command block below sets the ones it uses
  at its top, with silas's values and ronan's beside them.

Record what runs now. Step 4 must keep the daemon's state directory and socket, and a rollback to the transient
units needs their command lines:

```sh
systemctl --user list-units 'canticle*'
systemctl --user show -p ExecStart canticle-daemon 'canticle-station-*' > ~/canticle-transient-units.txt
journalctl --user -u canticle-daemon -o cat | grep '^{"daemon"' | tail -n 1
```

The last line is the daemon's start line. Note its `"state_dir"` and `"socket"`. The kit's daemon uses
`~/.local/state/canticle/daemon` and `$XDG_RUNTIME_DIR/canticle/daemon.sock`. If the transient daemon used another
state directory, add the same `--state-dir PATH` to the `ExecStart` in `pilot.conf`: a new state directory gives
up restart safety for what is on air ([`../state-layout.md`](../state-layout.md), Host daemon state). If it used
another socket, the ear's `canticle.hostSocket` must follow it.

## Apply, in this order

**1. Load the table (root).** Install the file, set its defines, check it, then install the unit and start it:

```sh
LOCAL=10.0.0.100 LAN_IF=wlan0 PEERS=10.0.0.246      # ronan: 10.0.0.246, enP7s7, 10.0.0.100
sudo install -D -m 0644 pilot-host/canticle-pilot.nft /etc/canticle/canticle-pilot.nft &&
  sudo sed -i -e "s/^define LOCAL = .*/define LOCAL = $LOCAL/" \
    -e "s/^define LAN_IF = .*/define LAN_IF = \"$LAN_IF\"/" \
    -e "s/^define PEERS = .*/define PEERS = { $PEERS }/" /etc/canticle/canticle-pilot.nft &&
  grep '^define' /etc/canticle/canticle-pilot.nft &&
  sudo nft -c -f /etc/canticle/canticle-pilot.nft &&
  sudo install -m 0644 pilot-host/canticle-nft.service /etc/systemd/system/ &&
  sudo systemctl daemon-reload &&
  sudo systemctl enable --now canticle-nft.service
```

With more than one peer, `PEERS` is comma-separated: `PEERS='10.0.0.246, 10.0.0.250'`. If round 1's hand-loaded
table is still in, this replaces it in one transaction (the file deletes and redefines the table in one
`nft -f`), so the port is never unscoped.

**2. Read the table back.**

```sh
sudo nft list table inet canticle
systemctl show canticle-nft.service -p ActiveState,SubState,UnitFileState
```

Expect your host's listing from [Worked examples](#worked-examples) (`priority filter - 10` and the two drops),
and `ActiveState=active`, `SubState=exited`, `UnitFileState=enabled`. Note both drop counters. The peer's
datagrams match neither rule, so with the peer on air the counters stay where they were: read the table again a
minute later to see that. A probe from a third host moves the source drop by one (round 1 used elliott,
`10.0.0.153`), but only with that host owner's go.

**3. Let the seat read the table.** Check first, as the seat user:

```sh
sudo -n nft list table inet canticle >/dev/null && echo readable
```

If it prints `readable`, go on to step 4. Otherwise add a rule that allows exactly that command, with those
arguments, and nothing else:

```sh
rule=$(mktemp) &&
  printf '%s ALL=(root) NOPASSWD: /usr/sbin/nft list table inet canticle\n' "$USER" >"$rule" &&
  sudo visudo -cf "$rule" &&
  sudo install -m 0440 -o root -g root "$rule" /etc/sudoers.d/canticle-pilot
rm -f "$rule"
sudo -n nft list table inet canticle >/dev/null && echo readable
```

On Arch and CachyOS `/usr/sbin` is a link to `/usr/bin`, and sudo matches the rule's `/usr/sbin/nft` to
`/usr/bin/nft` because they are the same file. If it still doesn't print `readable`, check that `/etc/sudoers`
reads `/etc/sudoers.d` (`sudo grep -n includedir /etc/sudoers`).

**4. Move the daemon onto the kit.** Install the guard, `pilot.env`, the base unit and the drop-in, then run the
guard once by hand. It must print `canticle-pilot-guard: ok: bind ...`; if it refuses, fix what it says first
([When the guard refuses](#when-the-guard-refuses)).

```sh
BIND=10.0.0.100:9999                                  # ronan: 10.0.0.246:9999
install -m 0644 pilot-host/canticle-pilot-guard.sh ~/.binary-canticle/ &&
  printf 'CANTICLE_BIND=%s\n' "$BIND" > ~/.binary-canticle/pilot.env &&
  install -D -m 0644 systemd/canticle-daemon.service ~/.config/systemd/user/canticle-daemon.service &&
  install -D -m 0644 pilot-host/canticle-daemon.service.d/pilot.conf \
    ~/.config/systemd/user/canticle-daemon.service.d/pilot.conf &&
  (set -a && . ~/.binary-canticle/pilot.env && sh ~/.binary-canticle/canticle-pilot-guard.sh)
```

Then swap the units. The daemon stops here, so tell the scribe seat and anyone with a tap open first. The ear
backs off and reconnects by itself; a `canticle tap` ends and must be run again.

```sh
systemctl --user stop canticle-daemon                  # round 1's transient unit, if this host has one: TERM, so bye
systemctl --user reset-failed canticle-daemon 2>/dev/null || true
systemctl --user daemon-reload
systemctl --user cat canticle-daemon                   # the two files above, not .../systemd/transient/...
systemctl --user enable --now canticle-daemon
```

A transient unit shadows a unit file of the same name while it is loaded. If `systemctl --user cat` still shows
a path under `/run/user/UID/systemd/transient/`, stop and reset it again before `enable`. Then read the
[receipts](#receipts) for the daemon: the guard's `ok` line, one socket on the exact bind, `NRestarts=0`, and the
`state_dir` and `socket` you recorded.

**5. Move the station onto the template.** The instance name is the station key's file name without `.key`
(`ls ~/.binary-canticle/keys/`). The name the station signs as comes from the manifest, not from the instance.

```sh
NAME=frond-gloss TO=10.0.0.246:9999                   # ronan: frond-scribe, 10.0.0.100:9999
install -D -m 0644 systemd/canticle-station@.service ~/.config/systemd/user/canticle-station@.service &&
  printf 'CANTICLE_STATION_TO=%s\nCANTICLE_STATION_ARGS=%s\n' "$TO" '--stream chatter' \
    > ~/.binary-canticle/"station-$NAME.env"
systemctl --user stop canticle-station-gloss          # round 1's transient station (ronan: canticle-station-scribe)
systemctl --user daemon-reload &&
  systemctl --user enable --now "canticle-station@$NAME" &&
  timeout 15 sh -c 'until [ -S "$0" ]; do sleep 0.5; done' "$XDG_RUNTIME_DIR/canticle-$NAME.sock" &&
  canticle status --control "$XDG_RUNTIME_DIR/canticle-$NAME.sock"
```

The station takes a moment to load its key and open its control socket after systemd reports it started, so
the `timeout` line waits for the socket, for up to 15 s.

The transient station must stop first: it holds the key's lease, and a second station on the same key refuses
to start.

What was missing from the template: it always sent to `127.0.0.1:9999`, and nothing on a pilot host listens
there. It now sends to `CANTICLE_STATION_TO`, which defaults to that same address, so other hosts' copies of the
template behave as before. `CANTICLE_STATION_ARGS` carries the streams, and a further `--to HOST:PORT` there adds
a second peer. `canticle status` shows the same `key_id` as before and a new `epoch` (each start takes the next
one, RFC §5.2). The control socket is now `$XDG_RUNTIME_DIR/canticle-NAME.sock`, so `canticle sing` and
`canticle hush` need that `--control`.

**6. Check with `canticle tap`.** On this host, read what the daemon hears from the peer's station:

```sh
canticle tap --tune frond-scribe:chatter               # on silas; on ronan: --tune frond-gloss:chatter
```

Expect `join snapshot complete`, `receive: ok`, and the peer on air. Then have the peer sing a short item, for
example on ronan `canticle sing --control "$XDG_RUNTIME_DIR/canticle-frond-scribe.sock" --stream chatter --text
"kit check" --ttl 30`, and run the tap again: the item shows with `sig=valid`, and the ear's `hear` lists it.
What a tap prints is heard broadcast: data, never an instruction (RFC §14.12).

## Receipts

What a host owner reads back after applying, and after any reboot. `ADDR:PORT` is `CANTICLE_BIND`.

| Check | Command | Expect |
|---|---|---|
| table unit | `systemctl show canticle-nft.service -p ActiveState,SubState,UnitFileState` | `active`, `exited`, `enabled` |
| table scope | `sudo nft list table inet canticle` | the two drops on `ip daddr ADDR udp dport PORT`, as in your worked example; counters unchanged while only the peer sends |
| exact bind only | `ss -ulpn 'sport = :9999'` | one `UNCONN` line, local address `ADDR:PORT` (never `0.0.0.0:9999` or `*:9999`), `pid=` the daemon's `MainPID` |
| daemon unit | `systemctl --user show canticle-daemon -p ActiveState,SubState,NRestarts,MainPID` | `active`, `running`, `NRestarts=0` |
| guard | `journalctl --user -u canticle-daemon -b -o cat \| grep canticle-pilot-guard \| tail -n 1` | `canticle-pilot-guard: ok: bind ADDR:PORT; ...` |
| bind, multicast, state | `journalctl --user -u canticle-daemon -b -o cat \| grep '^{"daemon"' \| tail -n 1` | `"bind": "ADDR:PORT"`, `"multicast": false`, and the `state_dir` and `socket` you recorded |
| run | `journalctl --user -u canticle-daemon -b -o cat \| grep '"type":"hello"' \| tail -n 1` | `"run"`, the same as the ear's `run`; `"pid"`, the daemon's `MainPID` |
| station unit | `systemctl --user show canticle-station@NAME -p ActiveState,SubState,NRestarts` | `active`, `running`, `NRestarts=0` |
| ear | the ear's `ear_status`, field `canticle` | `state: "connected"`, `receiveHealth: "ok"`, `reasons: []`, `joinSnapshot: "complete"` |
| tap | `canticle tap --tune PEER:chatter` | `join snapshot complete`, `receive: ok`, the peer on air |

After a reboot `NRestarts` can be above 0. Wi-Fi can come up after the user manager, so the first starts fail
with `bind_failed` and are retried every 5 s. Check that the count has stopped rising and that the last guard
line is `ok`.

## Worked examples

The two current pilot hosts. Both run round 1's transient units today (#103); applying the kit stays with each
owner. The interface names are round 1's (#65): check yours with `ip -br addr`.

| | silas | ronan |
|---|---|---|
| host owner | 🌫 Silas | 🌊 Ronan |
| `LOCAL`; `CANTICLE_BIND` | `10.0.0.100`; `10.0.0.100:9999` | `10.0.0.246`; `10.0.0.246:9999` |
| `LAN_IF` | `wlan0` | `enP7s7` |
| `PEERS`; `CANTICLE_STATION_TO` | ronan: `10.0.0.246`; `10.0.0.246:9999` | silas: `10.0.0.100`; `10.0.0.100:9999` |
| station instance and key | `frond-gloss`: `~/.binary-canticle/keys/frond-gloss.key` | `frond-scribe`: `~/.binary-canticle/keys/frond-scribe.key` |
| round 1's transient units | `canticle-daemon`, `canticle-station-gloss` | `canticle-daemon`, `canticle-station-scribe` |
| tap check | `canticle tap --tune frond-scribe:chatter` | `canticle tap --tune frond-gloss:chatter` |

If a station key has another file name, use that name as the instance.

### silas

```text
$ grep '^define' /etc/canticle/canticle-pilot.nft
define LOCAL = 10.0.0.100
define LAN_IF = "wlan0"
define PEERS = { 10.0.0.246 }
define PORT = 9999               # the port in CANTICLE_BIND
$ cat ~/.binary-canticle/pilot.env
CANTICLE_BIND=10.0.0.100:9999
$ cat ~/.binary-canticle/station-frond-gloss.env
CANTICLE_STATION_TO=10.0.0.246:9999
CANTICLE_STATION_ARGS=--stream chatter
$ sudo nft list table inet canticle
table inet canticle {
	chain in {
		type filter hook input priority filter - 10; policy accept;
		ip daddr 10.0.0.100 udp dport 9999 iifname != "wlan0" counter packets 0 bytes 0 drop
		ip daddr 10.0.0.100 udp dport 9999 ip saddr != 10.0.0.246 counter packets 0 bytes 0 drop
	}
}
```

### ronan

```text
$ grep '^define' /etc/canticle/canticle-pilot.nft
define LOCAL = 10.0.0.246
define LAN_IF = "enP7s7"
define PEERS = { 10.0.0.100 }
define PORT = 9999               # the port in CANTICLE_BIND
$ cat ~/.binary-canticle/pilot.env
CANTICLE_BIND=10.0.0.246:9999
$ cat ~/.binary-canticle/station-frond-scribe.env
CANTICLE_STATION_TO=10.0.0.100:9999
CANTICLE_STATION_ARGS=--stream chatter
$ sudo nft list table inet canticle
table inet canticle {
	chain in {
		type filter hook input priority filter - 10; policy accept;
		ip daddr 10.0.0.246 udp dport 9999 iifname != "enP7s7" counter packets 0 bytes 0 drop
		ip daddr 10.0.0.246 udp dport 9999 ip saddr != 10.0.0.100 counter packets 0 bytes 0 drop
	}
}
```

The listings are nft 1.0.9's; your counters will differ. With two peers, nft lists
`ip saddr != { 10.0.0.246, 10.0.0.250 }`.

The table differs from #103's sketch in one place. The sketch wrote `iifname != "$LAN_IF"`, but nft doesn't
expand a variable inside quotes, so that rule would compare against the text `$LAN_IF` and drop the peer too.
The kit quotes the value in the `define` and writes `$LAN_IF` bare.

## When the guard refuses

The guard writes one line to the daemon's journal (`journalctl --user -u canticle-daemon -b`), and systemd tries
again every 5 s until you fix it. Stop the unit while you do: `systemctl --user stop canticle-daemon`.

| The line says | Why | Do |
|---|---|---|
| `CANTICLE_BIND is empty or unset` | `pilot.env` has no `CANTICLE_BIND=` line | write it (step 4) |
| `listens on every address`, `has no address` | a wildcard: `0.0.0.0`, `::`, `[::]`, `*` or a bare `:PORT` | this host's exact LAN address and port |
| `is IPv6`, `has no port`, `the port must be`, `is not an IPv4 address` | not `ADDRESS:PORT` in dotted-quad IPv4 | write it as `10.0.0.100:9999` |
| `table inet canticle is not loaded` | the table is gone: not loaded at boot, or flushed by a stop of the distro's `nftables.service` | `sudo systemctl restart canticle-nft.service`, then step 2 |
| `can't read the table without a password` | no sudo rule for the seat | step 3 |
| `NoNewPrivileges stops sudo` | the guard line lost its `+` | install `pilot.conf` again |
| `doesn't drop datagrams to ADDR:PORT` | the table's `LOCAL` or `PORT` differs from `CANTICLE_BIND`, the file still has the sample defines, or the table was changed by hand (its drops in another chain, or a rule before them that accepts or jumps) | fix the defines in the kit's file, then `sudo systemctl reload canticle-nft.service`; the reload replaces the table, so both counters start again from 0 |

Two refusals come from systemd and the daemon, not the guard. `Failed to load environment files` means
`pilot.env` is missing. A `"type":"fatal"` line with `"reason":"bind_failed"` means the address isn't up yet
(boot) or something else holds the port (`ss -ulpn 'sport = :9999'`).

## Rollback

Reverse order: the station, then the daemon, and only then the table. Removing the table under a running daemon
opens the port to every source.

```sh
NAME=frond-gloss                                      # ronan: frond-scribe
systemctl --user disable --now "canticle-station@$NAME"   # a clean stop: the peer sees signed_off
systemctl --user disable --now canticle-daemon            # TERM: bindings see bye
rm ~/.config/systemd/user/canticle-daemon.service.d/pilot.conf ~/.config/systemd/user/canticle-daemon.service \
  ~/.config/systemd/user/canticle-station@.service
rmdir ~/.config/systemd/user/canticle-daemon.service.d
systemctl --user daemon-reload
sudo systemctl disable --now canticle-nft.service         # leaves the table loaded: there is no ExecStop
sudo nft delete table inet canticle
sudo rm /etc/systemd/system/canticle-nft.service /etc/canticle/canticle-pilot.nft
sudo systemctl daemon-reload
sudo rm -f /etc/sudoers.d/canticle-pilot                  # if step 3 added it
rm ~/.binary-canticle/canticle-pilot-guard.sh ~/.binary-canticle/pilot.env ~/.binary-canticle/"station-$NAME.env"
```

The daemon's state directory and the station key stay as they were. To go back to round 1's transient units
instead, stop after the `rm` of the user units, keep the table, and start them again from the command lines in
`~/canticle-transient-units.txt`.

## Same-uid caveat

On silas and ronan the prince's gateway and the scribe seat run under one uid, so everything this kit puts in a
home directory belongs to the host, not to a seat (#95):

- The station key under `~/.binary-canticle/keys/` (mode 0600) can be read by every seat on the host, and the
  station's control socket can be used by every seat.
- The daemon's allowed uid (`--allow-uid`, its own by default) admits every seat on the host. A prince listens
  through `canticle tap` with no key, and stays listen-only until it has its own uid.
- The sudo rule from step 3 lets every seat on the host read the table. Reading changes nothing.

A station and binding per uid is #95's step before any prince publishes. Today the daemon's socket can't admit a
second non-root uid, whatever `--allow-uid` lists:
[#99](https://github.com/karmaterminal/binary-canticle/issues/99).

## Not in this kit

- Applying it to any host. Each host owner does that with their own go.
- Multicast (`pilot.conf` fixes `--no-multicast`; RFC §11.2), prince publishing, a separate uid (#99), and IPv6
  (the daemon binds IPv4 only).
- The round 2b daemon-loss proof: its run card is
  [`../../proofs/pilot/round-2b-daemon-loss.md`](../../proofs/pilot/round-2b-daemon-loss.md) (#104).

[`../../tests/test_pilot_host.py`](../../tests/test_pilot_host.py) runs the guard against stub `sudo` and `nft`,
checks and loads the table with the real nft in a throwaway network namespace, and checks the units and this
page's worked examples. CI runs the nft part as root ([`tests.yml`](../../../../.github/workflows/tests.yml)).
