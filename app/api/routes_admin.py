"""Админка: доступна только Telegram ID из ADMIN_IDS."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import admin_user, get_ctx
from app.api.schemas import IdPath, Ban, Broadcast, CoinsDelta, Event, GiveReward, Level, Luck, PromoCreate, PromoToggle, RankIndex
from app.context import AppContext
from app.services import admin, promo
from app.store.users import User

router = APIRouter(prefix="/api/admin")


@router.get("/stats")
async def stats(user: User = Depends(admin_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await admin.stats(ctx)


@router.get("/users")
async def search(q: str = Query("", max_length=64), user: User = Depends(admin_user),
                 ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    return await admin.search(ctx, q)


@router.get("/users/{target_id}")
async def card(target_id: IdPath, user: User = Depends(admin_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await admin.user_card(ctx, target_id)


@router.post("/users/{target_id}/coins")
async def coins(target_id: IdPath, body: CoinsDelta, user: User = Depends(admin_user),
                ctx: AppContext = Depends(get_ctx)) -> dict:
    return await admin.adjust_coins(ctx, user.id, target_id, body.delta)


@router.post("/users/{target_id}/level")
async def level(target_id: IdPath, body: Level, user: User = Depends(admin_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await admin.set_level(ctx, user.id, target_id, body.level)


@router.post("/users/{target_id}/rank")
async def rank(target_id: IdPath, body: RankIndex, user: User = Depends(admin_user),
               ctx: AppContext = Depends(get_ctx)) -> dict:
    return await admin.set_rank(ctx, user.id, target_id, body.rank)


@router.post("/users/{target_id}/luck")
async def luck(target_id: IdPath, body: Luck, user: User = Depends(admin_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await admin.set_luck(ctx, user.id, target_id, body.luck)


@router.post("/users/{target_id}/give")
async def give(target_id: IdPath, body: GiveReward, user: User = Depends(admin_user),
               ctx: AppContext = Depends(get_ctx)) -> dict:
    return await admin.give(ctx, user.id, target_id, body.model_dump())


@router.post("/users/{target_id}/ban")
async def ban(target_id: IdPath, body: Ban, user: User = Depends(admin_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await admin.set_ban(ctx, user.id, target_id, body.banned)


@router.post("/users/{target_id}/repair")
async def repair(target_id: IdPath, user: User = Depends(admin_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await admin.repair_all(ctx, user.id, target_id)


@router.delete("/users/{target_id}/items/{uid}")
async def take_item(target_id: IdPath, uid: IdPath, user: User = Depends(admin_user),
                    ctx: AppContext = Depends(get_ctx)) -> dict:
    await admin.take_item(ctx, user.id, target_id, uid)
    return {"ok": True}


@router.get("/promos")
async def promos(user: User = Depends(admin_user), ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    return await promo.list_all(ctx)


@router.post("/promos")
async def create_promo(body: PromoCreate, user: User = Depends(admin_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await promo.create(ctx, user.id, body.code, body.reward.model_dump(), body.max_uses, body.days, body.note)


@router.patch("/promos/{code}")
async def toggle_promo(code: str, body: PromoToggle, user: User = Depends(admin_user),
                       ctx: AppContext = Depends(get_ctx)) -> dict:
    await promo.set_active(ctx, user.id, code, body.active)
    return {"ok": True}


@router.delete("/promos/{code}")
async def delete_promo(code: str, user: User = Depends(admin_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    await promo.delete(ctx, user.id, code)
    return {"ok": True}


@router.post("/events")
async def event(body: Event, user: User = Depends(admin_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await admin.set_event(ctx, user.id, body.key, body.value)


@router.post("/broadcast")
async def broadcast(body: Broadcast, user: User = Depends(admin_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await admin.broadcast(ctx, user.id, body.text)


@router.get("/log")
async def admin_log(user: User = Depends(admin_user), ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    return await admin.admin_log(ctx)
