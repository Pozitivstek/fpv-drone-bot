"""Кейсы, инвентарь, магазин запчастей и мастерская."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import current_user, get_ctx, limited
from app.api.schemas import Buy, Contract, OpenCase, SellBulk, Uids, Upgrade
from app.context import AppContext
from app.services import cases, inventory, workshop
from app.store.users import User

router = APIRouter(prefix="/api")


@router.get("/cases")
async def list_cases(user: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    return await cases.list_cases(ctx, user)


@router.get("/cases/{case_id}")
async def case_detail(case_id: str, user: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await cases.case_detail(ctx, user, case_id)


@router.post("/cases/{case_id}/open")
async def open_case(case_id: str, body: OpenCase, user: User = Depends(limited("write")),
                    ctx: AppContext = Depends(get_ctx)) -> dict:
    return await cases.open_case(ctx, user.id, case_id, body.count, body.use_keys)


@router.get("/inventory")
async def get_inventory(user: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await inventory.inventory(ctx, user.id)


@router.post("/inventory/sell")
async def sell(body: Uids, user: User = Depends(limited("write")), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await inventory.sell(ctx, user.id, body.uids)


@router.post("/inventory/sell-bulk")
async def sell_bulk(body: SellBulk, user: User = Depends(limited("write")), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await inventory.sell_bulk(ctx, user.id, body.max_rarity)


@router.get("/shop")
async def shop(user: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    return inventory.shop(ctx)


@router.post("/shop/buy")
async def buy(body: Buy, user: User = Depends(limited("write")), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await inventory.buy(ctx, user.id, body.item_id, body.qty)


@router.post("/workshop/upgrade")
async def upgrade(body: Upgrade, user: User = Depends(limited("write")), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await workshop.upgrade(ctx, user.id, body.uids, body.target)


@router.post("/workshop/contract")
async def contract(body: Contract, user: User = Depends(limited("write")), ctx: AppContext = Depends(get_ctx)) -> dict:
    return await workshop.contract(ctx, user.id, body.uids)
