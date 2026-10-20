"""Справочники игры: редкости, слоты сборки, классы дронов и видеосистемы."""

from __future__ import annotations

RARITIES = ("common", "uncommon", "rare", "epic", "legendary", "mythic")
TIER = {rarity: index for index, rarity in enumerate(RARITIES)}
RARITY_TITLES = {
    "common": "Обычная", "uncommon": "Необычная", "rare": "Редкая",
    "epic": "Эпическая", "legendary": "Легендарная", "mythic": "Мифическая",
}
BASE_VALUE = {"common": 60, "uncommon": 180, "rare": 550, "epic": 1600, "legendary": 5000, "mythic": 18000}
FEED_MIN_TIER = TIER["rare"]

SLOTS = ("frame", "motors", "stack", "video", "props", "battery")
GEAR = ("goggles", "radio")
ALL_SLOTS = SLOTS + GEAR
SLOT_TITLES = {
    "frame": "Рама", "motors": "Моторы", "stack": "Полётный стек", "video": "Видеосистема",
    "props": "Пропеллеры", "battery": "Аккумулятор", "goggles": "Очки", "radio": "Пульт",
}

CLASSES = ("whoop", "cine", "five", "seven")
CLASS_TITLES = {"whoop": "Тинивуп", "cine": "Синевуп", "five": "Фристайл 5\"", "seven": "Лонг-рейндж 7\""}

SYSTEMS = ("analog", "hdzero", "walksnail", "dji")
SYSTEM_TITLES = {"analog": "Аналог", "hdzero": "HDZero", "walksnail": "Walksnail", "dji": "DJI"}

MAX_BUILDS = 6
SELL_RATIO = 0.75
SHOP_MARKUP = 1.4
SHOP_MAX_TIER = TIER["uncommon"]


def item_value(rarity: str, quality: int) -> int:
    """Цена детали в монетах: база редкости, слегка растущая с качеством; кратна 5."""
    raw = BASE_VALUE[rarity] * (0.8 + 0.6 * quality / 100)
    return max(5, int(round(raw / 5)) * 5)


def next_rarity(rarity: str) -> str | None:
    tier = TIER[rarity] + 1
    return RARITIES[tier] if tier < len(RARITIES) else None
