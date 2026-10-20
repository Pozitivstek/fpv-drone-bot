"""Мастерская: апгрейд и контракты."""

from __future__ import annotations

from aiosqlite import Connection

from app.catalog import Item
from app.context import AppContext
from app.game.defs import FEED_MIN_TIER
from app.game.workshop import CONTRACT_SIZE, UPGRADE_MAX_INPUTS, contract_rarity, upgrade_chance
from app.services import progress
from app.services.errors import GameError, NotFound
from app.services.players import require_active
from app.services.views import item_view
from app.store import items, social, users
from app.store.items import Owned
from app.store.users import User

WORN_VALUE_FACTOR = 200  # изношенная деталь в ставке стоит меньше: при 100 % — половину


def stake_value(item: Item, wear: int) -> int:
    return round(item.value * (1 - wear / WORN_VALUE_FACTOR))


async def _take(ctx: AppContext, conn: Connection, user_id: int, uids: list[int]) -> tuple[User, list[Owned]]:
    user = await users.get(conn, user_id)
    if user is None:
        raise NotFound("Нет такого игрока")
    require_active(user)
    owned = await items.get_many(conn, user_id, uids)
    if len(owned) != len(uids) or any(o.item_id not in ctx.catalog.items for o in owned):
        raise NotFound("Некоторых деталей уже нет в инвентаре")
    if set(uids) & await items.locked(conn, user_id):
        raise GameError("Сначала снимите детали со сборки")
    return user, owned


async def _award(ctx: AppContext, conn: Connection, user: User, item: Item, source: str) -> dict:
    uid = await items.add(conn, user.id, item.id, source)
    if item.tier >= FEED_MIN_TIER:
        await social.add_drop(conn, user.id, user.display_name, item.id, item.rarity, source)
    return item_view(item, uid)


async def upgrade(ctx: AppContext, user_id: int, uids: list[int], target_id: str) -> dict:
    unique = list(dict.fromkeys(uids))
    if not 1 <= len(unique) <= UPGRADE_MAX_INPUTS:
        raise GameError(f"В апгрейд можно положить от 1 до {UPGRADE_MAX_INPUTS} деталей")
    target = ctx.catalog.items.get(target_id)
    if target is None:
        raise NotFound("Нет такой детали")
    async with ctx.db.tx() as conn:
        user, owned = await _take(ctx, conn, user_id, unique)
        stake = sum(stake_value(ctx.catalog.items[o.item_id], o.wear) for o in owned)
        luck = user.luck * (await progress.events(conn))["luck_event"]
        chance = upgrade_chance(stake, target.value, luck)
        await items.remove(conn, user_id, unique)
        success = ctx.rng.random() < chance
        prize = await _award(ctx, conn, user, target, "Апгрейд") if success else None
        await progress.track(conn, user_id, "workshop")
    return {"success": success, "chance": chance, "item": prize, "lost": len(unique)}


async def contract(ctx: AppContext, user_id: int, uids: list[int]) -> dict:
    unique = list(dict.fromkeys(uids))
    if len(unique) != CONTRACT_SIZE:
        raise GameError(f"Для контракта нужно ровно {CONTRACT_SIZE} разных деталей")
    async with ctx.db.tx() as conn:
        user, owned = await _take(ctx, conn, user_id, unique)
        target_rarity = contract_rarity([ctx.catalog.items[o.item_id].rarity for o in owned])
        prize = ctx.rng.choice(ctx.catalog.by_rarity(target_rarity))
        await items.remove(conn, user_id, unique)
        view = await _award(ctx, conn, user, prize, "Контракт")
        await progress.track(conn, user_id, "workshop")
    return {"item": view}
