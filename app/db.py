"""SQLite: схема и обёртка с транзакциями.

Соединение одно на процесс; все записи идут через `Database.tx()`, который держит asyncio-замок,
поэтому списание монет и выдача предметов не перемешиваются между параллельными запросами.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable, Iterable

import aiosqlite

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT '',
    coins INTEGER NOT NULL DEFAULT 0 CHECK (coins >= 0),
    xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1,
    luck REAL NOT NULL DEFAULT 1.0,
    banned INTEGER NOT NULL DEFAULT 0,
    referrer_id INTEGER,
    ref_bonus_paid INTEGER NOT NULL DEFAULT 0,
    active_build_id INTEGER,
    goggles_uid INTEGER,
    radio_uid INTEGER,
    streak INTEGER NOT NULL DEFAULT 0,
    daily_last TEXT,
    cases_opened INTEGER NOT NULL DEFAULT 0,
    races INTEGER NOT NULL DEFAULT 0,
    golds INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_seen TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    wear INTEGER NOT NULL DEFAULT 0 CHECK (wear BETWEEN 0 AND 100),
    source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_user ON items(user_id);
CREATE TABLE IF NOT EXISTS case_keys (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 0 CHECK (qty >= 0),
    PRIMARY KEY (user_id, case_id)
);
CREATE TABLE IF NOT EXISTS builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    frame INTEGER, motors INTEGER, stack INTEGER, video INTEGER, props INTEGER, battery INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_builds_user ON builds(user_id);
CREATE TABLE IF NOT EXISTS races (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_id TEXT NOT NULL,
    training INTEGER NOT NULL DEFAULT 0,
    fee INTEGER NOT NULL DEFAULT 0,
    build_id INTEGER,
    build_name TEXT NOT NULL DEFAULT '',
    cls TEXT NOT NULL DEFAULT '',
    flight TEXT NOT NULL DEFAULT '{}',
    parts TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'started',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    time_ms INTEGER,
    gates INTEGER NOT NULL DEFAULT 0,
    crashes INTEGER NOT NULL DEFAULT 0,
    medal TEXT NOT NULL DEFAULT '',
    coins INTEGER NOT NULL DEFAULT 0,
    xp INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_races_user ON races(user_id, started_at);
CREATE TABLE IF NOT EXISTS records (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    track_id TEXT NOT NULL,
    time_ms INTEGER NOT NULL,
    cls TEXT NOT NULL DEFAULT '',
    build_name TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, track_id)
);
CREATE INDEX IF NOT EXISTS idx_records_track ON records(track_id, time_ms);
CREATE TABLE IF NOT EXISTS promos (
    code TEXT PRIMARY KEY,
    reward TEXT NOT NULL,
    max_uses INTEGER NOT NULL DEFAULT 0,
    uses INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    note TEXT NOT NULL DEFAULT '',
    created_by INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS promo_uses (
    code TEXT NOT NULL REFERENCES promos(code) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    used_at TEXT NOT NULL,
    PRIMARY KEY (code, user_id)
);
CREATE TABLE IF NOT EXISTS tasks (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    period TEXT NOT NULL,
    task_id TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    claimed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, period, task_id)
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_name TEXT NOT NULL DEFAULT '',
    item_id TEXT NOT NULL,
    rarity TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_id INTEGER,
    details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
"""

Params = Iterable | dict


async def one(conn: aiosqlite.Connection, sql: str, params: Params = ()) -> aiosqlite.Row | None:
    async with conn.execute(sql, params) as cursor:
        return await cursor.fetchone()


async def rows(conn: aiosqlite.Connection, sql: str, params: Params = ()) -> list[aiosqlite.Row]:
    async with conn.execute(sql, params) as cursor:
        return list(await cursor.fetchall())


async def insert(conn: aiosqlite.Connection, sql: str, params: Params = ()) -> int:
    async with conn.execute(sql, params) as cursor:
        return int(cursor.lastrowid or 0)


async def changed(conn: aiosqlite.Connection, sql: str, params: Params = ()) -> int:
    """Выполняет UPDATE/DELETE и возвращает число затронутых строк."""
    async with conn.execute(sql, params) as cursor:
        return cursor.rowcount


AfterCommit = Callable[[], Awaitable[None]]


class Database:
    """Одно соединение aiosqlite + замок для транзакций записи.

    `on_commit` откладывает побочные эффекты (сообщения в Telegram) до успешного COMMIT:
    если транзакция откатилась, игрок не получит уведомление о том, чего не было.
    """

    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn
        self._lock = asyncio.Lock()
        self._pending: list[AfterCommit] = []
        self._tasks: set[asyncio.Task] = set()

    @asynccontextmanager
    async def tx(self) -> AsyncIterator[aiosqlite.Connection]:
        async with self._lock:
            self._pending = []
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except BaseException:
                await self.conn.execute("ROLLBACK")
                self._pending = []
                raise
            try:
                await self.conn.execute("COMMIT")
            except BaseException:
                await self.conn.execute("ROLLBACK")
                self._pending = []
                raise
            pending, self._pending = self._pending, []
        for callback in pending:
            task = asyncio.create_task(self._run(callback))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    def on_commit(self, callback: AfterCommit) -> None:
        self._pending.append(callback)

    @staticmethod
    async def _run(callback: AfterCommit) -> None:
        try:
            await callback()
        except Exception:
            log.exception("after-commit callback failed")

    async def close(self) -> None:
        await self.conn.close()


async def connect(path: Path | str) -> Database:
    conn = await aiosqlite.connect(str(path), isolation_level=None)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute("PRAGMA busy_timeout=5000")
    await conn.executescript(SCHEMA)
    return Database(conn)
