"""Профиль, каталог, ежедневный бонус, задания, лента, рейтинги и промокоды."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import current_user, get_ctx, limited
from app.api.schemas import Promo
from app.context import AppContext
from app.services import players, progress, promo, social
from app.services.views import catalog_payload
from app.store.users import User

router = APIRouter(prefix="/api")


@router.get("/catalog")
async def catalog(ctx: AppContext = Depends(get_ctx)) -> dict:
    return catalog_payload(ctx.catalog)


@router.get("/me")
async def me(user: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await players.profile(ctx, user)


@router.post("/daily")
async def daily(user: User = Depends(limited("write")), ctx: AppContext = Depends(get_ctx)) -> dict:
    players.require_active(user)
    return await progress.claim_daily(ctx, user.id)


@router.get("/tasks")
async def tasks(user: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    return await progress.task_list(ctx, user.id)


@router.post("/tasks/{task_id}/claim")
async def claim(task_id: str, user: User = Depends(limited("write")), ctx: AppContext = Depends(get_ctx)) -> dict:
    players.require_active(user)
    return await progress.claim_task(ctx, user.id, task_id)


@router.get("/feed")
async def feed(user: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    return await social.feed(ctx)


@router.get("/leaderboard")
async def leaderboard(kind: str = Query("level", max_length=16), user: User = Depends(limited("read")),
                      ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    return await social.leaderboard(ctx, kind)


@router.post("/promo")
async def redeem(body: Promo, user: User = Depends(limited("promo")), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await promo.redeem(ctx, user.id, body.code)
