"""Инвентарь (экземпляры деталей с износом) и ключи от кейсов."""

from __future__ import annotations

from dataclasses import dataclass

from aiosqlite import Connection

from app import clock
from app.db import changed, insert, one, rows
from app.game.defs import SLOTS


@dataclass(frozen=True)
class Owned:
    uid: int
    item_id: str
    wear: int
    created_at: str = ""


def _placeholders(values: list) -> str:
    return ",".join("?" for _ in values)


async def add(conn: Connection, user_id: int, item_id: str, source: str) -> int:
    return await insert(conn, "INSERT INTO items (user_id, item_id, source, created_at) VALUES (?, ?, ?, ?)",
                        (user_id, item_id, source[:40], clock.iso()))


async def owned(conn: Connection, user_id: int) -> list[Owned]:
    result = await rows(conn, "SELECT id, item_id, wear, created_at FROM items WHERE user_id = ? ORDER BY id DESC",
                        (user_id,))
    return [Owned(row["id"], row["item_id"], row["wear"], row["created_at"]) for row in result]


async def get_many(conn: Connection, user_id: int, uids: list[int]) -> list[Owned]:
    if not uids:
        return []
    result = await rows(conn, f"SELECT id, item_id, wear, created_at FROM items WHERE user_id = ?"
                              f" AND id IN ({_placeholders(uids)})", (user_id, *uids))
    return [Owned(row["id"], row["item_id"], row["wear"], row["created_at"]) for row in result]


async def remove(conn: Connection, user_id: int, uids: list[int]) -> int:
    if not uids:
        return 0
    return await changed(conn, f"DELETE FROM items WHERE user_id = ? AND id IN ({_placeholders(uids)})",
                         (user_id, *uids))


async def add_wear(conn: Connection, uid: int, amount: int) -> None:
    await conn.execute("UPDATE items SET wear = MIN(100, wear + ?) WHERE id = ?", (amount, uid))


async def set_wear(conn: Connection, user_id: int, uids: list[int], wear: int) -> None:
    if uids:
        await conn.execute(f"UPDATE items SET wear = ? WHERE user_id = ? AND id IN ({_placeholders(uids)})",
                           (wear, user_id, *uids))


async def locked(conn: Connection, user_id: int) -> set[int]:
    """Детали, стоящие в сборках или надетые (очки, пульт) — их нельзя продать или сжечь."""
    result: set[int] = set()
    for row in await rows(conn, f"SELECT {', '.join(SLOTS)} FROM builds WHERE user_id = ?", (user_id,)):
        result.update(value for value in row if value)
    gear = await one(conn, "SELECT goggles_uid, radio_uid FROM users WHERE id = ?", (user_id,))
    if gear:
        result.update(value for value in gear if value)
    return result


async def unequip(conn: Connection, user_id: int, uids: list[int]) -> None:
    """Снимает детали отовсюду (перед удалением)."""
    if not uids:
        return
    marks = _placeholders(uids)
    for slot in SLOTS:
        await conn.execute(f"UPDATE builds SET {slot} = NULL WHERE user_id = ? AND {slot} IN ({marks})",
                           (user_id, *uids))
    for column in ("goggles_uid", "radio_uid"):
        await conn.execute(f"UPDATE users SET {column} = NULL WHERE id = ? AND {column} IN ({marks})",
                           (user_id, *uids))


async def keys(conn: Connection, user_id: int) -> dict[str, int]:
    result = await rows(conn, "SELECT case_id, qty FROM case_keys WHERE user_id = ? AND qty > 0", (user_id,))
    return {row["case_id"]: row["qty"] for row in result}


async def add_keys(conn: Connection, user_id: int, case_id: str, qty: int) -> None:
    if qty > 0:
        await conn.execute("INSERT INTO case_keys (user_id, case_id, qty) VALUES (?, ?, ?)"
                           " ON CONFLICT(user_id, case_id) DO UPDATE SET qty = qty + excluded.qty",
                           (user_id, case_id, qty))


async def use_keys(conn: Connection, user_id: int, case_id: str, qty: int) -> bool:
    return await changed(conn, "UPDATE case_keys SET qty = qty - ? WHERE user_id = ? AND case_id = ? AND qty >= ?",
                         (qty, user_id, case_id, qty)) == 1


async def item_counts(conn: Connection) -> list[tuple[int, str, int]]:
    """(игрок, деталь, количество) — для рейтинга коллекций."""
    result = await rows(conn, "SELECT i.user_id, i.item_id, COUNT(*) AS n FROM items i"
                              " JOIN users u ON u.id = i.user_id WHERE u.banned = 0 GROUP BY i.user_id, i.item_id")
    return [(row["user_id"], row["item_id"], row["n"]) for row in result]


async def count_all(conn: Connection) -> int:
    row = await one(conn, "SELECT COUNT(*) AS n FROM items")
    return int(row["n"]) if row else 0
