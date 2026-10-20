"""Опыт, уровни, ранги пилота и награды за новый уровень."""

from __future__ import annotations

from dataclasses import dataclass

MAX_LEVEL = 60
XP_BASE = 100
XP_POWER = 1.7


@dataclass(frozen=True)
class Rank:
    level: int
    title: str
    icon: str


RANKS = (
    Rank(1, "Симуляторщик", "🎮"),
    Rank(3, "Первый взлёт", "🛫"),
    Rank(5, "Ховер-мастер", "🛸"),
    Rank(8, "Фристайлер", "🌀"),
    Rank(12, "Гонщик", "🏁"),
    Rank(16, "Пилот лиги", "🎖"),
    Rank(20, "Про-пилот", "⚡"),
    Rank(25, "Чемпион", "🏆"),
    Rank(30, "Легенда DRL", "👑"),
)


def xp_for_level(level: int) -> int:
    """Сколько всего опыта нужно, чтобы достичь уровня."""
    return round(XP_BASE * (max(1, level) - 1) ** XP_POWER)


def level_for_xp(xp: int) -> int:
    level = 1
    while level < MAX_LEVEL and xp >= xp_for_level(level + 1):
        level += 1
    return level


def rank_for_level(level: int) -> Rank:
    current = RANKS[0]
    for rank in RANKS:
        if level >= rank.level:
            current = rank
    return current


def rank_index(level: int) -> int:
    return RANKS.index(rank_for_level(level))


def level_reward(level: int) -> tuple[int, dict[str, int]]:
    """Монеты и ключи от кейсов за достижение уровня."""
    keys: dict[str, int] = {}
    if level % 5 == 0:
        keys["freestyle"] = 1
    if level % 10 == 0:
        keys["legend"] = 1
    return 50 * level, keys


def progress(xp: int) -> dict:
    level = level_for_xp(xp)
    start, end = xp_for_level(level), xp_for_level(level + 1)
    span = max(1, end - start)
    rank = rank_for_level(level)
    return {
        "level": level, "xp": xp, "level_xp": xp - start, "level_span": span,
        "pct": 100 if level >= MAX_LEVEL else round((xp - start) / span * 100),
        "rank": {"title": rank.title, "icon": rank.icon, "index": RANKS.index(rank)},
    }
