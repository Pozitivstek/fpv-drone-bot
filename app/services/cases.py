"""Кейсы: витрина с честными шансами и открытие (за монеты или ключи)."""

from __future__ import annotations

from app.context import AppContext
from app.game.defs import FEED_MIN_TIER, TIER
from app.game.drops import case_odds, rarity_odds, roll
from app.services import progress
from app.services.errors import GameError, NotFound
from app.services.players import require_active
from app.services.rewards import add_xp
from app.services.views import item_view
from app.store import items, social, users
from app.store.users import User

MAX_OPEN = 5
XP_PRICE_DIVISOR = 40
MIN_CASE_XP = 5
TOP_PREVIEW = 4


def case_xp(price: int) -> int:
    return max(MIN_CASE_XP, price // XP_PRICE_DIVISOR)


async def _luck(ctx: AppContext, user: User) -> float:
    return user.luck * (await progress.events(ctx.db.conn))["luck_event"]


async def list_cases(ctx: AppContext, user: User) -> list[dict]:
    luck = await _luck(ctx, user)
    keys = await items.keys(ctx.db.conn, user.id)
    result = []
    for case in ctx.catalog.cases.values():
        pool = ctx.catalog.pool(case.id)
        everything = [item for group in pool.values() for item in group]
        top = sorted(everything, key=lambda item: (item.tier, item.value), reverse=True)[:TOP_PREVIEW]
        result.append({
            "id": case.id, "name": case.name, "price": case.price, "color": case.color, "tagline": case.tagline,
            "buyable": case.buyable, "min_level": case.min_level, "locked": user.level < case.min_level,
            "keys": keys.get(case.id, 0), "count": len(everything), "top": [item.id for item in top],
            "odds": {rarity: round(chance * 100, 3) for rarity, chance in rarity_odds(case, pool, luck).items()},
        })
    return result


async def case_detail(ctx: AppContext, user: User, case_id: str) -> dict:
    case = ctx.catalog.cases.get(case_id)
    if case is None:
        raise NotFound("Нет такого кейса")
    odds = case_odds(case, ctx.catalog.pool(case_id), await _luck(ctx, user))
    ordered = sorted(odds, key=lambda entry: (-TIER[entry.item.rarity], -entry.item.value))
    keys = await items.keys(ctx.db.conn, user.id)
    return {"id": case.id, "name": case.name, "price": case.price, "color": case.color, "tagline": case.tagline,
            "buyable": case.buyable, "min_level": case.min_level, "locked": user.level < case.min_level,
            "keys": keys.get(case.id, 0),
            "items": [{"id": entry.item.id, "chance": round(entry.chance * 100, 4)} for entry in ordered]}


async def open_case(ctx: AppContext, user_id: int, case_id: str, count: int = 1, use_keys: bool = False) -> dict:
    case = ctx.catalog.cases.get(case_id)
    if case is None:
        raise NotFound("Нет такого кейса")
    if not 1 <= count <= MAX_OPEN:
        raise GameError(f"За раз можно открыть от 1 до {MAX_OPEN} кейсов")
    async with ctx.db.tx() as conn:
        user = await users.get(conn, user_id)
        if user is None:
            raise NotFound("Нет такого игрока")
        require_active(user)
        if not use_keys and user.level < case.min_level:
            raise GameError(f"Кейс откроется на {case.min_level} уровне — или откройте его ключом")
        if use_keys:
            if not await items.use_keys(conn, user_id, case_id, count):
                raise GameError("Не хватает ключей от этого кейса")
        elif not case.buyable:
            raise GameError("Этот кейс не продаётся — его дают за бонусы и задания")
        elif not await users.spend(conn, user_id, case.price * count):
            raise GameError("Не хватает монет")
        luck = user.luck * (await progress.events(conn))["luck_event"]
        odds = case_odds(case, ctx.catalog.pool(case_id), luck)
        dropped = []
        for _ in range(count):
            item = roll(odds, ctx.rng)
            uid = await items.add(conn, user_id, item.id, f"case:{case_id}")
            dropped.append(item_view(item, uid))
            if item.tier >= FEED_MIN_TIER:
                await social.add_drop(conn, user_id, user.display_name, item.id, item.rarity, case.name)
        await users.bump(conn, user_id, "cases_opened", count)
        await progress.track(conn, user_id, "case_open", count)
        level_up = await add_xp(ctx, conn, user_id, case_xp(case.price) * count)
        fresh = await users.get(conn, user_id)
        remaining = (await items.keys(conn, user_id)).get(case_id, 0)
    assert fresh is not None
    return {"items": dropped, "coins": fresh.coins, "keys": remaining, "level_up": level_up}
