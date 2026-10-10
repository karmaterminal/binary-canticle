"""The LAN pilot-host kit (``docs/pilot-host/``, #103): the daemon's start guard, the nft table, the units.

``GuardTest`` runs the shipped guard under every POSIX shell found here (dash is Debian's ``/bin/sh``, bash is
Arch's), with stub ``id``, ``sudo`` and ``nft`` first on PATH: no root, no nft, no host firewall.

``NftTest`` checks and loads the shipped table with the real nft, inside a throwaway network namespace, so
nothing reaches the host's own ruleset. That needs nft and either root or unprivileged user namespaces; without
them it skips and says why, unless ``CANTICLE_REQUIRE_NFT=1`` (CI's nft step) makes a skip a failure.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
KIT = DOCS / "pilot-host"
GUARD = KIT / "canticle-pilot-guard.sh"
TABLE = KIT / "canticle-pilot.nft"

# The two current pilot hosts (#103; interfaces from round 1, #65).
HOSTS = {
    "silas": {"local": "10.0.0.100", "lan_if": "wlan0", "peers": ["10.0.0.246"], "station": "frond-gloss"},
    "ronan": {"local": "10.0.0.246", "lan_if": "enP7s7", "peers": ["10.0.0.100"], "station": "frond-scribe"},
}
STUB_ID = """#!/bin/sh
[ "${1-}" = -u ] || { echo "stub id: unexpected arguments: $*" >&2; exit 97; }
echo "${STUB_UID:-1000}"
"""
STUB_SUDO = """#!/bin/sh
printf 'sudo %s\\n' "$*" >>"$STUB_LOG"
case ${STUB_SUDO-} in
password) echo 'sudo: a password is required' >&2; exit 1 ;;
nnp) echo 'sudo: The "no new privileges" flag is set, which prevents sudo from running as root.' >&2; exit 1 ;;
esac
[ "${1-}" = -n ] || { echo "stub sudo: called without -n: $*" >&2; exit 99; }
shift
exec "$@"
"""
STUB_NFT = """#!/bin/sh
printf 'nft %s\\n' "$*" >>"$STUB_LOG"
case ${STUB_NFT-} in
missing) printf 'Error: No such file or directory\\nlist table inet canticle\\n                 ^^^^^^^^\\n' >&2; exit 1 ;;
eperm) printf 'Operation not permitted (you must be root)\\nnetlink: Error: cache initialization failed: Operation not permitted\\n' >&2; exit 1 ;;
esac
[ "$*" = "list table inet canticle" ] || { echo "stub nft: unexpected arguments: $*" >&2; exit 98; }
cat "$STUB_LISTING"
"""
READ = ["sudo -n nft list table inet canticle", "nft list table inet canticle"]


def listing(local, lan_if, peers, port=9999, hook="input", verdict="drop", rules=("iif", "src")) -> str:
    """``nft list table inet canticle`` for a loaded canticle-pilot.nft, as nft 1.0.9 prints it (NftTest pins
    this against the real nft)."""
    saddr = peers[0] if len(peers) == 1 else "{ " + ", ".join(peers) + " }"
    lines = ["table inet canticle {", "\tchain in {",
             f"\t\ttype filter hook {hook} priority filter - 10; policy accept;"]
    if "iif" in rules:
        lines.append(f'\t\tip daddr {local} udp dport {port} iifname != "{lan_if}" counter packets 0 bytes 0 {verdict}')
    if "src" in rules:
        lines.append(f"\t\tip daddr {local} udp dport {port} ip saddr != {saddr} counter packets 0 bytes 0 {verdict}")
    return "\n".join(lines + ["\t}", "}"]) + "\n"


def host_listing(name: str) -> str:
    h = HOSTS[name]
    return listing(h["local"], h["lan_if"], h["peers"])


def table_for(local, lan_if, peers, port=9999) -> str:
    """canticle-pilot.nft with its four defines set, the way the README's step 1 sets them."""
    text = TABLE.read_text()
    values = {"LOCAL": local, "LAN_IF": f'"{lan_if}"', "PEERS": "{ " + ", ".join(peers) + " }", "PORT": str(port)}
    for name, value in values.items():
        text, n = re.subn(rf"^define {name} = .*$", f"define {name} = {value}", text, flags=re.M)
        assert n == 1, f"canticle-pilot.nft has {n} 'define {name}' lines"
    return text


def shells() -> list:
    """Each distinct POSIX shell on this host: dash and bash are the pilot hosts' /bin/sh."""
    found, seen = [], set()
    for name in ("sh", "dash", "bash"):
        path = shutil.which(name)
        if path and os.path.realpath(path) not in seen:
            seen.add(os.path.realpath(path))
            found.append(path)
    return found


class GuardTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.stubs = Path(cls.tmp.name) / "bin"
        cls.stubs.mkdir()
        for name, text in (("id", STUB_ID), ("sudo", STUB_SUDO), ("nft", STUB_NFT)):
            (cls.stubs / name).write_text(text)
            (cls.stubs / name).chmod(0o755)
        cls.shells = shells()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def guard(self, shell, bind="10.0.0.100:9999", *, table=None, uid=1000, nft=None, sudo=None):
        """Run the guard once: (exit status, stderr, the stub calls in order). ``bind=None`` leaves it unset."""
        work = Path(tempfile.mkdtemp(dir=self.tmp.name))
        log, table_file = work / "calls.log", work / "listing.txt"
        log.write_text("")
        table_file.write_text(table if table is not None else host_listing("silas"))
        env = {"PATH": f"{self.stubs}{os.pathsep}/usr/bin{os.pathsep}/bin", "LC_ALL": "C", "STUB_LOG": str(log),
               "STUB_LISTING": str(table_file), "STUB_UID": str(uid), "STUB_NFT": nft or "", "STUB_SUDO": sudo or ""}
        if bind is not None:
            env["CANTICLE_BIND"] = bind
        p = subprocess.run([shell, str(GUARD)], env=env, capture_output=True, text=True, timeout=30)
        return p.returncode, p.stderr, log.read_text().splitlines()

    def assertRefused(self, result, status, *phrases, calls=None):
        code, err, made = result
        self.assertEqual(code, status, err)
        self.assertTrue(err.startswith("canticle-pilot-guard: refusing to start the daemon: "), err)
        self.assertEqual(len(err.splitlines()), 1, err)
        for phrase in phrases:
            self.assertIn(phrase, err)
        if calls is not None:
            self.assertEqual(made, calls)

    def test_found_a_shell(self):
        self.assertTrue(self.shells, "no POSIX shell on PATH")

    def test_wildcard_bind_refused_before_the_table_is_read(self):
        for shell in self.shells:
            for bind in ("0.0.0.0:9999", "0.0.0.0", "*:9999", "*", "::", ":::9999", "[::]", "[::]:9999"):
                with self.subTest(shell=shell, bind=bind):
                    self.assertRefused(self.guard(shell, bind), 78, "listens on every address", calls=[])
            with self.subTest(shell=shell, bind=":9999"):
                self.assertRefused(self.guard(shell, ":9999"), 78, "has no address", calls=[])

    def test_unset_or_malformed_bind_refused_before_the_table_is_read(self):
        bad = {
            None: "empty or unset", "": "empty or unset",
            "10.0.0.100": "has no port", "silas": "has no port",
            "[::1]:9999": "is IPv6", "fe80::1:9999": "is IPv6", "::1": "is IPv6",
            "10.0.0.100:": "the port must be", "10.0.0.100:0": "the port must be",
            "10.0.0.100:099": "the port must be", "10.0.0.100:65536": "the port must be",
            "10.0.0.100:999999": "the port must be", "10.0.0.100:99a": "the port must be",
            "10.0.0.100:9999 ": "the port must be", "10.0.0.100:-1": "the port must be",
            "silas:9999": "is not an IPv4 address", "localhost:9999": "is not an IPv4 address",
            " 10.0.0.100:9999": "is not an IPv4 address", "10.0.0.256:9999": "is not an IPv4 address",
            "10.0.0:9999": "is not an IPv4 address", "10.0.0.1.2:9999": "is not an IPv4 address",
            "010.0.0.100:9999": "is not an IPv4 address", "10.0.0.0100:9999": "is not an IPv4 address",
            "10..0.100:9999": "is not an IPv4 address", ".10.0.0.100:9999": "is not an IPv4 address",
            "10.0.0.100.:9999": "is not an IPv4 address", "10.0.0.*:9999": "is not an IPv4 address",
        }
        for shell in self.shells:
            for bind, why in bad.items():
                with self.subTest(shell=shell, bind=bind):
                    self.assertRefused(self.guard(shell, bind), 78, why, calls=[])
            with self.subTest(shell=shell, bind="a newline"):
                code, err, made = self.guard(shell, "10.0.0.100\n:9999")
                self.assertEqual((code, made), (78, []), err)
                self.assertIn("is not an IPv4 address", err)

    def test_missing_table_refused(self):
        for shell in self.shells:
            with self.subTest(shell=shell):
                self.assertRefused(self.guard(shell, nft="missing"), 69, "No such file or directory",
                                   "is not loaded: sudo systemctl start canticle-nft.service", calls=READ)

    def test_unreadable_table_refused(self):
        for shell in self.shells:
            with self.subTest(shell=shell, sudo="password"):
                self.assertRefused(self.guard(shell, sudo="password"), 69, "a password is required",
                                   "add the sudo rule (README.md, step 3)", calls=READ[:1])
            with self.subTest(shell=shell, sudo="nnp"):
                self.assertRefused(self.guard(shell, sudo="nnp"), 69, "ExecStartPre=+", calls=READ[:1])
            with self.subTest(shell=shell, uid=0, nft="eperm"):
                self.assertRefused(self.guard(shell, uid=0, nft="eperm"), 69, "Operation not permitted",
                                   calls=READ[1:])

    def test_table_must_scope_exactly_this_bind(self):
        silas = HOSTS["silas"]
        wrong = {
            "the sample defines": listing("192.0.2.10", "lan0", ["192.0.2.20"]),
            "another host's address": host_listing("ronan"),
            "a prefix of the address": listing("10.0.0.10", "wlan0", ["10.0.0.246"]),
            "a longer address": listing("10.0.0.1000", "wlan0", ["10.0.0.246"]),
            "another port": listing(silas["local"], "wlan0", silas["peers"], port=99999),
            "a prefix of the port": listing(silas["local"], "wlan0", silas["peers"], port=999),
            "no interface drop": listing(silas["local"], "wlan0", silas["peers"], rules=("src",)),
            "no source drop": listing(silas["local"], "wlan0", silas["peers"], rules=("iif",)),
            "the output hook": listing(silas["local"], "wlan0", silas["peers"], hook="output"),
            "accept, not drop": listing(silas["local"], "wlan0", silas["peers"], verdict="accept"),
            "the interface rule accepts": host_listing("silas").replace('"wlan0" counter packets 0 bytes 0 drop',
                                                                          '"wlan0" counter packets 0 bytes 0 accept'),
            "the source rule accepts": host_listing("silas").replace("10.0.0.246 counter packets 0 bytes 0 drop",
                                                                       "10.0.0.246 counter packets 0 bytes 0 accept"),
            "an empty table": "table inet canticle {\n}\n",
            # Drops nothing reaches: in a chain without the hook, or after a rule that lets the datagram past.
            "the drops in a chain without the hook": host_listing("silas").replace(
                "policy accept;\n", "policy accept;\n\t}\n\tchain stale {\n"),
            "an accept before the drops": host_listing("silas").replace(
                "policy accept;\n", "policy accept;\n\t\tip daddr 10.0.0.100 udp dport 9999 accept\n"),
            "an accept between the drops": host_listing("silas").replace(
                "drop\n", "drop\n\t\tudp dport 9999 accept\n", 1),
            "a jump before the drops": host_listing("silas").replace(
                "policy accept;\n", "policy accept;\n\t\tudp dport 9999 jump allow\n"),
            "a return before the drops": host_listing("silas").replace(
                "policy accept;\n", "policy accept;\n\t\tip saddr 10.0.0.0/24 return\n"),
        }
        for shell in self.shells:
            for why, table in wrong.items():
                with self.subTest(shell=shell, table=why):
                    self.assertRefused(self.guard(shell, "10.0.0.100:9999", table=table), 65,
                                       "doesn't drop datagrams to 10.0.0.100:9999", calls=READ)

    def test_scoped_table_passes(self):
        for shell in self.shells:
            for name, h in HOSTS.items():
                bind = f"{h['local']}:9999"
                with self.subTest(shell=shell, host=name):
                    code, err, made = self.guard(shell, bind, table=host_listing(name))
                    self.assertEqual(code, 0, err)
                    self.assertEqual(err, f"canticle-pilot-guard: ok: bind {bind}; table inet canticle drops "
                                          "datagrams to it from other interfaces and other sources\n")
                    self.assertEqual(made, READ)
            with self.subTest(shell=shell, peers=2):
                table = listing("10.0.0.100", "wlan0", ["10.0.0.246", "10.0.0.250"])
                code, err, made = self.guard(shell, table=table)
                self.assertEqual(code, 0, err)
            with self.subTest(shell=shell, after="an accept after both drops"):
                # Both drops have run by then: nothing it accepts was going to be dropped.
                table = host_listing("silas").replace("\t}\n}", "\t\tudp dport 9999 accept\n\t}\n}")
                code, err, made = self.guard(shell, table=table)
                self.assertEqual(code, 0, err)
            with self.subTest(shell=shell, uid=0):
                code, err, made = self.guard(shell, uid=0)
                self.assertEqual(code, 0, err)
                self.assertEqual(made, READ[1:], "as root the guard reads the table without sudo")


def _netns() -> tuple:
    """(argv prefix that runs a command as root in a new, empty network namespace, nft path), or (None, reason)."""
    nft = shutil.which("nft") or next((p for p in ("/usr/sbin/nft", "/sbin/nft") if os.access(p, os.X_OK)), None)
    unshare = shutil.which("unshare")
    if nft is None or unshare is None:
        return None, f"{'nft' if nft is None else 'unshare'} is not installed"
    prefixes = ([[unshare, "--net"]] if os.geteuid() == 0 else []) + [[unshare, "--user", "--map-root-user", "--net"]]
    why = []
    for prefix in prefixes:
        try:
            p = subprocess.run(prefix + [nft, "list", "ruleset"], capture_output=True, text=True, timeout=30)
        except OSError as e:
            why.append(f"{' '.join(prefix[1:])}: {e}")
            continue
        if p.returncode == 0:
            return prefix, nft
        why.append(f"{' '.join(prefix[1:])}: {(p.stderr.strip() or 'exit %d' % p.returncode).splitlines()[0]}")
    return None, "no network namespace where nft may run (needs root or unprivileged user namespaces): " + "; ".join(why)


class NftTest(unittest.TestCase):
    """The shipped table with the real nft, in a throwaway network namespace."""

    @classmethod
    def setUpClass(cls):
        cls.prefix, cls.nft = _netns()
        if cls.prefix is None:
            if os.environ.get("CANTICLE_REQUIRE_NFT") == "1":
                raise AssertionError(f"CANTICLE_REQUIRE_NFT=1, but {cls.nft}")
            raise unittest.SkipTest(cls.nft)
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def netns(self, script: str, *args) -> subprocess.CompletedProcess:
        """Run a sh script in a new network namespace; $1 is nft, then ``args``."""
        return subprocess.run(self.prefix + ["sh", "-c", script, "sh", self.nft, *map(str, args)],
                              capture_output=True, text=True, timeout=60)

    def write(self, name: str, text: str) -> Path:
        path = Path(self.tmp.name) / name
        path.write_text(text)
        return path

    def test_shipped_table_checks(self):
        p = self.netns('"$1" -c -f "$2"', TABLE)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_host_tables_load_twice_as_one_table(self):
        for name, h in HOSTS.items():
            with self.subTest(host=name):
                path = self.write(f"{name}.nft", table_for(h["local"], h["lan_if"], h["peers"]))
                p = self.netns('"$1" -c -f "$2" && "$1" -f "$2" && "$1" -f "$2" && "$1" list ruleset', path)
                self.assertEqual(p.returncode, 0, p.stderr)
                # Loading again replaces the table: one table, two drops, never four. This is also the listing the
                # guard tests feed their stub nft, and the one the README shows.
                self.assertEqual(p.stdout, host_listing(name))

    def test_two_peers_list_as_a_set(self):
        path = self.write("two.nft", table_for("10.0.0.100", "wlan0", ["10.0.0.246", "10.0.0.250"]))
        p = self.netns('"$1" -f "$2" && "$1" list table inet canticle', path)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, listing("10.0.0.100", "wlan0", ["10.0.0.246", "10.0.0.250"]))

    def test_guard_reads_the_real_table(self):
        h = HOSTS["silas"]
        path = self.write("guard.nft", table_for(h["local"], h["lan_if"], h["peers"]))
        script = """
            nft=$1 table=$2 guard=$3
            "$nft" -f "$table" || exit 1
            CANTICLE_BIND=10.0.0.100:9999 sh "$guard"; echo "scoped=$?"
            CANTICLE_BIND=10.0.0.246:9999 sh "$guard"; echo "other=$?"
            "$nft" delete table inet canticle || exit 1
            CANTICLE_BIND=10.0.0.100:9999 sh "$guard"; echo "missing=$?"
        """
        p = self.netns(script, path, GUARD)
        self.assertEqual(p.stdout.split(), ["scoped=0", "other=65", "missing=69"], p.stderr)
        self.assertIn("ok: bind 10.0.0.100:9999", p.stderr)
        self.assertIn("is not loaded: sudo systemctl start canticle-nft.service", p.stderr)

    def test_guard_refuses_drops_nothing_reaches(self):
        """#104 review: drops in a chain without the hook, or after an accept, scope nothing; the real nft's
        listing of each is refused."""
        drops = ('ip daddr 10.0.0.100 udp dport 9999 iifname != "wlan0" counter drop\n'
                 "ip daddr 10.0.0.100 udp dport 9999 ip saddr != 10.0.0.246 counter drop\n")
        hook = "type filter hook input priority -10; policy accept;\n"
        tables = {
            "another chain": "table inet canticle {\nchain in {\n" + hook + "}\nchain stale {\n" + drops + "}\n}\n",
            "an accept first": ("table inet canticle {\nchain in {\n" + hook
                                + "ip daddr 10.0.0.100 udp dport 9999 accept\n" + drops + "}\n}\n"),
        }
        script = '"$1" -f "$2" || exit 1; CANTICLE_BIND=10.0.0.100:9999 sh "$3"; echo "status=$?"'
        for why, text in tables.items():
            with self.subTest(table=why):
                p = self.netns(script, self.write("bypass.nft", text), GUARD)
                self.assertEqual(p.stdout.split(), ["status=65"], p.stderr)
                self.assertIn("doesn't drop datagrams to 10.0.0.100:9999", p.stderr)

    def test_a_quoted_variable_is_not_expanded(self):
        """Why the kit writes $LAN_IF bare (README.md, Worked examples): #103's sketch quoted it."""
        text = table_for("10.0.0.100", "wlan0", ["10.0.0.246"]).replace("iifname != $LAN_IF", 'iifname != "$LAN_IF"')
        path = self.write("quoted.nft", text)
        p = self.netns('"$1" -f "$2" && "$1" list table inet canticle', path)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('iifname != "$LAN_IF"', p.stdout)


def _settings(path: Path) -> list:
    """(key, value) for each setting line of a unit file, in order (repeated keys kept)."""
    out = []
    for line in path.read_text().splitlines():
        if line and not line.startswith(("#", ";", "[")) and "=" in line:
            key, _, value = line.partition("=")
            out.append((key.strip(), value.strip()))
    return out


class UnitFilesTest(unittest.TestCase):
    """What systemd can't check for us: the kit's units say what the README and the guard rely on."""

    def test_daemon_drop_in(self):
        s = _settings(KIT / "canticle-daemon.service.d" / "pilot.conf")
        # Without "-", a missing pilot.env fails the start; with "+" the guard runs without NoNewPrivileges; a
        # "-" before the guard would ignore its refusal.
        self.assertIn(("EnvironmentFile", "%h/.binary-canticle/pilot.env"), s)
        self.assertIn(("ExecStartPre", "+/bin/sh %h/.binary-canticle/canticle-pilot-guard.sh"), s)
        starts = [v for k, v in s if k == "ExecStart"]
        self.assertEqual(starts[0], "", "the drop-in must reset the base unit's ExecStart first")
        self.assertEqual(len(starts), 2)
        argv = starts[1].split()
        base = [v for k, v in _settings(DOCS / "systemd" / "canticle-daemon.service") if k == "ExecStart"]
        self.assertEqual(argv[:2], base[0].split()[:2], "the same canticle, from the same venv")
        for flag, value in (("--stations", "%h/.binary-canticle/stations.toml"), ("--bind", "${CANTICLE_BIND}"),
                            ("--socket", "%t/canticle/daemon.sock")):
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertIn("--no-multicast", argv)
        self.assertNotIn("--multicast", argv)
        self.assertNotIn("--manifest", argv)

    def test_firewall_unit(self):
        s = _settings(KIT / "canticle-nft.service")
        self.assertIn(("Type", "oneshot"), s)
        self.assertIn(("RemainAfterExit", "yes"), s)
        self.assertIn(("ExecStart", "/usr/sbin/nft -f /etc/canticle/canticle-pilot.nft"), s)
        before = " ".join(v for k, v in s if k == "Before").split()
        self.assertIn("network-pre.target", before)
        # logind starts every user manager (a lingering one when logind starts), so the daemon comes after the
        # table at boot. systemd-user-sessions.service would not do: user@.service dropped that order in v252.
        self.assertIn("systemd-logind.service", before)
        # Stopping or disabling the unit must never open the port under a running daemon.
        self.assertNotIn("ExecStop", [k for k, _ in s])

    def test_station_template_destination(self):
        s = _settings(DOCS / "systemd" / "canticle-station@.service")
        keys = [k for k, _ in s]
        self.assertIn(("Environment", "CANTICLE_STATION_TO=127.0.0.1:9999"), s)
        # EnvironmentFile overrides Environment whatever their order; keeping the default first reads that way.
        self.assertLess(keys.index("Environment"), keys.index("EnvironmentFile"))
        start = dict(s)["ExecStart"].split()
        self.assertEqual(start[start.index("--to") + 1], "${CANTICLE_STATION_TO}")
        self.assertEqual(start[-1], "$CANTICLE_STATION_ARGS")

    def test_readme_worked_examples_match_the_tested_values(self):
        readme = (KIT / "README.md").read_text()
        for name, h in HOSTS.items():
            peer = h["peers"][0]
            with self.subTest(host=name):
                for line in (f"define LOCAL = {h['local']}", f'define LAN_IF = "{h["lan_if"]}"',
                             f"define PEERS = {{ {peer} }}", f"CANTICLE_BIND={h['local']}:9999",
                             f"CANTICLE_STATION_TO={peer}:9999", f"station-{h['station']}.env"):
                    self.assertIn(line, readme)
                self.assertIn(host_listing(name), readme)

    def test_readme_applies_the_firewall_before_the_daemon(self):
        readme = (KIT / "README.md").read_text()
        order = [readme.index(s) for s in ("sudo systemctl enable --now canticle-nft.service",
                                           "sudo nft list table inet canticle\n",
                                           "systemctl --user enable --now canticle-daemon",
                                           'systemctl --user enable --now "canticle-station@$NAME"',
                                           "canticle tap --tune frond-scribe:chatter")]
        self.assertEqual(order, sorted(order))


if __name__ == "__main__":
    unittest.main()
