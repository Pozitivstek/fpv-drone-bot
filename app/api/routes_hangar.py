"""Ангар (сборки, детали, очки и пульт, ремонт) и гонки."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import current_user, get_ctx, limited
from app.api.schemas import IdPath, Name, RaceFinish, RaceStart, Slot, Uids
from app.context import AppContext
from app.services import hangar, racing
from app.store.users import User

router = APIRouter(prefix="/api")


@router.get("/hangar")
async def get_hangar(user: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await hangar.hangar(ctx, user.id)


@router.post("/hangar/builds")
async def create_build(body: Name, user: User = Depends(limited("write")), ctx: AppContext = Depends(get_ctx)) -> dict:
    return {"id": await hangar.create_build(ctx, user.id, body.name)}


@router.patch("/hangar/builds/{build_id}")
async def rename_build(build_id: IdPath, body: Name, user: User = Depends(limited("write")),
                       ctx: AppContext = Depends(get_ctx)) -> dict:
    await hangar.rename_build(ctx, user.id, build_id, body.name)
    return {"ok": True}


@router.delete("/hangar/builds/{build_id}")
async def delete_build(build_id: IdPath, user: User = Depends(limited("write")), ctx: AppContext = Depends(get_ctx)) -> dict:
    await hangar.delete_build(ctx, user.id, build_id)
    return {"ok": True}


@router.post("/hangar/builds/{build_id}/activate")
async def activate(build_id: IdPath, user: User = Depends(limited("write")), ctx: AppContext = Depends(get_ctx)) -> dict:
    await hangar.set_active(ctx, user.id, build_id)
    return {"ok": True}


@router.put("/hangar/builds/{build_id}/slots/{slot}")
async def equip(build_id: IdPath, slot: str, body: Slot, user: User = Depends(limited("write")),
                ctx: AppContext = Depends(get_ctx)) -> dict:
    await hangar.equip(ctx, user.id, build_id, slot, body.uid)
    return {"ok": True}


@router.put("/hangar/gear/{slot}")
async def equip_gear(slot: str, body: Slot, user: User = Depends(limited("write")),
                     ctx: AppContext = Depends(get_ctx)) -> dict:
    await hangar.equip_gear(ctx, user.id, slot, body.uid)
    return {"ok": True}


@router.post("/hangar/repair")
async def repair(body: Uids, user: User = Depends(limited("write")), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await hangar.repair(ctx, user.id, body.uids)


@router.get("/tracks")
async def tracks(user: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    return await racing.tracks(ctx, user)


@router.get("/tracks/{track_id}/leaderboard")
async def track_leaderboard(track_id: str, user: User = Depends(current_user),
                            ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    return await racing.leaderboard(ctx, track_id)


@router.post("/race/start")
async def race_start(body: RaceStart, user: User = Depends(limited("race")), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await racing.start(ctx, user.id, body.track_id, body.training)


@router.post("/race/{race_id}/finish")
async def race_finish(race_id: IdPath, body: RaceFinish, user: User = Depends(limited("race")),
                      ctx: AppContext = Depends(get_ctx)) -> dict:
    return await racing.finish(ctx, user.id, race_id, body.model_dump())
