"""Промокоды, прогресс заданий, глобальные настройки (kv), лента дропов и журнал админа."""

from __future__ import annotations

import json
from dataclasses import dataclass

from aiosqlite import Connection, Row

from app import clock
from app.db import changed, insert, one, rows


@dataclass(frozen=True)
class Promo:
    code: str
    reward: dict
    max_uses: int
    uses: int
    expires_at: str | None
    active: bool
    note: str
    created_at: str


def _promo(row: Row) -> Promo:
    return Promo(code=row["code"], reward=json.loads(row["reward"]), max_uses=row["max_uses"], uses=row["uses"],
                 expires_at=row["expires_at"], active=bool(row["active"]), note=row["note"],
                 created_at=row["created_at"])


async def promo(conn: Connection, code: str) -> Promo | None:
    row = await one(conn, "SELECT * FROM promos WHERE code = ?", (code,))
    return _promo(row) if row else None


async def create_promo(conn: Connection, code: str, reward: dict, max_uses: int, expires_at: str | None,
                       note: str, created_by: int) -> None:
    await conn.execute("INSERT INTO promos (code, reward, max_uses, expires_at, note, created_by, created_at)"
                       " VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (code, json.dumps(reward, ensure_ascii=False), max_uses, expires_at, note[:120], created_by,
                        clock.iso()))


async def promos(conn: Connection) -> list[Promo]:
    return [_promo(row) for row in await rows(conn, "SELECT * FROM promos ORDER BY created_at DESC")]


async def set_promo_active(conn: Connection, code: str, active: bool) -> bool:
    return await changed(conn, "UPDATE promos SET active = ? WHERE code = ?", (int(active), code)) == 1


async def delete_promo(conn: Connection, code: str) -> bool:
    return await changed(conn, "DELETE FROM promos WHERE code = ?", (code,)) == 1


async def use_promo(conn: Connection, code: str, user_id: int) -> bool:
    """Отмечает использование: False, если игрок уже вводил код или лимит исчерпан."""
    used = await one(conn, "SELECT 1 FROM promo_uses WHERE code = ? AND user_id = ?", (code, user_id))
    if used:
        return False
    if await changed(conn, "UPDATE promos SET uses = uses + 1 WHERE code = ? AND (max_uses = 0 OR uses < max_uses)",
                     (code,)) != 1:
        return False
    await conn.execute("INSERT INTO promo_uses (code, user_id, used_at) VALUES (?, ?, ?)", (code, user_id, clock.iso()))
    return True


async def task_progress(conn: Connection, user_id: int, periods: list[str]) -> dict[tuple[str, str], tuple[int, bool]]:
    marks = ",".join("?" for _ in periods)
    result = await rows(conn, f"SELECT period, task_id, progress, claimed FROM tasks WHERE user_id = ?"
                              f" AND period IN ({marks})", (user_id, *periods))
    return {(row["period"], row["task_id"]): (row["progress"], bool(row["claimed"])) for row in result}


async def add_task_progress(conn: Connection, user_id: int, period: str, task_id: str, amount: int, goal: int) -> None:
    await conn.execute("INSERT INTO tasks (user_id, period, task_id, progress) VALUES (?, ?, ?, MIN(?, ?))"
                       " ON CONFLICT(user_id, period, task_id) DO UPDATE SET progress = MIN(?, progress + ?)"
                       " WHERE claimed = 0", (user_id, period, task_id, amount, goal, goal, amount))


async def claim_task(conn: Connection, user_id: int, period: str, task_id: str, goal: int) -> bool:
    return await changed(conn, "UPDATE tasks SET claimed = 1 WHERE user_id = ? AND period = ? AND task_id = ?"
                               " AND claimed = 0 AND progress >= ?", (user_id, period, task_id, goal)) == 1


async def get_kv(conn: Connection, key: str, default: str = "") -> str:
    row = await one(conn, "SELECT value FROM kv WHERE key = ?", (key,))
    return row["value"] if row else default


async def set_kv(conn: Connection, key: str, value: str) -> None:
    await conn.execute("INSERT INTO kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                       (key, value))


async def add_drop(conn: Connection, user_id: int, user_name: str, item_id: str, rarity: str, source: str) -> None:
    await conn.execute("INSERT INTO drops (user_id, user_name, item_id, rarity, source, created_at)"
                       " VALUES (?, ?, ?, ?, ?, ?)", (user_id, user_name[:40], item_id, rarity, source, clock.iso()))


async def recent_drops(conn: Connection, limit: int = 20) -> list[dict]:
    result = await rows(conn, "SELECT user_name, item_id, rarity, source, created_at FROM drops"
                              " ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(row) for row in result]


async def count_drops_since(conn: Connection, since_iso: str) -> int:
    row = await one(conn, "SELECT COUNT(*) AS n FROM drops WHERE created_at >= ?", (since_iso,))
    return int(row["n"]) if row else 0


async def log_admin(conn: Connection, admin_id: int, action: str, target_id: int | None, details: dict) -> int:
    return await insert(conn, "INSERT INTO admin_log (admin_id, action, target_id, details, created_at)"
                              " VALUES (?, ?, ?, ?, ?)",
                        (admin_id, action, target_id, json.dumps(details, ensure_ascii=False), clock.iso()))


async def admin_log(conn: Connection, limit: int = 50) -> list[dict]:
    result = await rows(conn, "SELECT id, admin_id, action, target_id, details, created_at FROM admin_log"
                              " ORDER BY id DESC LIMIT ?", (limit,))
    return [{**dict(row), "details": json.loads(row["details"])} for row in result]
