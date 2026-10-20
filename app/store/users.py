"""Игроки: баланс, опыт, удача, бан, экипировка и счётчики."""

from __future__ import annotations

from dataclasses import dataclass

from aiosqlite import Connection, Row

from app import clock
from app.db import changed, one, rows

STARTING_COINS = 500
EDITABLE = frozenset({
    "xp", "level", "luck", "banned", "referrer_id", "ref_bonus_paid", "active_build_id",
    "goggles_uid", "radio_uid", "streak", "daily_last",
})
COUNTERS = frozenset({"cases_opened", "races", "golds"})


@dataclass(frozen=True)
class User:
    id: int
    first_name: str
    username: str
    coins: int
    xp: int
    level: int
    luck: float
    banned: bool
    referrer_id: int | None
    ref_bonus_paid: bool
    active_build_id: int | None
    goggles_uid: int | None
    radio_uid: int | None
    streak: int
    daily_last: str | None
    cases_opened: int
    races: int
    golds: int
    created_at: str
    last_seen: str

    @property
    def display_name(self) -> str:
        return self.first_name or (f"@{self.username}" if self.username else f"Пилот {self.id}")


def _user(row: Row | None) -> User | None:
    if row is None:
        return None
    data = dict(row)
    data["banned"] = bool(data["banned"])
    data["ref_bonus_paid"] = bool(data["ref_bonus_paid"])
    return User(**data)


async def get(conn: Connection, user_id: int) -> User | None:
    return _user(await one(conn, "SELECT * FROM users WHERE id = ?", (user_id,)))


async def create(conn: Connection, user_id: int, first_name: str, username: str,
                 referrer_id: int | None = None) -> User:
    moment = clock.iso()
    await conn.execute(
        "INSERT INTO users (id, first_name, username, coins, referrer_id, created_at, last_seen)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, first_name[:64], username[:64], STARTING_COINS, referrer_id, moment, moment),
    )
    created = await get(conn, user_id)
    assert created is not None
    return created


async def touch(conn: Connection, user_id: int, first_name: str, username: str) -> None:
    await conn.execute("UPDATE users SET first_name = ?, username = ?, last_seen = ? WHERE id = ?",
                       (first_name[:64], username[:64], clock.iso(), user_id))


async def add_coins(conn: Connection, user_id: int, amount: int) -> None:
    if amount:
        await conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (amount, user_id))


async def spend(conn: Connection, user_id: int, amount: int) -> bool:
    """Списывает монеты, только если их хватает. Возвращает False при нехватке."""
    if amount <= 0:
        return True
    return await changed(conn, "UPDATE users SET coins = coins - ? WHERE id = ? AND coins >= ?",
                         (amount, user_id, amount)) == 1


async def update(conn: Connection, user_id: int, **fields) -> None:
    unknown = set(fields) - EDITABLE
    if unknown:
        raise ValueError(f"нельзя менять поля {sorted(unknown)}")
    if fields:
        assignments = ", ".join(f"{name} = ?" for name in fields)
        await conn.execute(f"UPDATE users SET {assignments} WHERE id = ?", (*fields.values(), user_id))


async def bump(conn: Connection, user_id: int, counter: str, amount: int = 1) -> None:
    if counter not in COUNTERS:
        raise ValueError(f"неизвестный счётчик {counter}")
    await conn.execute(f"UPDATE users SET {counter} = {counter} + ? WHERE id = ?", (amount, user_id))


async def search(conn: Connection, query: str, limit: int = 20) -> list[User]:
    text = query.strip().lstrip("@")
    if text.isdigit():
        found = await get(conn, int(text))
        return [found] if found else []
    pattern = f"%{text}%"
    result = await rows(conn, "SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ?"
                              " ORDER BY last_seen DESC LIMIT ?", (pattern, pattern, limit))
    return [user for user in map(_user, result) if user]


async def recent(conn: Connection, limit: int = 20) -> list[User]:
    result = await rows(conn, "SELECT * FROM users ORDER BY last_seen DESC LIMIT ?", (limit,))
    return [user for user in map(_user, result) if user]


async def top(conn: Connection, order: str, limit: int = 50) -> list[User]:
    columns = {"xp": "xp DESC, id", "golds": "golds DESC, xp DESC", "coins": "coins DESC, id"}
    result = await rows(conn, f"SELECT * FROM users WHERE banned = 0 ORDER BY {columns[order]} LIMIT ?", (limit,))
    return [user for user in map(_user, result) if user]


async def count_referrals(conn: Connection, user_id: int) -> int:
    row = await one(conn, "SELECT COUNT(*) AS n FROM users WHERE referrer_id = ?", (user_id,))
    return int(row["n"]) if row else 0


async def all_ids(conn: Connection) -> list[int]:
    return [int(row["id"]) for row in await rows(conn, "SELECT id FROM users WHERE banned = 0 ORDER BY id")]
