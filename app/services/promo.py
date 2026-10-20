"""Промокоды: активация игроком и управление из админки."""

from __future__ import annotations

import re
import secrets
import string
from datetime import timedelta

from app import clock
from app.context import AppContext
from app.ratelimit import RateLimiter
from app.services.errors import GameError, NotFound
from app.services.players import require_active
from app.services.rewards import Reward, grant
from app.store import social, users

CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{3,32}$")
RANDOM_CODE_LENGTH = 6
MAX_PROMO_DAYS = 365
MAX_PROMO_USES = 1_000_000
FAILED_ATTEMPTS = RateLimiter(limit=8, window=600)  # перебор кодов: 8 промахов за 10 минут


def normalize(code: str) -> str:
    return code.strip().upper()


async def redeem(ctx: AppContext, user_id: int, raw_code: str) -> dict:
    key = str(user_id)
    if FAILED_ATTEMPTS.blocked(key):
        raise GameError("Слишком много неверных кодов. Попробуйте через 10 минут.")
    try:
        return await _redeem(ctx, user_id, normalize(raw_code))
    except GameError:
        FAILED_ATTEMPTS.hit(key)
        raise


async def _redeem(ctx: AppContext, user_id: int, code: str) -> dict:
    if not CODE_PATTERN.match(code):
        raise GameError("Такого промокода нет")
    async with ctx.db.tx() as conn:
        user = await users.get(conn, user_id)
        if user is None:
            raise NotFound("Нет такого игрока")
        require_active(user)
        promo = await social.promo(conn, code)
        if promo is None or not promo.active:
            raise GameError("Такого промокода нет")
        expires = clock.parse(promo.expires_at)
        if expires and expires < clock.now():
            raise GameError("Срок действия промокода истёк")
        if not await social.use_promo(conn, code, user_id):
            raise GameError("Промокод уже использован или закончился")
        reward = Reward.from_dict(promo.reward, ctx.catalog)
        summary = await grant(ctx, conn, user_id, reward, f"promo:{code}")
    return {**summary, "code": code, "text": reward.describe(ctx.catalog)}


def _random_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "FPV-" + "".join(secrets.choice(alphabet) for _ in range(RANDOM_CODE_LENGTH))


async def create(ctx: AppContext, admin_id: int, code: str | None, reward_data: dict, max_uses: int,
                 days: int | None, note: str = "") -> dict:
    reward = Reward.from_dict(reward_data, ctx.catalog)
    final = normalize(code) if code else _random_code()
    if not CODE_PATTERN.match(final):
        raise GameError("Код: 3–32 символа, латиница, цифры, дефис и подчёркивание")
    if not 0 <= max_uses <= MAX_PROMO_USES:
        raise GameError("Лимит активаций: от 0 (без лимита) до 1 000 000")
    if days is not None and not 1 <= days <= MAX_PROMO_DAYS:
        raise GameError("Срок: от 1 до 365 дней")
    expires = clock.iso(clock.now() + timedelta(days=days)) if days else None
    async with ctx.db.tx() as conn:
        if await social.promo(conn, final):
            raise GameError("Такой код уже есть")
        await social.create_promo(conn, final, reward.to_dict(), max_uses, expires, note, admin_id)
        await social.log_admin(conn, admin_id, "promo_create", None, {"code": final, "reward": reward.to_dict()})
    return {"code": final, "text": reward.describe(ctx.catalog), "expires_at": expires}


async def list_all(ctx: AppContext) -> list[dict]:
    result = []
    for promo in await social.promos(ctx.db.conn):
        try:
            text = Reward.from_dict(promo.reward, ctx.catalog).describe(ctx.catalog)
        except GameError:
            text = "награда устарела"
        result.append({"code": promo.code, "text": text, "reward": promo.reward, "max_uses": promo.max_uses,
                       "uses": promo.uses, "expires_at": promo.expires_at, "active": promo.active,
                       "note": promo.note, "created_at": promo.created_at})
    return result


async def set_active(ctx: AppContext, admin_id: int, code: str, active: bool) -> None:
    async with ctx.db.tx() as conn:
        if not await social.set_promo_active(conn, normalize(code), active):
            raise NotFound("Нет такого промокода")
        await social.log_admin(conn, admin_id, "promo_toggle", None, {"code": normalize(code), "active": active})


async def delete(ctx: AppContext, admin_id: int, code: str) -> None:
    async with ctx.db.tx() as conn:
        if not await social.delete_promo(conn, normalize(code)):
            raise NotFound("Нет такого промокода")
        await social.log_admin(conn, admin_id, "promo_delete", None, {"code": normalize(code)})
