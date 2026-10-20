"""Зависимости FastAPI: текущий игрок по initData, админ, ограничение частоты запросов."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status

from app.api.auth import InitDataError, validate
from app.context import AppContext
from app.ratelimit import RateLimiter
from app.services import players
from app.store.users import User


LIMITERS = {
    "write": RateLimiter(limit=150, window=60),
    "race": RateLimiter(limit=30, window=60),
    "promo": RateLimiter(limit=10, window=60),
    "read": RateLimiter(limit=40, window=60),
}


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


async def current_user(ctx: AppContext = Depends(get_ctx),
                       init_data: str = Header(default="", alias="X-Telegram-Init-Data")) -> User:
    settings = ctx.settings
    if not init_data and settings.dev_mode:
        return await players.ensure(ctx, settings.dev_user_id, "Разработчик", "dev")
    try:
        tg_user, fields = validate(init_data, settings.bot_token, settings.init_data_ttl)
    except InitDataError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Не удалось войти: {exc}") from exc
    return await players.ensure(ctx, tg_user["id"], tg_user.get("first_name", ""), tg_user.get("username", ""),
                                fields.get("start_param"))


def limited(bucket: str):
    limiter = LIMITERS[bucket]

    async def dependency(user: User = Depends(current_user)) -> User:
        if not limiter.allow(f"{bucket}:{user.id}"):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Слишком часто. Подождите немного.")
        return user
    return dependency


async def admin_user(user: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)) -> User:
    if not ctx.settings.is_admin(user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Раздел только для администратора")
    return user
