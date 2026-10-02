from __future__ import annotations

import sqlite3
from enum import StrEnum
from pathlib import Path

from .model import Notice, NoticeKind


class ClaimOutcome(StrEnum):
    CLAIMED = "claimed"
    REPLAY = "replay"
    SUBJECT_TOMBSTONED = "subject_tombstoned"
    REPLAY_CACHE_FULL = "replay_cache_full"
    TOMBSTONE_CACHE_FULL = "tombstone_cache_full"


class ReceptorState:
    def __init__(
        self,
        path: str | Path,
        *,
        max_replay_entries: int = 10_000,
        max_tombstones: int = 10_000,
        replay_retention_seconds: int = 86_400,
    ):
        if max_replay_entries < 1 or max_tombstones < 1 or replay_retention_seconds < 0:
            raise ValueError("invalid_state_bounds")
        self._max_replay_entries = max_replay_entries
        self._max_tombstones = max_tombstones
        self._replay_retention_seconds = replay_retention_seconds
        self._connection = sqlite3.connect(path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_notices (
                notice_id TEXT PRIMARY KEY,
                retain_until INTEGER NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS subject_tombstones (
                subject TEXT PRIMARY KEY,
                notice_id TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def claim(self, notice: Notice, now: int) -> ClaimOutcome:
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                "DELETE FROM seen_notices WHERE retain_until <= ?",
                (now,),
            )
            if self._connection.execute(
                "SELECT 1 FROM seen_notices WHERE notice_id = ?",
                (notice.notice_id,),
            ).fetchone():
                self._connection.rollback()
                return ClaimOutcome.REPLAY
            if self._connection.execute(
                "SELECT 1 FROM subject_tombstones WHERE subject = ?",
                (notice.subject,),
            ).fetchone():
                self._connection.rollback()
                return ClaimOutcome.SUBJECT_TOMBSTONED

            seen_count = self._connection.execute(
                "SELECT COUNT(*) FROM seen_notices"
            ).fetchone()[0]
            if seen_count >= self._max_replay_entries:
                self._connection.rollback()
                return ClaimOutcome.REPLAY_CACHE_FULL

            if notice.kind is NoticeKind.TOMBSTONE:
                tombstone_count = self._connection.execute(
                    "SELECT COUNT(*) FROM subject_tombstones"
                ).fetchone()[0]
                if tombstone_count >= self._max_tombstones:
                    self._connection.rollback()
                    return ClaimOutcome.TOMBSTONE_CACHE_FULL
                self._connection.execute(
                    """
                    INSERT INTO subject_tombstones (subject, notice_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (notice.subject, notice.notice_id, now),
                )

            self._connection.execute(
                "INSERT INTO seen_notices (notice_id, retain_until) VALUES (?, ?)",
                (
                    notice.notice_id,
                    notice.expires_at + self._replay_retention_seconds,
                ),
            )
            self._connection.commit()
            return ClaimOutcome.CLAIMED
        except sqlite3.Error:
            self._connection.rollback()
            raise
