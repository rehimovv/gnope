"""SQLite persistence for users, translation sessions and processed updates.

Every request may run in a fresh process, so all conversation state lives
here rather than in memory.
"""

from __future__ import annotations

import json
import sqlite3
import time
import zlib
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      INTEGER PRIMARY KEY,
    ui_lang      TEXT,
    name         TEXT NOT NULL DEFAULT '',
    email        TEXT NOT NULL DEFAULT '',
    last_lang    TEXT NOT NULL DEFAULT '',
    state        TEXT NOT NULL DEFAULT '',
    state_data   TEXT NOT NULL DEFAULT '{}',
    upload_day   TEXT NOT NULL DEFAULT '',
    upload_count INTEGER NOT NULL DEFAULT 0,
    updated_at   INTEGER NOT NULL DEFAULT 0,
    hide_reserve_note INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
    user_id         INTEGER PRIMARY KEY,
    file_name       TEXT NOT NULL,
    out_name        TEXT NOT NULL,
    lang            TEXT NOT NULL,
    mode            TEXT NOT NULL DEFAULT '',
    queue           TEXT NOT NULL DEFAULT '[]',
    position        INTEGER NOT NULL DEFAULT 0,
    plural_form     INTEGER NOT NULL DEFAULT 0,
    plural_draft    TEXT NOT NULL DEFAULT '[]',
    card_message_id INTEGER NOT NULL DEFAULT 0,
    changed         INTEGER NOT NULL DEFAULT 0,
    updated_at      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS processed_updates (
    update_id INTEGER PRIMARY KEY,
    at        INTEGER NOT NULL
);
"""


@dataclass(frozen=True)
class User:
    user_id: int
    ui_lang: Optional[str] = None
    name: str = ""
    email: str = ""
    last_lang: str = ""
    state: str = ""
    state_data: Dict[str, Any] = field(default_factory=dict)
    upload_day: str = ""
    upload_count: int = 0
    hide_reserve_note: bool = False

    @property
    def has_profile(self) -> bool:
        return bool(self.name and self.email)


@dataclass(frozen=True)
class Session:
    user_id: int
    file_name: str
    out_name: str
    lang: str
    mode: str = ""
    queue: Tuple[int, ...] = ()
    position: int = 0
    plural_form: int = 0
    plural_draft: Tuple[str, ...] = ()
    card_message_id: int = 0
    changed: bool = False
    updated_at: int = 0

    @property
    def current(self) -> Optional[int]:
        return self.queue[self.position] if 0 <= self.position < len(self.queue) else None

    @property
    def token(self) -> str:
        """Short id of the open file, put in destructive buttons to reject stale taps."""
        return format(zlib.crc32(self.file_name.encode("utf-8")) & 0xFFFFFF, "x")


class Store:
    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.executescript(_SCHEMA)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            if "hide_reserve_note" not in columns:  # databases created before this column existed
                conn.execute("ALTER TABLE users ADD COLUMN hide_reserve_note INTEGER NOT NULL DEFAULT 0")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def _write(self, sql: str, params: Tuple[Any, ...]) -> int:
        with closing(self._connect()) as conn, conn:
            return conn.execute(sql, params).rowcount

    def _read(self, sql: str, params: Tuple[Any, ...]) -> List[sqlite3.Row]:
        with closing(self._connect()) as conn:
            return conn.execute(sql, params).fetchall()

    # -- users -------------------------------------------------------------

    def get_user(self, user_id: int) -> User:
        rows = self._read("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not rows:
            return User(user_id=user_id)
        row = rows[0]
        return User(
            user_id=row["user_id"],
            ui_lang=row["ui_lang"],
            name=row["name"],
            email=row["email"],
            last_lang=row["last_lang"],
            state=row["state"],
            state_data=json.loads(row["state_data"] or "{}"),
            upload_day=row["upload_day"],
            upload_count=row["upload_count"],
            hide_reserve_note=bool(row["hide_reserve_note"]),
        )

    def save_user(self, user: User) -> User:
        self._write(
            # Full-row replace: works on the old SQLite versions shipped by some hosts.
            """INSERT OR REPLACE INTO users (user_id, ui_lang, name, email, last_lang, state, state_data,
                                  upload_day, upload_count, updated_at, hide_reserve_note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user.user_id, user.ui_lang, user.name, user.email, user.last_lang, user.state,
                json.dumps(user.state_data), user.upload_day, user.upload_count, int(time.time()),
                int(user.hide_reserve_note),
            ),
        )
        return user

    # -- sessions ----------------------------------------------------------

    def get_session(self, user_id: int) -> Optional[Session]:
        rows = self._read("SELECT * FROM sessions WHERE user_id = ?", (user_id,))
        if not rows:
            return None
        row = rows[0]
        return Session(
            user_id=row["user_id"],
            file_name=row["file_name"],
            out_name=row["out_name"],
            lang=row["lang"],
            mode=row["mode"],
            queue=tuple(json.loads(row["queue"])),
            position=row["position"],
            plural_form=row["plural_form"],
            plural_draft=tuple(json.loads(row["plural_draft"])),
            card_message_id=row["card_message_id"],
            changed=bool(row["changed"]),
            updated_at=row["updated_at"],
        )

    def save_session(self, s: Session) -> Session:
        self._write(
            """INSERT OR REPLACE INTO sessions (user_id, file_name, out_name, lang, mode, queue, position,
                   plural_form, plural_draft, card_message_id, changed, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                s.user_id, s.file_name, s.out_name, s.lang, s.mode, json.dumps(list(s.queue)), s.position,
                s.plural_form, json.dumps(list(s.plural_draft)), s.card_message_id, int(s.changed),
                int(time.time()),
            ),
        )
        return s

    def delete_session(self, user_id: int) -> None:
        self._write("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def expired_sessions(self, older_than: int) -> List[int]:
        return [r["user_id"] for r in self._read("SELECT user_id FROM sessions WHERE updated_at < ?", (older_than,))]

    # -- updates -----------------------------------------------------------

    def claim_update(self, update_id: int) -> bool:
        """Record an update id; False when it was already processed."""
        return self._write(
            "INSERT OR IGNORE INTO processed_updates (update_id, at) VALUES (?, ?)", (update_id, int(time.time()))
        ) == 1

    def purge_updates(self, older_than: int) -> None:
        self._write("DELETE FROM processed_updates WHERE at < ?", (older_than,))
