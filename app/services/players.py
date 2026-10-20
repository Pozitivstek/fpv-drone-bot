"""Регистрация игрока (стартовый комплект, реферал) и профиль."""

from __future__ import annotations

from html import escape

from app import clock
from app.context import AppContext
from app.game.defs import TIER
from app.game.progression import progress
from app.services import progress as progress_service
from app.services.players_guard import require_active
from app.services.rewards import REF_STAGES, give_kit
from app.store import builds, items, users
from app.store.users import User

REF_PREFIX = "ref_"
NEW_PLAYER_REF_BONUS = 200
STARTER_KIT = "starter"
STARTER_KEYS = {"starter": 1, "daily": 1}
TOUCH_INTERVAL_S = 300


def referrer_from(start_param: str | None, user_id: int) -> int | None:
    text = (start_param or "").strip()
    if not text.startswith(REF_PREFIX) or not text[len(REF_PREFIX):].isdigit():
        return None
    referrer = int(text[len(REF_PREFIX):])
    return referrer if referrer != user_id else None


async def ensure(ctx: AppContext, user_id: int, first_name: str = "", username: str = "",
                 start_param: str | None = None) -> User:
    """Возвращает игрока, при первом входе — создаёт со стартовым комплектом."""
    user = await users.get(ctx.db.conn, user_id)
    if user and user.first_name == first_name[:64] and user.username == username[:64]:
        seen = clock.parse(user.last_seen)
        if seen and (clock.now() - seen).total_seconds() < TOUCH_INTERVAL_S:
            return user
    async with ctx.db.tx() as conn:
        user = await users.get(conn, user_id)
        if user:
            await users.touch(conn, user_id, first_name, username)
        else:
            await _register(ctx, conn, user_id, first_name, username, start_param)
        fresh = await users.get(conn, user_id)
    assert fresh is not None
    return fresh


async def _register(ctx: AppContext, conn, user_id: int, first_name: str, username: str,
                    start_param: str | None) -> None:
    referrer_id = referrer_from(start_param, user_id)
    if referrer_id and await users.get(conn, referrer_id) is None:
        referrer_id = None
    created = await users.create(conn, user_id, first_name, username, referrer_id)
    await give_kit(ctx, conn, user_id, STARTER_KIT, "starter")
    for case_id, qty in STARTER_KEYS.items():
        await items.add_keys(conn, user_id, case_id, qty)
    if referrer_id:
        # Пригласившему платим позже — когда друг реально поиграет (см. REF_STAGES в rewards).
        await users.add_coins(conn, user_id, NEW_PLAYER_REF_BONUS)
        first_level, first_coins = REF_STAGES[0]
        ctx.notify_after_commit(referrer_id, f"🛸 По вашей ссылке пришёл пилот {escape(created.display_name)}! "
                                             f"Когда он дойдёт до {first_level} уровня — вам +{first_coins} монет.")


def ref_link(ctx: AppContext, user_id: int) -> str:
    username = ctx.settings.bot_username
    return f"https://t.me/{username}?start={REF_PREFIX}{user_id}" if username else ""


async def collection_value(ctx: AppContext, user_id: int) -> tuple[int, int]:
    """Стоимость и количество всех деталей игрока."""
    owned = await items.owned(ctx.db.conn, user_id)
    value = sum(ctx.catalog.items[o.item_id].value for o in owned if o.item_id in ctx.catalog.items)
    return value, len(owned)


async def profile(ctx: AppContext, user: User) -> dict:
    conn = ctx.db.conn
    value, count = await collection_value(ctx, user.id)
    owned = await items.owned(conn, user.id)
    best = max((ctx.catalog.items[o.item_id] for o in owned if o.item_id in ctx.catalog.items),
               key=lambda item: (TIER[item.rarity], item.value), default=None)
    return {
        "id": user.id, "name": user.display_name, "username": user.username, "coins": user.coins,
        "progress": progress(user.xp), "luck": round(user.luck, 2), "banned": user.banned,
        "is_admin": ctx.settings.is_admin(user.id),
        "stats": {"cases_opened": user.cases_opened, "races": user.races, "golds": user.golds,
                  "items": count, "collection": value, "builds": len(await builds.list_for(conn, user.id)),
                  "referrals": await users.count_referrals(conn, user.id)},
        "best_item": best.id if best else None,
        "keys": await items.keys(conn, user.id),
        "daily": progress_service.daily_state(user.streak, user.daily_last),
        "events": await progress_service.events(conn),
        "ref_link": ref_link(ctx, user.id),
        "ref_bonus": {"friend": NEW_PLAYER_REF_BONUS,
                      "stages": [{"level": level, "coins": coins} for level, coins in REF_STAGES]},
    }
