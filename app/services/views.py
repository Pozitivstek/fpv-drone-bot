"""Сериализация деталей и каталога для мини-приложения."""

from __future__ import annotations

from app.catalog import Catalog, Item
from app.game.builds import PROFILES
from app.game.defs import (
    CLASS_TITLES, RARITIES, RARITY_TITLES, SELL_RATIO, SHOP_MARKUP, SHOP_MAX_TIER, SLOT_TITLES, SYSTEM_TITLES,
)
from app.game.progression import RANKS
from app.game.racing import BOOST, MISS_PENALTY_MS
from app.game.racing import repair_cost as _repair_cost
from app.game.workshop import (
    CONTRACT_SIZE, UPGRADE_EDGE, UPGRADE_LUCK_EXPONENT, UPGRADE_MAX_CHANCE, UPGRADE_MAX_INPUTS, UPGRADE_MIN_CHANCE,
)

SELL_WEAR_FACTOR = 200  # при износе 100 % деталь продаётся за половину обычной цены


def sell_price(item: Item, wear: int = 0) -> int:
    return max(1, round(item.value * SELL_RATIO * (1 - wear / SELL_WEAR_FACTOR)))


def shop_price(item: Item) -> int | None:
    return round(item.value * SHOP_MARKUP / 5) * 5 if item.tier <= SHOP_MAX_TIER else None


def item_view(item: Item, uid: int | None = None, wear: int = 0, locked: bool = False) -> dict:
    view: dict = {"id": item.id, "slot": item.slot, "name": item.name, "rarity": item.rarity, "q": item.q,
                  "value": item.value, "spec": item.spec}
    if item.desc:
        view["desc"] = item.desc
    if item.cls:
        view["cls"] = list(item.cls)
    if item.system:
        view["system"] = item.system
    if item.systems:
        view["systems"] = list(item.systems)
    if item.lat:
        view["lat"] = item.lat
    if uid is not None:
        view.update(uid=uid, wear=wear, locked=locked, sell=sell_price(item, wear),
                    repair=_repair_cost(item.value, wear))
    return view


def catalog_payload(catalog: Catalog) -> dict:
    """Всё статичное разом: мини-приложение кэширует это на время сессии."""
    return {
        "items": [item_view(item) for item in catalog.items.values()],
        "cases": {case.id: {"name": case.name, "color": case.color, "price": case.price}
                  for case in catalog.cases.values()},
        "kits": [{"id": kit.id, "name": kit.name, "desc": kit.desc, "items": list(kit.items)}
                 for kit in catalog.kits.values()],
        "tracks": [{"id": t.id, "name": t.name, "theme": t.theme, "desc": t.desc, "seed": t.seed, "gates": t.gates,
                    "spacing": t.spacing, "gate_size": t.gate_size, "wiggle": t.wiggle, "obstacles": t.obstacles,
                    "lead_in": t.LEAD_IN, "length": t.length, "fee": t.fee, "reward": t.reward, "xp": t.xp,
                    "min_level": t.min_level} for t in catalog.tracks.values()],
        "ranks": [{"level": r.level, "title": r.title, "icon": r.icon} for r in RANKS],
        "rarities": [{"id": r, "title": RARITY_TITLES[r]} for r in RARITIES],
        "slots": SLOT_TITLES, "classes": CLASS_TITLES, "systems": SYSTEM_TITLES,
        "class_hitbox": {cls: profile.hitbox for cls, profile in PROFILES.items()},
        "rules": {
            "upgrade_edge": UPGRADE_EDGE, "upgrade_max": UPGRADE_MAX_CHANCE, "upgrade_min": UPGRADE_MIN_CHANCE,
            "upgrade_luck_exp": UPGRADE_LUCK_EXPONENT, "upgrade_max_inputs": UPGRADE_MAX_INPUTS,
            "contract_size": CONTRACT_SIZE, "boost": BOOST, "miss_penalty_ms": MISS_PENALTY_MS,
        },
    }
