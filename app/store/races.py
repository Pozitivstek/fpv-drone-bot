"""Заезды и рекорды трасс (с записью траектории для «призрака»)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from aiosqlite import Connection, Row

from app import clock
from app.db import insert, one, rows


@dataclass(frozen=True)
class Race:
    id: int
    user_id: int
    track_id: str
    training: bool
    fee: int
    build_id: int | None
    build_name: str
    cls: str
    flight: dict
    parts: dict[str, int]
    status: str
    started_at: str


@dataclass(frozen=True)
class Record:
    user_id: int
    track_id: str
    time_ms: int
    cls: str
    build_name: str
    updated_at: str
    name: str = ""


def _race(row: Row) -> Race:
    return Race(id=row["id"], user_id=row["user_id"], track_id=row["track_id"], training=bool(row["training"]),
                fee=row["fee"], build_id=row["build_id"], build_name=row["build_name"], cls=row["cls"],
                flight=json.loads(row["flight"]), parts=json.loads(row["parts"]), status=row["status"],
                started_at=row["started_at"])


async def create(conn: Connection, user_id: int, track_id: str, training: bool, fee: int, build_id: int,
                 build_name: str, cls: str, flight: dict, parts: dict[str, int]) -> int:
    await conn.execute("UPDATE races SET status = 'abandoned' WHERE user_id = ? AND status = 'started'", (user_id,))
    return await insert(conn, "INSERT INTO races (user_id, track_id, training, fee, build_id, build_name, cls, flight,"
                              " parts, started_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (user_id, track_id, int(training), fee, build_id, build_name, cls, json.dumps(flight),
                         json.dumps(parts), clock.iso()))


async def get(conn: Connection, user_id: int, race_id: int) -> Race | None:
    row = await one(conn, "SELECT * FROM races WHERE id = ? AND user_id = ?", (race_id, user_id))
    return _race(row) if row else None


async def finish(conn: Connection, race_id: int, status: str, time_ms: int | None = None, gates: int = 0,
                 crashes: int = 0, medal: str = "", coins: int = 0, xp: int = 0) -> None:
    await conn.execute("UPDATE races SET status = ?, finished_at = ?, time_ms = ?, gates = ?, crashes = ?, medal = ?,"
                       " coins = ?, xp = ? WHERE id = ?",
                       (status, clock.iso(), time_ms, gates, crashes, medal, coins, xp, race_id))


async def record(conn: Connection, user_id: int, track_id: str) -> Record | None:
    row = await one(conn, "SELECT user_id, track_id, time_ms, cls, build_name, updated_at FROM records"
                          " WHERE user_id = ? AND track_id = ?", (user_id, track_id))
    return Record(**dict(row)) if row else None


async def save_record(conn: Connection, user_id: int, track_id: str, time_ms: int, cls: str, build_name: str,
                      path: list) -> None:
    await conn.execute("INSERT INTO records (user_id, track_id, time_ms, cls, build_name, path, updated_at)"
                       " VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(user_id, track_id) DO UPDATE SET"
                       " time_ms = excluded.time_ms, cls = excluded.cls, build_name = excluded.build_name,"
                       " path = excluded.path, updated_at = excluded.updated_at",
                       (user_id, track_id, time_ms, cls, build_name, json.dumps(path), clock.iso()))


async def leaderboard(conn: Connection, track_id: str, limit: int = 20) -> list[Record]:
    result = await rows(conn, "SELECT r.user_id, r.track_id, r.time_ms, r.cls, r.build_name, r.updated_at,"
                              " COALESCE(NULLIF(u.first_name, ''), u.username) AS name FROM records r"
                              " JOIN users u ON u.id = r.user_id WHERE r.track_id = ? AND u.banned = 0"
                              " ORDER BY r.time_ms, r.updated_at LIMIT ?", (track_id, limit))
    return [Record(**dict(row)) for row in result]


async def place(conn: Connection, track_id: str, time_ms: int) -> int:
    row = await one(conn, "SELECT COUNT(*) AS n FROM records r JOIN users u ON u.id = r.user_id"
                          " WHERE r.track_id = ? AND r.time_ms < ? AND u.banned = 0", (track_id, time_ms))
    return int(row["n"]) + 1 if row else 1


async def ghost(conn: Connection, track_id: str, user_id: int | None = None) -> dict | None:
    """Траектория лучшего заезда трассы (или игрока)."""
    where, params = ("r.track_id = ? AND r.user_id = ?", (track_id, user_id)) if user_id \
        else ("r.track_id = ? AND u.banned = 0", (track_id,))
    row = await one(conn, f"SELECT r.time_ms, r.path, COALESCE(NULLIF(u.first_name, ''), u.username) AS name"
                          f" FROM records r JOIN users u ON u.id = r.user_id WHERE {where}"
                          f" ORDER BY r.time_ms LIMIT 1", params)
    if not row:
        return None
    return {"name": row["name"], "time_ms": row["time_ms"], "path": json.loads(row["path"])}


async def user_records(conn: Connection, user_id: int) -> dict[str, int]:
    result = await rows(conn, "SELECT track_id, time_ms FROM records WHERE user_id = ?", (user_id,))
    return {row["track_id"]: row["time_ms"] for row in result}


async def count_since(conn: Connection, since_iso: str) -> int:
    row = await one(conn, "SELECT COUNT(*) AS n FROM races WHERE started_at >= ? AND status = 'finished'",
                    (since_iso,))
    return int(row["n"]) if row else 0


async def count_rewarded_since(conn: Connection, user_id: int, since_iso: str) -> int:
    """Платные (не тренировочные) заезды игрока, уже получившие награду."""
    row = await one(conn, "SELECT COUNT(*) AS n FROM races WHERE user_id = ? AND training = 0"
                          " AND status IN ('finished', 'dnf') AND started_at >= ?", (user_id, since_iso))
    return int(row["n"]) if row else 0
