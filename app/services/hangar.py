"""Ангар: сборки, установка деталей, очки и пульт, ремонт."""

from __future__ import annotations

from aiosqlite import Connection

from app.context import AppContext
from app.game.builds import BuildReport, Part, evaluate
from app.game.defs import GEAR, MAX_BUILDS, SLOT_TITLES, SLOTS
from app.services import progress
from app.services.errors import GameError, NotFound
from app.services.players import require_active
from app.services.views import item_view
from app.store import builds, items, users
from app.store.builds import Build
from app.store.users import User

MAX_NAME = 40


def _clean_name(name: str) -> str:
    cleaned = " ".join(name.split())[:MAX_NAME]
    if not cleaned:
        raise GameError("Дайте сборке имя")
    return cleaned


async def _parts(ctx: AppContext, conn: Connection, user: User, build: Build | None
                 ) -> tuple[dict[str, Part | None], Part | None, Part | None]:
    uids = [uid for uid in (build.slots.values() if build else ()) if uid] \
        + [uid for uid in (user.goggles_uid, user.radio_uid) if uid]
    owned = {o.uid: o for o in await items.get_many(conn, user.id, uids)}

    def part(uid: int | None) -> Part | None:
        found = owned.get(uid) if uid else None
        if found is None or found.item_id not in ctx.catalog.items:
            return None
        return Part(ctx.catalog.items[found.item_id], found.wear, found.uid)

    slots = {slot: part(build.slots.get(slot)) for slot in SLOTS} if build else {slot: None for slot in SLOTS}
    return slots, part(user.goggles_uid), part(user.radio_uid)


def _part_view(part: Part | None) -> dict | None:
    return item_view(part.item, part.uid, part.wear, True) if part else None


def _build_view(build: Build, report: BuildReport, slots: dict[str, Part | None], active: bool) -> dict:
    return {"id": build.id, "name": build.name, "active": active, "cls": report.cls, "rating": report.rating,
            "ready": report.ready, "issues": list(report.issues), "stats": report.stats,
            "parts": {slot: _part_view(slots[slot]) for slot in SLOTS}}


async def active_build(ctx: AppContext, conn: Connection, user: User
                       ) -> tuple[Build | None, BuildReport, dict[str, Part | None]]:
    build = await builds.get(conn, user.id, user.active_build_id) if user.active_build_id else None
    slots, goggles, radio = await _parts(ctx, conn, user, build)
    return build, evaluate(slots, goggles, radio), {**slots, "goggles": goggles, "radio": radio}


async def hangar(ctx: AppContext, user_id: int) -> dict:
    conn = ctx.db.conn
    user = await users.get(conn, user_id)
    if user is None:
        raise NotFound("Нет такого игрока")
    views = []
    goggles = radio = None
    for build in await builds.list_for(conn, user_id):
        slots, goggles, radio = await _parts(ctx, conn, user, build)
        views.append(_build_view(build, evaluate(slots, goggles, radio), slots, build.id == user.active_build_id))
    if not views:
        _, goggles, radio = await _parts(ctx, conn, user, None)
    return {"builds": views, "active_id": user.active_build_id, "goggles": _part_view(goggles),
            "radio": _part_view(radio), "max_builds": MAX_BUILDS}


async def _user(conn: Connection, user_id: int) -> User:
    user = await users.get(conn, user_id)
    if user is None:
        raise NotFound("Нет такого игрока")
    require_active(user)
    return user


async def create_build(ctx: AppContext, user_id: int, name: str) -> int:
    async with ctx.db.tx() as conn:
        user = await _user(conn, user_id)
        if len(await builds.list_for(conn, user_id)) >= MAX_BUILDS:
            raise GameError(f"В ангаре помещается {MAX_BUILDS} сборок")
        build_id = await builds.create(conn, user_id, _clean_name(name))
        if not user.active_build_id:
            await users.update(conn, user_id, active_build_id=build_id)
        return build_id


async def rename_build(ctx: AppContext, user_id: int, build_id: int, name: str) -> None:
    async with ctx.db.tx() as conn:
        await _user(conn, user_id)
        if not await builds.rename(conn, user_id, build_id, _clean_name(name)):
            raise NotFound("Нет такой сборки")


async def delete_build(ctx: AppContext, user_id: int, build_id: int) -> None:
    """Разбирает сборку: детали остаются в инвентаре."""
    async with ctx.db.tx() as conn:
        user = await _user(conn, user_id)
        if not await builds.delete(conn, user_id, build_id):
            raise NotFound("Нет такой сборки")
        if user.active_build_id == build_id:
            remaining = await builds.list_for(conn, user_id)
            await users.update(conn, user_id, active_build_id=remaining[0].id if remaining else None)


async def set_active(ctx: AppContext, user_id: int, build_id: int) -> None:
    async with ctx.db.tx() as conn:
        await _user(conn, user_id)
        if await builds.get(conn, user_id, build_id) is None:
            raise NotFound("Нет такой сборки")
        await users.update(conn, user_id, active_build_id=build_id)


async def _owned_item(ctx: AppContext, conn: Connection, user_id: int, uid: int, slot: str):
    found = await items.get_many(conn, user_id, [uid])
    if not found or found[0].item_id not in ctx.catalog.items:
        raise NotFound("Нет такой детали в инвентаре")
    item = ctx.catalog.items[found[0].item_id]
    if item.slot != slot:
        raise GameError(f"{item.name} — это не «{SLOT_TITLES[slot].lower()}»")
    return item


async def equip(ctx: AppContext, user_id: int, build_id: int, slot: str, uid: int | None) -> None:
    if slot not in SLOTS:
        raise GameError("Неизвестный слот")
    async with ctx.db.tx() as conn:
        await _user(conn, user_id)
        if await builds.get(conn, user_id, build_id) is None:
            raise NotFound("Нет такой сборки")
        if uid is not None:
            await _owned_item(ctx, conn, user_id, uid, slot)
            await builds.free_uid(conn, user_id, uid)
        await builds.set_slot(conn, user_id, build_id, slot, uid)


async def equip_gear(ctx: AppContext, user_id: int, slot: str, uid: int | None) -> None:
    if slot not in GEAR:
        raise GameError("Неизвестный слот")
    async with ctx.db.tx() as conn:
        await _user(conn, user_id)
        if uid is not None:
            await _owned_item(ctx, conn, user_id, uid, slot)
        await users.update(conn, user_id, **{f"{slot}_uid": uid})


async def repair(ctx: AppContext, user_id: int, uids: list[int]) -> dict:
    unique = list(dict.fromkeys(uids))
    if not unique:
        raise GameError("Нечего чинить")
    async with ctx.db.tx() as conn:
        await _user(conn, user_id)
        owned = [o for o in await items.get_many(conn, user_id, unique)
                 if o.wear > 0 and o.item_id in ctx.catalog.items]
        if not owned:
            raise GameError("Эти детали как новые")
        cost = sum(item_view(ctx.catalog.items[o.item_id], o.uid, o.wear)["repair"] for o in owned)
        if not await users.spend(conn, user_id, cost):
            raise GameError(f"Ремонт стоит {cost} монет — не хватает")
        await items.set_wear(conn, user_id, [o.uid for o in owned], 0)
        await progress.track(conn, user_id, "repair")
        fresh = await users.get(conn, user_id)
    return {"repaired": len(owned), "cost": cost, "coins": fresh.coins if fresh else 0}
