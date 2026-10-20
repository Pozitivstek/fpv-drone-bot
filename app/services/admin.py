"""Админка: статистика, карточка игрока и действия над ним, глобальные события, рассылка.

Каждое действие пишется в журнал admin_log, а игрок получает уведомление о подарке.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from app import clock
from app.context import AppContext
from app.db import one
from app.game.drops import MAX_LUCK, MIN_LUCK
from app.game.progression import MAX_LEVEL, RANKS, progress, xp_for_level
from app.services import progress as progress_service
from app.services.errors import Forbidden, GameError, NotFound
from app.services.hangar import hangar
from app.services.inventory import inventory
from app.services.players import collection_value
from app.services.rewards import Reward, grant
from app.store import items, races, social, users
from app.store.users import User

log = logging.getLogger(__name__)

MAX_COIN_DELTA = 10_000_000
MAX_BROADCAST = 3500
BROADCAST_DELAY_S = 0.05  # ~20 сообщений в секунду — в пределах лимитов Telegram


def require_admin(ctx: AppContext, user_id: int) -> None:
    if not ctx.settings.is_admin(user_id):
        raise Forbidden("Раздел только для администратора")


def brief(user: User) -> dict:
    return {"id": user.id, "name": user.display_name, "username": user.username, "level": user.level,
            "coins": user.coins, "luck": round(user.luck, 2), "banned": user.banned, "last_seen": user.last_seen}


async def stats(ctx: AppContext) -> dict:
    conn = ctx.db.conn
    since = clock.iso(clock.now() - timedelta(days=1))
    totals = await one(conn, "SELECT COUNT(*) AS users, COALESCE(SUM(coins), 0) AS coins,"
                             " COALESCE(SUM(cases_opened), 0) AS cases, COALESCE(SUM(races), 0) AS races,"
                             " SUM(last_seen >= ?) AS active, SUM(created_at >= ?) AS new FROM users", (since, since))
    return {"users": totals["users"], "active_24h": totals["active"] or 0, "new_24h": totals["new"] or 0,
            "coins": totals["coins"], "cases_opened": totals["cases"], "races": totals["races"],
            "races_24h": await races.count_since(conn, since), "rare_drops_24h": await social.count_drops_since(conn, since),
            "items": await items.count_all(conn), "events": await progress_service.events(conn),
            "broadcast": {key: value for key, value in ctx.broadcast_state.items() if not key.startswith("_")}}


async def search(ctx: AppContext, query: str) -> list[dict]:
    found = await users.search(ctx.db.conn, query) if query.strip() else await users.recent(ctx.db.conn)
    return [brief(user) for user in found]


async def user_card(ctx: AppContext, target_id: int) -> dict:
    user = await users.get(ctx.db.conn, target_id)
    if user is None:
        raise NotFound("Игрок не найден")
    value, count = await collection_value(ctx, target_id)
    return {**brief(user), "progress": progress(user.xp), "created_at": user.created_at,
            "stats": {"cases_opened": user.cases_opened, "races": user.races, "golds": user.golds, "items": count,
                      "collection": value, "referrals": await users.count_referrals(ctx.db.conn, target_id)},
            "inventory": await inventory(ctx, target_id), "hangar": await hangar(ctx, target_id)}


async def _target(conn, target_id: int) -> User:
    user = await users.get(conn, target_id)
    if user is None:
        raise NotFound("Игрок не найден")
    return user


async def adjust_coins(ctx: AppContext, admin_id: int, target_id: int, delta: int) -> dict:
    if not delta or abs(delta) > MAX_COIN_DELTA:
        raise GameError("Сумма: от 1 до 10 млн (можно со знаком минус)")
    async with ctx.db.tx() as conn:
        user = await _target(conn, target_id)
        applied = max(delta, -user.coins)
        await users.add_coins(conn, target_id, applied)
        await social.log_admin(conn, admin_id, "coins", target_id, {"delta": applied})
        if applied > 0:
            ctx.notify_after_commit(target_id, f"🎁 Администратор начислил вам {applied} монет!")
    return {"applied": applied}


async def set_level(ctx: AppContext, admin_id: int, target_id: int, level: int) -> dict:
    if not 1 <= level <= MAX_LEVEL:
        raise GameError(f"Уровень: от 1 до {MAX_LEVEL}")
    async with ctx.db.tx() as conn:
        user = await _target(conn, target_id)
        await users.update(conn, target_id, level=level, xp=xp_for_level(level))
        await social.log_admin(conn, admin_id, "level", target_id, {"from": user.level, "to": level})
        if level > user.level:
            ctx.notify_after_commit(target_id, f"⚡ Администратор повысил вас до {level} уровня!")
    return {"level": level}


async def set_rank(ctx: AppContext, admin_id: int, target_id: int, rank_index: int) -> dict:
    if not 0 <= rank_index < len(RANKS):
        raise GameError("Нет такого ранга")
    return await set_level(ctx, admin_id, target_id, RANKS[rank_index].level)


async def set_luck(ctx: AppContext, admin_id: int, target_id: int, luck: float) -> dict:
    if not MIN_LUCK <= luck <= MAX_LUCK:
        raise GameError(f"Удача: от {MIN_LUCK} до {MAX_LUCK}")
    async with ctx.db.tx() as conn:
        user = await _target(conn, target_id)
        await users.update(conn, target_id, luck=round(luck, 2))
        await social.log_admin(conn, admin_id, "luck", target_id, {"from": user.luck, "to": round(luck, 2)})
    return {"luck": round(luck, 2)}


async def give(ctx: AppContext, admin_id: int, target_id: int, reward_data: dict) -> dict:
    reward = Reward.from_dict(reward_data, ctx.catalog)
    async with ctx.db.tx() as conn:
        await _target(conn, target_id)
        summary = await grant(ctx, conn, target_id, reward, "admin")
        await social.log_admin(conn, admin_id, "give", target_id, reward.to_dict())
        ctx.notify_after_commit(target_id, f"🎁 Подарок от администратора: {reward.describe(ctx.catalog)}")
    return summary


async def set_ban(ctx: AppContext, admin_id: int, target_id: int, banned: bool) -> dict:
    if target_id == admin_id and banned:
        raise GameError("Себя забанить нельзя")
    async with ctx.db.tx() as conn:
        await _target(conn, target_id)
        await users.update(conn, target_id, banned=int(banned))
        await social.log_admin(conn, admin_id, "ban" if banned else "unban", target_id, {})
    return {"banned": banned}


async def take_item(ctx: AppContext, admin_id: int, target_id: int, uid: int) -> None:
    async with ctx.db.tx() as conn:
        await _target(conn, target_id)
        found = await items.get_many(conn, target_id, [uid])
        if not found:
            raise NotFound("У игрока нет такой детали")
        await items.unequip(conn, target_id, [uid])
        await items.remove(conn, target_id, [uid])
        await social.log_admin(conn, admin_id, "take_item", target_id, {"uid": uid, "item": found[0].item_id})


async def repair_all(ctx: AppContext, admin_id: int, target_id: int) -> dict:
    async with ctx.db.tx() as conn:
        await _target(conn, target_id)
        worn = [o.uid for o in await items.owned(conn, target_id) if o.wear > 0]
        await items.set_wear(conn, target_id, worn, 0)
        await social.log_admin(conn, admin_id, "repair_all", target_id, {"count": len(worn)})
        if worn:
            ctx.notify_after_commit(target_id, "🔧 Администратор бесплатно починил все ваши детали!")
    return {"repaired": len(worn)}


async def set_event(ctx: AppContext, admin_id: int, key: str, value: float) -> dict:
    async with ctx.db.tx() as conn:
        applied = await progress_service.set_event(conn, key, value)
        await social.log_admin(conn, admin_id, "event", None, {"key": key, "value": applied})
    return {"key": key, "value": applied}


async def admin_log(ctx: AppContext) -> list[dict]:
    return await social.admin_log(ctx.db.conn)


async def broadcast(ctx: AppContext, admin_id: int, text: str) -> dict:
    """Запускает рассылку в фоне; прогресс виден в статистике."""
    message = text.strip()
    if not message or len(message) > MAX_BROADCAST:
        raise GameError(f"Текст рассылки: от 1 до {MAX_BROADCAST} символов")
    if ctx.notifier is None:
        raise GameError("Бот не подключён — рассылка недоступна")
    if ctx.broadcast_state.get("running"):
        raise GameError("Предыдущая рассылка ещё идёт")
    ctx.broadcast_state.clear()
    ctx.broadcast_state.update(running=True, total=0, sent=0, failed=0, started_at=clock.iso())
    try:
        recipients = await users.all_ids(ctx.db.conn)
        async with ctx.db.tx() as conn:
            await social.log_admin(conn, admin_id, "broadcast", None, {"text": message[:200], "total": len(recipients)})
    except BaseException:
        ctx.broadcast_state["running"] = False
        raise
    ctx.broadcast_state["total"] = len(recipients)
    task = asyncio.create_task(_run_broadcast(ctx, recipients, message))
    ctx.broadcast_state["_task"] = task
    return {"total": len(recipients)}


async def _run_broadcast(ctx: AppContext, recipients: list[int], text: str) -> None:
    notifier = ctx.notifier
    assert notifier is not None
    for chat_id in recipients:
        try:
            await notifier(chat_id, text, "Открыть игру")
            ctx.broadcast_state["sent"] += 1
        except Exception:
            log.info("broadcast to %s failed", chat_id, exc_info=True)
            ctx.broadcast_state["failed"] += 1
        await asyncio.sleep(BROADCAST_DELAY_S)
    ctx.broadcast_state["running"] = False
    ctx.broadcast_state["finished_at"] = clock.iso()
