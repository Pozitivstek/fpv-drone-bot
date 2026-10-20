"""Таблицы лидеров и лента редких дропов."""

from __future__ import annotations

import time
from collections import defaultdict

from app.context import AppContext
from app.game.progression import rank_for_level
from app.services.errors import GameError
from app.store import items, social, users

TOP_SIZE = 50
KINDS = ("level", "golds", "collection")
CACHE_TTL_S = 60
CACHE: dict[str, tuple[float, list[dict]]] = {}


async def leaderboard(ctx: AppContext, kind: str) -> list[dict]:
    """Рейтинги пересчитываются не чаще раза в минуту: группировка по всем деталям не бесплатна."""
    if kind not in KINDS:
        raise GameError("Неизвестный рейтинг")
    cached = CACHE.get(kind)
    if cached and time.monotonic() - cached[0] < CACHE_TTL_S:
        return cached[1]
    result = await _compute(ctx, kind)
    CACHE[kind] = (time.monotonic(), result)
    return result


async def _compute(ctx: AppContext, kind: str) -> list[dict]:
    conn = ctx.db.conn
    if kind == "collection":
        totals: dict[int, int] = defaultdict(int)
        for user_id, item_id, count in await items.item_counts(conn):
            item = ctx.catalog.items.get(item_id)
            if item:
                totals[user_id] += item.value * count
        leaders = sorted(totals.items(), key=lambda pair: pair[1], reverse=True)[:TOP_SIZE]
        rows = []
        for user_id, value in leaders:
            user = await users.get(conn, user_id)
            if user:
                rows.append((user, value))
    else:
        rows = [(user, user.golds if kind == "golds" else user.xp)
                for user in await users.top(conn, "golds" if kind == "golds" else "xp", TOP_SIZE)]
    return [{"place": index + 1, "user_id": user.id, "name": user.display_name, "level": user.level,
             "rank": rank_for_level(user.level).icon, "value": value} for index, (user, value) in enumerate(rows)]


async def feed(ctx: AppContext, limit: int = 20) -> list[dict]:
    result = []
    for drop in await social.recent_drops(ctx.db.conn, limit):
        if drop["item_id"] in ctx.catalog.items:
            result.append({"name": drop["user_name"], "item": drop["item_id"], "rarity": drop["rarity"],
                           "source": drop["source"], "at": drop["created_at"]})
    return result
