"""Шансы выпадения из кейсов. Удача игрока смещает веса в сторону редких деталей."""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.catalog import CaseDef, Item
from app.game.defs import TIER

LUCK_EXPONENT = 0.6
MIN_LUCK, MAX_LUCK = 0.25, 10.0


def clamp_luck(luck: float) -> float:
    return max(MIN_LUCK, min(MAX_LUCK, luck))


def luck_factor(luck: float, tier: int) -> float:
    """Удача 2.0 даёт мифике (tier 5) множитель 2^3 = 8, обычным деталям — 1."""
    return clamp_luck(luck) ** (tier * LUCK_EXPONENT)


@dataclass(frozen=True)
class Odds:
    item: Item
    chance: float


def rarity_odds(case: CaseDef, pool: dict[str, tuple[Item, ...]], luck: float) -> dict[str, float]:
    weights = {rarity: case.weights[rarity] * luck_factor(luck, TIER[rarity]) for rarity in pool}
    total = sum(weights.values())
    return {rarity: weight / total for rarity, weight in weights.items()}


def case_odds(case: CaseDef, pool: dict[str, tuple[Item, ...]], luck: float) -> list[Odds]:
    shares = rarity_odds(case, pool, luck)
    return [Odds(item, shares[rarity] / len(items)) for rarity, items in pool.items() for item in items]


def roll(odds: list[Odds], rng: random.Random) -> Item:
    point = rng.random()
    cumulative = 0.0
    for entry in odds:
        cumulative += entry.chance
        if point < cumulative:
            return entry.item
    return odds[-1].item


def expected_value(odds: list[Odds]) -> float:
    return sum(entry.item.value * entry.chance for entry in odds)
