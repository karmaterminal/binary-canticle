"""``stations.toml``: the static locator file (RFC-0001 §13.6).

It says where this host's fleet manifest is and where its listener hears. It
holds locators only, never trust: names and keys come from the manifest (§5.3,
§10.3). ``canticle listen`` and ``canticle doctor`` read it when no
``--manifest`` is given. The schema is in ``docs/stations-toml.md``.

Every key is checked, and an unknown one is an error, so a misspelt key fails
loudly instead of leaving its default in place.
"""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .runner import DEFAULT_PORT

DEFAULT_PATH = "~/.binary-canticle/stations.toml"
VERSION = 1
DEFAULT_BIND = f"0.0.0.0:{DEFAULT_PORT}"
KEYS = {"": ("version", "manifest", "listen"), "manifest.": ("path",), "listen.": ("bind", "multicast")}
TRUST = ("[trust] (the genesis pin, RFC §10.3) is not supported: this spike's manifest is unsigned, so a pin "
         "could not be enforced, and a pin that is silently ignored is worse than none")


class StationsError(ValueError):
    """stations.toml is invalid; the message names the file and the key."""


class StationsMissing(StationsError):
    """stations.toml does not exist."""


@dataclass(frozen=True)
class Stations:
    path: Path        # the file read, absolute
    manifest: Path    # absolute; a relative path in the file is relative to the file
    bind: str         # IPv4 address and port the listener binds, "host:port"
    multicast: bool   # join the group (runner.MCAST_GROUP); off unless the file says true


def default_path() -> Path:
    return Path(os.path.expanduser(DEFAULT_PATH))


def load(path=None) -> Stations:
    import tomllib  # imported here, so that `canticle doctor` can still report a Python older than 3.11

    p = Path(os.path.abspath(os.path.expanduser(os.fspath(path)))) if path is not None else default_path()
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise StationsMissing(f"{p}: not found") from None
    except (OSError, UnicodeDecodeError) as e:
        raise StationsError(f"{p}: {e}") from None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise StationsError(f"{p}: not valid TOML: {e}") from None
    return parse(data, p)


def parse(data: dict, path: Path) -> Stations:
    def bad(msg: str) -> StationsError:
        return StationsError(f"{path}: {msg}")

    _only(data, "", bad)
    version = data.get("version")
    if type(version) is not int or version != VERSION:
        raise bad(f"version must be {VERSION}, not {version!r}" if "version" in data else f"version = {VERSION} is required")
    manifest = data.get("manifest")
    if not isinstance(manifest, dict):
        raise bad('a [manifest] table with path = "..." is required')
    _only(manifest, "manifest.", bad)
    where = manifest.get("path")
    if not isinstance(where, str) or not where:
        raise bad("manifest.path must be a non-empty string")
    listen = data.get("listen", {})
    if not isinstance(listen, dict):
        raise bad("listen must be a table")
    _only(listen, "listen.", bad)
    bind = listen.get("bind", DEFAULT_BIND)
    problem = bind_problem(bind)
    if problem:
        raise bad(f"listen.bind {bind!r}: {problem}")
    multicast = listen.get("multicast", False)
    if type(multicast) is not bool:
        raise bad("listen.multicast must be true or false")
    resolved = Path(os.path.expanduser(where))
    return Stations(path=path, manifest=Path(os.path.abspath(path.parent / resolved)), bind=bind, multicast=multicast)


def bind_problem(bind) -> str:
    """Why ``bind`` is not an IPv4 "address:port" the listener can bind, or "" when it is."""
    if not isinstance(bind, str):
        return "must be a string"
    host, sep, port = bind.rpartition(":")
    if not sep or not re.fullmatch(r"[0-9]{1,5}", port) or not 0 < int(port) < 65536:
        return "must be IPv4-address:port, with a port from 1 to 65535"
    try:
        ipaddress.IPv4Address(host)
    except ValueError:
        return f"{host!r} is not an IPv4 address (the listener is IPv4 only; 0.0.0.0 hears every interface)"
    return ""


def _only(table: dict, prefix: str, bad) -> None:
    for k in table:
        if k not in KEYS[prefix]:
            if prefix == "" and k == "trust":
                raise bad(TRUST)
            raise bad(f"unknown key {prefix}{k} (allowed here: {', '.join(KEYS[prefix])})")
