"""Выдача наград одним пакетом: монеты, опыт (с повышением уровня), детали, ключи, комплекты."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

from aiosqlite import Connection

from app.catalog import Catalog
from app.context import AppContext
from app.game.defs import MAX_BUILDS
from app.game.progression import level_for_xp, level_reward, rank_for_level
from app.services.errors import GameError, NotFound
from app.services.quests import track
from app.services.views import item_view
from app.store import builds, items, users

# Бонусы пригласившему: (уровень друга, монеты). Платятся по очереди, когда друг дорастает до уровня.
REF_STAGES = ((3, 300), (5, 700))
MAX_REWARD_COINS = 10_000_000
MAX_REWARD_ITEMS = 50


@dataclass(frozen=True)
class Reward:
    coins: int = 0
    xp: int = 0
    items: tuple[str, ...] = ()
    keys: dict[str, int] = field(default_factory=dict)
    kits: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict, catalog: Catalog) -> "Reward":
        reward = cls(coins=int(data.get("coins") or 0), xp=int(data.get("xp") or 0),
                     items=tuple(data.get("items") or ()), keys={k: int(v) for k, v in (data.get("keys") or {}).items()},
                     kits=tuple(data.get("kits") or ()))
        reward.validate(catalog)
        return reward

    def validate(self, catalog: Catalog) -> None:
        if not 0 <= self.coins <= MAX_REWARD_COINS or not 0 <= self.xp <= MAX_REWARD_COINS:
            raise GameError("Награда: монеты и опыт — от 0 до 10 млн")
        if len(self.items) > MAX_REWARD_ITEMS or any(i not in catalog.items for i in self.items):
            raise GameError("Награда: неизвестная деталь")
        if any(k not in catalog.cases or not 0 < q <= 100 for k, q in self.keys.items()):
            raise GameError("Награда: неизвестный кейс или неверное количество")
        if any(k not in catalog.kits for k in self.kits):
            raise GameError("Награда: неизвестный комплект")
        if self.is_empty:
            raise GameError("Награда пустая")

    @property
    def is_empty(self) -> bool:
        return not (self.coins or self.xp or self.items or self.keys or self.kits)

    def to_dict(self) -> dict:
        data: dict = {}
        if self.coins:
            data["coins"] = self.coins
        if self.xp:
            data["xp"] = self.xp
        if self.items:
            data["items"] = list(self.items)
        if self.keys:
            data["keys"] = dict(self.keys)
        if self.kits:
            data["kits"] = list(self.kits)
        return data

    def describe(self, catalog: Catalog) -> str:
        parts = []
        if self.coins:
            parts.append(f"{self.coins:,} монет".replace(",", " "))
        if self.xp:
            parts.append(f"{self.xp} опыта")
        parts += [catalog.items[i].name for i in self.items]
        parts += [f"ключ «{catalog.cases[k].name}» ×{q}" for k, q in self.keys.items()]
        parts += [f"комплект «{catalog.kits[k].name}»" for k in self.kits]
        return " · ".join(parts)


async def add_xp(ctx: AppContext, conn: Connection, user_id: int, amount: int) -> dict | None:
    """Начисляет опыт; при новом уровне выдаёт награды уровня и возвращает сведения о повышении."""
    user = await users.get(conn, user_id)
    if user is None or amount <= 0:
        return None
    xp = user.xp + amount
    level = level_for_xp(xp)
    await users.update(conn, user_id, xp=xp, level=level)
    if level <= user.level:
        return None
    coins, keys = 0, {}
    for reached in range(user.level + 1, level + 1):
        level_coins, level_keys = level_reward(reached)
        coins += level_coins
        for case_id, qty in level_keys.items():
            keys[case_id] = keys.get(case_id, 0) + qty
    await users.add_coins(conn, user_id, coins)
    for case_id, qty in keys.items():
        await items.add_keys(conn, user_id, case_id, qty)
    if user.referrer_id:
        await _pay_referrer(ctx, conn, user, level)
    old_rank, new_rank = rank_for_level(user.level), rank_for_level(level)
    return {"from": user.level, "to": level, "coins": coins, "keys": keys,
            "rank": {"title": new_rank.title, "icon": new_rank.icon} if new_rank != old_rank else None}


async def _pay_referrer(ctx: AppContext, conn: Connection, user, level: int) -> None:
    paid = int(user.ref_bonus_paid)
    due = [stage for stage in REF_STAGES[paid:] if level >= stage[0]]
    if not due:
        return
    coins = sum(stage_coins for _, stage_coins in due)
    await users.update(conn, user.id, ref_bonus_paid=paid + len(due))
    await users.add_coins(conn, user.referrer_id, coins)
    if paid == 0:
        await track(conn, user.referrer_id, "invite")
    ctx.notify_after_commit(user.referrer_id, f"🎉 Ваш друг {escape(user.display_name)} достиг {level} уровня — "
                                              f"+{coins} монет!")


async def give_kit(ctx: AppContext, conn: Connection, user_id: int, kit_id: str, source: str) -> list[dict]:
    """Кладёт детали комплекта в инвентарь и сразу собирает из них дрон (если есть место в ангаре)."""
    kit = ctx.catalog.kits.get(kit_id)
    if kit is None:
        raise NotFound("Нет такого комплекта")
    user = await users.get(conn, user_id)
    if user is None:
        raise NotFound("Нет такого игрока")
    kit_video = next((ctx.catalog.items[i] for i in kit.items if ctx.catalog.items[i].slot == "video"), None)
    current_goggles = await items.get_many(conn, user_id, [user.goggles_uid]) if user.goggles_uid else []
    goggles_fit = bool(current_goggles) and (kit_video is None or kit_video.system in ctx.catalog.items[
        current_goggles[0].item_id].systems)
    given, slots = [], {}
    for item_id in kit.items:
        item = ctx.catalog.items[item_id]
        uid = await items.add(conn, user_id, item_id, source)
        given.append(item_view(item, uid))
        if item.slot == "goggles" and not goggles_fit:
            # очки комплекта надеваем, если своих нет или они не видят видеосистему комплекта
            await users.update(conn, user_id, goggles_uid=uid)
        elif item.slot == "radio" and not user.radio_uid:
            await users.update(conn, user_id, radio_uid=uid)
        elif not item.is_gear:
            slots[item.slot] = uid
    if len(await builds.list_for(conn, user_id)) < MAX_BUILDS:
        build_id = await builds.create(conn, user_id, kit.name, slots)
        if not user.active_build_id:
            await users.update(conn, user_id, active_build_id=build_id)
    return given


async def grant(ctx: AppContext, conn: Connection, user_id: int, reward: Reward, source: str) -> dict:
    summary: dict = {"coins": reward.coins, "xp": reward.xp, "items": [], "keys": dict(reward.keys), "kits": []}
    await users.add_coins(conn, user_id, reward.coins)
    for item_id in reward.items:
        uid = await items.add(conn, user_id, item_id, source)
        summary["items"].append(item_view(ctx.catalog.items[item_id], uid))
    for case_id, qty in reward.keys.items():
        await items.add_keys(conn, user_id, case_id, qty)
    for kit_id in reward.kits:
        summary["items"] += await give_kit(ctx, conn, user_id, kit_id, source)
        summary["kits"].append(ctx.catalog.kits[kit_id].name)
    summary["level_up"] = await add_xp(ctx, conn, user_id, reward.xp)
    return summary
