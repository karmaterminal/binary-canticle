"""Opt-in, station-owned cue table (#147, parent #120).

This is a local operator control extension, not a wire message or a world clock.
The station serializes commands and ticks. A durable claim precedes the one sing;
an uncertain claim is never reissued. Existing carousel repeats keep its identity.
"""

from __future__ import annotations

from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from . import wire
from .ids import CLASS_BY_NAME, SCOPES
from .station import STOP_BEFORE_EXPIRY_MS, Station

FORMAT = "canticle-cues/1"
MAX_ROWS = 1024
MAX_TEXT_BYTES = 800
MAX_DELAY_S = 86_400
MAX_DURATION_S = 3600
MAX_NOT_AFTER_MS = (1 << 53) - 1  # exact integer across JSON/JavaScript clients
MAX_LIST = 32
MIN_DISPATCH_MS = 1000
_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}\Z")


def _integer(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} to {high}")
    return value


def _cue_id(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("cue id must be 1-64 ASCII letters, digits, '.', '_' or '-', starting alphanumeric")
    return value


def _state_key(cue_id):
    return "cue:" + hashlib.sha256(cue_id.encode()).hexdigest()[:28]


class CueStore:
    """A private, bounded SQLite queue leased to one station process.

    All calls belong on the station's serialized thread. SQLite FULL commits make
    the pre-effect claim durable; failure to store an outcome must stop the station,
    rather than resume polling an unrecorded acceptance. No queue method sends UDP.
    """

    def __init__(self, path, station: Station, *, now_ms: int):
        self.path = Path(path).absolute()
        self.station = station
        self.db = None
        self.fd = None
        parent = self.path.parent.stat()
        if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) & 0o077:
            raise ValueError("cue database needs an owner-only directory (mode 0700)")
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
        try:
            self.fd = os.open(self.path, flags, 0o600)
            info = os.fstat(self.fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise ValueError("cue database must be an owned, singly linked regular file with mode 0600")
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.db = sqlite3.connect(self.path, timeout=0)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA secure_delete=ON")
            tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not tables and info.st_size == 0:
                self.db.executescript("""
                    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE cues (
                        id TEXT PRIMARY KEY, request TEXT NOT NULL, stream TEXT NOT NULL,
                        cls TEXT NOT NULL, text TEXT NOT NULL, loop TEXT NOT NULL,
                        created_at INTEGER NOT NULL, starts_at INTEGER NOT NULL, ends_at INTEGER NOT NULL,
                        state TEXT NOT NULL, detail TEXT, claimed_epoch INTEGER, candidate_seq INTEGER,
                        result TEXT, cancellation TEXT, hush TEXT, updated_at INTEGER NOT NULL
                    );
                    CREATE INDEX due_cues ON cues(state, starts_at, id);
                """)
                with self.db:
                    self.db.executemany("INSERT INTO meta VALUES (?, ?)", (
                        ("format", FORMAT), ("public_key", wire.public_key_bytes(station.sk).hex()),
                        ("watermark", str(now_ms)), ("last_dispatch", "0")))
                # Persist the new filename as well as SQLite's contents.
                dfd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            elif tables != {"meta", "cues"}:
                raise ValueError("not a cue database; refusing to modify it")
            if self._meta("format") != FORMAT:
                raise ValueError("unsupported cue database format")
            if self._meta("public_key") != wire.public_key_bytes(station.sk).hex():
                raise ValueError("cue database belongs to a different station key; use its original key or a fresh database")
            self.watermark = int(self._meta("watermark"))
            self.last_dispatch = int(self._meta("last_dispatch"))
            self._saved_watermark = self.watermark
            # A claim may have crossed sing without storing its result. A prior
            # acceptance belonged to a volatile carousel that no longer exists.
            with self.db:
                self.db.execute("UPDATE cues SET state='unknown', detail='station restarted after claim; not retried', "
                                "updated_at=? WHERE state='claimed'", (now_ms,))
                self.db.execute("UPDATE cues SET state='interrupted', detail='station restarted; accepted item not replayed', "
                                "updated_at=? WHERE state='accepted'", (now_ms,))
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _meta(self, key):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if row is None:
            raise ValueError("incomplete cue database metadata")
        return row[0]

    def _row(self, cue_id):
        row = self.db.execute("SELECT * FROM cues WHERE id=?", (_cue_id(cue_id),)).fetchone()
        if row is None:
            raise ValueError("unknown cue id")
        return row

    def _update(self, cue_id, now, **values):
        values["updated_at"] = now
        with self.db:
            self.db.execute("UPDATE cues SET " + ", ".join(f"{k}=?" for k in values) + " WHERE id=?",
                            (*values.values(), cue_id))

    def _observe(self, now, *, durable=False):
        forward = now >= self.watermark
        self.watermark = max(now, self.watermark)
        if durable or self.watermark - self._saved_watermark >= 1000:
            with self.db:
                self.db.execute("UPDATE meta SET value=? WHERE key='watermark'", (str(self.watermark),))
            self._saved_watermark = self.watermark
        return forward

    def _authority(self, stream, cls, duration_s, socket_classes, grant):
        if grant is None or grant.revoked or grant.public_key != wire.public_key_bytes(self.station.sk):
            raise ValueError("cue has no current active manifest grant for this station")
        st = self.station.streams.get(stream)
        if st is None or st.cfg.cls != cls:
            raise ValueError("cue stream is absent or its configured class changed")
        if cls not in {"ambient", "chatter"} or cls not in socket_classes:
            raise ValueError("cues require ambient/chatter granted to this control socket")
        spec = CLASS_BY_NAME[cls]
        if spec.code not in grant.classes or SCOPES["lan"] not in grant.scopes:
            raise ValueError("cue class or LAN scope is not currently granted")
        if grant.streams and stream not in grant.streams:
            raise ValueError("cue stream is not currently granted")
        if self.station.host_binding:
            raise ValueError("cue worker requires the UDP station binding")
        if duration_s > min(st.cfg.default_ttl_s, st.cfg.max_ttl_s, spec.max_ttl_s):
            raise ValueError("cue duration exceeds the effective stream default TTL; configure an adequate TTL first")

    @staticmethod
    def _grant(loader):
        if loader is None:
            raise ValueError("cue worker needs a current manifest loader")
        try:
            return loader()
        except (OSError, ValueError, KeyError, TypeError) as e:
            # Do not echo malformed manifest contents or queued text into receipts.
            raise ValueError(f"current cue manifest cannot be read ({type(e).__name__})") from e

    def add(self, req, now, socket_classes, grant_loader):
        cue_id = _cue_id(req.get("id"))
        delay = _integer(req.get("in"), "in", 0, MAX_DELAY_S)
        duration = _integer(req.get("for"), "for", 1, MAX_DURATION_S)
        not_after = (_integer(req["not_after"], "not_after", 0, MAX_NOT_AFTER_MS)
                     if "not_after" in req else None)
        stream, text, loop = req.get("stream"), req.get("text"), req.get("loop", "normal")
        if not isinstance(stream, str) or stream not in self.station.streams:
            raise ValueError("cue needs a configured stream")
        if not isinstance(text, str) or not 1 <= len(text.encode("utf-8")) <= MAX_TEXT_BYTES:
            raise ValueError(f"cue text must be 1-{MAX_TEXT_BYTES} UTF-8 bytes")
        if loop not in {"fast", "normal", "slow"}:
            raise ValueError("cue loop must be fast, normal or slow")
        binding = [stream, text, delay, duration, loop]
        if not_after is not None:
            binding.append(not_after)
        # Preserve the exact original relative-form identity in existing tables.
        request = json.dumps(binding, ensure_ascii=True, separators=(",", ":"))
        old = self.db.execute("SELECT * FROM cues WHERE id=?", (cue_id,)).fetchone()
        if old is not None:
            if old["request"] != request:
                raise ValueError("cue id already binds a different request; cancel and choose a new id")
            return self._public(old)  # Retry never moves the original start/end.
        if not self._observe(now, durable=True):
            raise ValueError("cue clock moved backwards; creation held until the recorded watermark")
        cls = self.station.streams[stream].cfg.cls
        self._authority(stream, cls, duration, socket_classes, self._grant(grant_loader))
        if self.db.execute("SELECT count(*) FROM cues").fetchone()[0] >= MAX_ROWS:
            raise ValueError(f"cue table full ({MAX_ROWS} rows); retain receipts and use a fresh run database")
        start = now + delay * 1000
        end = start + duration * 1000
        if not_after is not None:
            end = min(end, not_after)
        # A first request can already have missed its originator's deadline.
        # Persist the same immutable request/receipt, but never make it eligible
        # for a claim, even if the station clock subsequently moves backwards.
        state = "missed" if end <= start + STOP_BEFORE_EXPIRY_MS else "pending"
        detail = "originator deadline left no playable window before acceptance" if state == "missed" else None
        with self.db:
            self.db.execute("INSERT INTO cues (id,request,stream,cls,text,loop,created_at,starts_at,ends_at,state,detail,updated_at) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (cue_id, request, stream, cls, text, loop, now, start, end, state, detail, now))
        return self.show(cue_id)

    def _public(self, row):
        text = row["text"].encode("utf-8")
        result = json.loads(row["result"]) if row["result"] else None
        binding = json.loads(row["request"])
        return {"id": row["id"], "station_key_id": self.station.key_id.hex(), "stream": row["stream"],
                "class": row["cls"], "scope": "lan", "state": row["state"], "loop": row["loop"],
                "created_at": row["created_at"], "starts_at": row["starts_at"], "ends_at": row["ends_at"],
                "not_after": binding[5] if len(binding) == 6 else None,
                "updated_at": row["updated_at"], "text_bytes": len(text), "text_sha256": hashlib.sha256(text).hexdigest(),
                "claimed_epoch": row["claimed_epoch"], "candidate_seq": row["candidate_seq"],
                "detail": row["detail"], "acceptance": result,
                "late_start_ms": max(0, result["issued_at"] - row["starts_at"]) if result else None,
                "cancellation": row["cancellation"], "hush": json.loads(row["hush"]) if row["hush"] else None,
                "remote_receipt": "not_proved"}

    def show(self, cue_id):
        return self._public(self._row(cue_id))

    def listing(self, limit=MAX_LIST, after=""):
        _integer(limit, "limit", 1, MAX_LIST)
        if after:
            _cue_id(after)
        rows = self.db.execute("SELECT * FROM cues WHERE id>? ORDER BY id LIMIT ?", (after, limit + 1)).fetchall()
        return {"cues": [self._public(r) for r in rows[:limit]],
                "next_after": rows[limit - 1]["id"] if len(rows) > limit else None,
                "clock_watermark": self.watermark, "max_rows": MAX_ROWS}

    def _target(self, row):
        # Epoch plus exact candidate tuple plus our state key: never hush a new
        # epoch's unrelated sequence after restart, even when seq numbers match.
        if row["claimed_epoch"] != self.station.epoch:
            return None
        stream = self.station.streams.get(row["stream"])
        target = stream.ring.get(row["candidate_seq"]) if stream else None
        if target is not None and target.kind == wire.KIND_ITEM and target.state_key == _state_key(row["id"]):
            return target
        return None

    def _stop(self, row, now):
        if self._target(row) is None:
            return "local_not_on_air; remote_expiry_or_prior_pluck_only", None
        try:
            result = self.station.hush(now, row["stream"], row["candidate_seq"]).to_json()
            return "local_stopped; pluck_accepted_remote_delivery_not_proved", json.dumps(result)
        except Exception as e:
            # Capacity/near-expiry refusal must not keep an elected cancellation
            # playing. Remove only this cue's verified local ITEM; no remote erase
            # claim and no blind retry of a possibly accepted PLUCK.
            if self._target(row) is not None:
                del self.station.streams[row["stream"]].ring[row["candidate_seq"]]
            return f"local_stopped; pluck_outcome_unproved_{type(e).__name__}", None

    def cancel(self, cue_id, now):
        self._observe(now, durable=True)
        row = self._row(cue_id)
        if row["state"] == "pending":
            self._update(cue_id, now, state="cancelled", cancellation="never_submitted")
        elif row["state"] in {"claimed", "accepted", "unknown"} and not row["cancellation"]:
            self._update(cue_id, now, cancellation="requested")  # durable before local hush
            cancellation, hush = self._stop(row, max(now, self.watermark))
            # Unknown acceptance stays unknown even when its local loop is stopped.
            state = "cancelled" if row["state"] == "accepted" else "unknown"
            self._update(cue_id, now, state=state, cancellation=cancellation, hush=hush)
        return self.show(cue_id)

    def tick(self, now, socket_classes, grant_loader):
        """One bounded tick: housekeeping, then at most one new claim per second."""
        forward = self._observe(now)
        with self.db:
            self.db.execute("UPDATE cues SET state='missed', detail='window ended before acceptance', updated_at=? "
                            "WHERE state='pending' AND ends_at<=?", (now, self.watermark + STOP_BEFORE_EXPIRY_MS))
        active = self.db.execute("SELECT * FROM cues WHERE state IN ('accepted','unknown')").fetchall()
        due = self.db.execute("SELECT * FROM cues WHERE state='pending' AND starts_at<=? "
                              "ORDER BY starts_at,id LIMIT 1", (now,)).fetchone()
        grant, grant_error = None, None
        if active or due is not None:
            try:
                grant = self._grant(grant_loader)
            except ValueError as e:
                grant_error = str(e)
        for row in active:
            target = self._target(row)
            if row["state"] == "unknown" and target is None:
                continue
            reason = None
            if not forward:
                reason = "wall clock moved backwards; local cue stopped"
            elif row["cancellation"] == "requested":
                reason = "recovering requested cancellation"
            elif row["ends_at"] <= now + STOP_BEFORE_EXPIRY_MS:
                reason = "cue window ended"
            elif target is None:
                reason = "accepted item left local carousel; not replayed"
            else:
                try:
                    if grant_error:
                        raise ValueError(grant_error)
                    self._authority(row["stream"], row["cls"], 0, socket_classes, grant)
                except ValueError as e:
                    reason = str(e)
            if reason:
                cancellation, hush = self._stop(row, max(now, self.watermark))
                state = ("ended" if reason == "cue window ended" else "interrupted")
                if row["state"] == "unknown":
                    state = "unknown"
                self._update(row["id"], now, state=state, detail=reason, cancellation=cancellation, hush=hush)
        if not forward or due is None or now - self.last_dispatch < MIN_DISPATCH_MS:
            return
        try:
            if grant_error:
                raise ValueError(grant_error)
            # Preserve the admitted full window's TTL contract even after delay.
            self._authority(due["stream"], due["cls"], json.loads(due["request"])[3],
                            socket_classes, grant)
        except ValueError as e:
            self._update(due["id"], now, state="refused", detail=str(e))
            return
        self._observe(now, durable=True)
        candidate = self.station.streams[due["stream"]].head_seq + 1
        with self.db:
            self.db.execute("UPDATE cues SET state='claimed', claimed_epoch=?, candidate_seq=?, updated_at=? WHERE id=?",
                            (self.station.epoch, candidate, now, due["id"]))
            self.db.execute("UPDATE meta SET value=? WHERE key='last_dispatch'", (str(now),))
        self.last_dispatch = now
        try:
            result = self.station.sing(now, due["stream"], text=due["text"], cls=due["cls"],
                                       ttl_s=Decimal(due["ends_at"] - now) / 1000,
                                       loop=due["loop"], scope="lan", state_key=_state_key(due["id"])).to_json()
        except Exception as e:
            # Even ValueError could come from a changed adapter after acceptance.
            # Conservatively retain unknown and never automatically sing again.
            self._update(due["id"], now, state="unknown", detail=f"sing outcome unknown ({type(e).__name__}); not retried")
            row = self._row(due["id"])
            cancellation, hush = self._stop(row, now)
            self._update(due["id"], now, cancellation=cancellation, hush=hush)
            return
        self._update(due["id"], now, state="accepted", result=json.dumps(result),
                     detail="accepted by local carousel; network send and receipt not proved")

    def dispatch(self, req, now, socket_classes, grant_loader):
        op = req.get("op")
        fields = {"cue_add": {"op", "id", "stream", "text", "loop", "in", "for", "not_after"},
                  "cue_list": {"op", "limit", "after"}, "cue_show": {"op", "id"}, "cue_cancel": {"op", "id"},
                  "cue_capabilities": {"op"}}
        if op in fields and set(req) - fields[op]:
            raise ValueError("unsupported cue request field; cues only support original text and bounded LAN ambient/chatter")
        if op == "cue_add":
            return {"ok": True, "cue": self.add(req, now, socket_classes, grant_loader)}
        if op == "cue_show":
            return {"ok": True, "cue": self.show(req.get("id"))}
        if op == "cue_list":
            return {"ok": True, **self.listing(req.get("limit", MAX_LIST), req.get("after", ""))}
        if op == "cue_cancel":
            return {"ok": True, "cue": self.cancel(req.get("id"), now)}
        if op == "cue_capabilities":
            return {"ok": True, "capabilities": {"schema": "canticle-cue-control/1", "absolute_not_after": True,
                                                   "timestamp_unit": "unix_ms", "max_not_after": MAX_NOT_AFTER_MS}}
        return {"ok": False, "error": "unknown cue operation"}
