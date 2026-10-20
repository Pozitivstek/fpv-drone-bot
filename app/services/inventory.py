"""Инвентарь: список деталей, продажа (поштучно и пачкой) и магазин запчастей."""

from __future__ import annotations

from app.context import AppContext
from app.game.defs import RARITIES, TIER
from app.services import progress
from app.services.errors import GameError, NotFound
from app.services.players import require_active
from app.services.views import item_view, sell_price, shop_price
from app.store import items, users

MAX_SELL = 200
MAX_BUY = 10


async def inventory(ctx: AppContext, user_id: int) -> dict:
    conn = ctx.db.conn
    owned = await items.owned(conn, user_id)
    locked = await items.locked(conn, user_id)
    views = [item_view(ctx.catalog.items[o.item_id], o.uid, o.wear, o.uid in locked)
             for o in owned if o.item_id in ctx.catalog.items]
    return {"items": views, "keys": await items.keys(conn, user_id),
            "value": sum(view["value"] for view in views)}


async def _sell(ctx: AppContext, conn, user_id: int, uids: list[int]) -> dict:
    owned = await items.get_many(conn, user_id, uids)
    if len(owned) != len(set(uids)):
        raise NotFound("Некоторых деталей уже нет в инвентаре")
    if set(uids) & await items.locked(conn, user_id):
        raise GameError("Сначала снимите детали со сборки")
    coins = sum(sell_price(ctx.catalog.items[o.item_id], o.wear) if o.item_id in ctx.catalog.items else 1
                for o in owned)  # снятая с каталога деталь продаётся за символическую монету
    await items.remove(conn, user_id, uids)
    await users.add_coins(conn, user_id, coins)
    await progress.track(conn, user_id, "sell", len(owned))
    fresh = await users.get(conn, user_id)
    return {"sold": len(owned), "earned": coins, "coins": fresh.coins if fresh else 0}


async def sell(ctx: AppContext, user_id: int, uids: list[int]) -> dict:
    unique = list(dict.fromkeys(uids))
    if not 1 <= len(unique) <= MAX_SELL:
        raise GameError(f"Выберите от 1 до {MAX_SELL} деталей")
    async with ctx.db.tx() as conn:
        user = await users.get(conn, user_id)
        if user is None:
            raise NotFound("Нет такого игрока")
        require_active(user)
        return await _sell(ctx, conn, user_id, unique)


async def sell_bulk(ctx: AppContext, user_id: int, max_rarity: str) -> dict:
    """Продаёт все свободные детали до указанной редкости включительно."""
    if max_rarity not in RARITIES:
        raise GameError("Неизвестная редкость")
    async with ctx.db.tx() as conn:
        user = await users.get(conn, user_id)
        if user is None:
            raise NotFound("Нет такого игрока")
        require_active(user)
        locked = await items.locked(conn, user_id)
        uids = [o.uid for o in await items.owned(conn, user_id)
                if o.uid not in locked and o.item_id in ctx.catalog.items
                and ctx.catalog.items[o.item_id].tier <= TIER[max_rarity]][:MAX_SELL]
        if not uids:
            raise GameError("Нечего продавать: всё занято в сборках или выше выбранной редкости")
        return await _sell(ctx, conn, user_id, uids)


def shop(ctx: AppContext) -> list[dict]:
    result = []
    for item in ctx.catalog.items.values():
        price = shop_price(item)
        if price is not None:
            result.append({**item_view(item), "price": price})
    return sorted(result, key=lambda view: (view["slot"], view["price"]))


async def buy(ctx: AppContext, user_id: int, item_id: str, qty: int = 1) -> dict:
    item = ctx.catalog.items.get(item_id)
    if item is None:
        raise NotFound("Нет такой детали")
    price = shop_price(item)
    if price is None:
        raise GameError("Эту деталь можно получить только из кейсов")
    if not 1 <= qty <= MAX_BUY:
        raise GameError(f"За раз можно купить от 1 до {MAX_BUY} штук")
    async with ctx.db.tx() as conn:
        user = await users.get(conn, user_id)
        if user is None:
            raise NotFound("Нет такого игрока")
        require_active(user)
        if not await users.spend(conn, user_id, price * qty):
            raise GameError("Не хватает монет")
        bought = [item_view(item, await items.add(conn, user_id, item_id, "shop")) for _ in range(qty)]
        fresh = await users.get(conn, user_id)
    return {"items": bought, "coins": fresh.coins if fresh else 0}
