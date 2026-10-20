"""Время: метки в UTC (ISO), игровые сутки и недели — по Москве."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

GAME_TZ = ZoneInfo("Europe/Moscow")


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime | None = None) -> str:
    return (moment or now()).astimezone(timezone.utc).isoformat(timespec="seconds")


def parse(value: str | None) -> datetime | None:
    if not value:
        return None
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def game_day(moment: datetime | None = None) -> date:
    return (moment or now()).astimezone(GAME_TZ).date()


def day_key(moment: datetime | None = None) -> str:
    return "d:" + game_day(moment).isoformat()


def week_key(moment: datetime | None = None) -> str:
    year, week, _ = game_day(moment).isocalendar()
    return f"w:{year}-W{week:02d}"


def seconds_to_next_day(moment: datetime | None = None) -> int:
    local = (moment or now()).astimezone(GAME_TZ)
    tomorrow = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), GAME_TZ)
    return max(0, int((tomorrow - local).total_seconds()))


def day_start(moment: datetime | None = None) -> datetime:
    """Начало текущих игровых суток (полночь по Москве) в UTC."""
    local = (moment or now()).astimezone(GAME_TZ)
    return datetime.combine(local.date(), datetime.min.time(), GAME_TZ).astimezone(timezone.utc)
