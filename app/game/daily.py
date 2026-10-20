"""Ежедневный бонус: серия входов по дням, награда растёт до 7-го дня и идёт по кругу."""

from __future__ import annotations

from datetime import date, timedelta

DAILY_REWARDS: tuple[tuple[int, dict[str, int]], ...] = (
    (100, {}),
    (150, {}),
    (200, {"daily": 1}),
    (250, {}),
    (300, {}),
    (400, {"daily": 1}),
    (600, {"freestyle": 1}),
)


def next_streak(last_day: date | None, today: date, streak: int) -> int | None:
    """Новая длина серии или None, если бонус за сегодня уже получен."""
    if last_day == today:
        return None
    if last_day == today - timedelta(days=1):
        return streak + 1
    return 1


def reward_for(streak: int) -> tuple[int, dict[str, int]]:
    return DAILY_REWARDS[(max(1, streak) - 1) % len(DAILY_REWARDS)]
