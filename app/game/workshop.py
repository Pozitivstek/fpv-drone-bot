"""Мастерская: апгрейд (рискнуть деталями ради дорогой) и контракт (5 одной редкости → 1 редкостью выше)."""

from __future__ import annotations

from app.errors import GameError
from app.game.defs import next_rarity
from app.game.drops import clamp_luck

UPGRADE_EDGE = 0.9
UPGRADE_MAX_CHANCE = 0.8
UPGRADE_MIN_CHANCE = 0.02
UPGRADE_MAX_INPUTS = 6
UPGRADE_LUCK_EXPONENT = 0.35
CONTRACT_SIZE = 5


class WorkshopError(GameError):
    """Операцию в мастерской нельзя выполнить — текст для игрока."""


def upgrade_chance(stake_value: int, target_value: int, luck: float = 1.0) -> float:
    if stake_value <= 0:
        raise WorkshopError("Положите хотя бы одну деталь")
    if target_value <= stake_value:
        raise WorkshopError("Цель должна быть дороже ставки — иначе это не апгрейд")
    chance = stake_value / target_value * UPGRADE_EDGE * clamp_luck(luck) ** UPGRADE_LUCK_EXPONENT
    if chance < UPGRADE_MIN_CHANCE:
        raise WorkshopError("Шанс меньше 2 % — добавьте деталей или выберите цель скромнее")
    return round(min(UPGRADE_MAX_CHANCE, chance), 4)


def contract_rarity(rarities: list[str]) -> str:
    if len(rarities) != CONTRACT_SIZE:
        raise WorkshopError(f"Для контракта нужно ровно {CONTRACT_SIZE} деталей")
    if len(set(rarities)) != 1:
        raise WorkshopError("Все детали контракта должны быть одной редкости")
    target = next_rarity(rarities[0])
    if target is None:
        raise WorkshopError("Мифические детали некуда улучшать")
    return target
