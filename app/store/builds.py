"""Сборки дронов в ангаре: в каждом слоте — id экземпляра детали из инвентаря."""

from __future__ import annotations

from dataclasses import dataclass

from aiosqlite import Connection, Row

from app import clock
from app.db import changed, insert, one, rows
from app.game.defs import SLOTS


@dataclass(frozen=True)
class Build:
    id: int
    name: str
    slots: dict[str, int | None]


def _build(row: Row) -> Build:
    return Build(id=row["id"], name=row["name"], slots={slot: row[slot] for slot in SLOTS})


async def list_for(conn: Connection, user_id: int) -> list[Build]:
    return [_build(row) for row in await rows(conn, "SELECT * FROM builds WHERE user_id = ? ORDER BY id", (user_id,))]


async def get(conn: Connection, user_id: int, build_id: int) -> Build | None:
    row = await one(conn, "SELECT * FROM builds WHERE id = ? AND user_id = ?", (build_id, user_id))
    return _build(row) if row else None


async def create(conn: Connection, user_id: int, name: str, slots: dict[str, int] | None = None) -> int:
    filled = {slot: (slots or {}).get(slot) for slot in SLOTS}
    return await insert(conn, f"INSERT INTO builds (user_id, name, {', '.join(SLOTS)}, created_at)"
                              f" VALUES (?, ?, {', '.join('?' for _ in SLOTS)}, ?)",
                        (user_id, name[:40], *filled.values(), clock.iso()))


async def rename(conn: Connection, user_id: int, build_id: int, name: str) -> bool:
    return await changed(conn, "UPDATE builds SET name = ? WHERE id = ? AND user_id = ?",
                         (name[:40], build_id, user_id)) == 1


async def delete(conn: Connection, user_id: int, build_id: int) -> bool:
    return await changed(conn, "DELETE FROM builds WHERE id = ? AND user_id = ?", (build_id, user_id)) == 1


async def set_slot(conn: Connection, user_id: int, build_id: int, slot: str, uid: int | None) -> None:
    if slot not in SLOTS:
        raise ValueError(f"неизвестный слот {slot}")
    await conn.execute(f"UPDATE builds SET {slot} = ? WHERE id = ? AND user_id = ?", (uid, build_id, user_id))


async def free_uid(conn: Connection, user_id: int, uid: int) -> None:
    """Убирает деталь из всех сборок игрока (деталь может стоять только в одной)."""
    for slot in SLOTS:
        await conn.execute(f"UPDATE builds SET {slot} = NULL WHERE user_id = ? AND {slot} = ?", (user_id, uid))
