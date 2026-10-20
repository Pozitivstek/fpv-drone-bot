"""Задания, ежедневный бонус и глобальные события (удача ×N, награды за гонки ×N)."""

from __future__ import annotations

from aiosqlite import Connection

from app import clock
from app.context import AppContext
from app.game import daily, tasks
from app.services.errors import GameError, NotFound
from app.services.players_guard import require_active
from app.services.quests import track  # noqa: F401  (progress.track — привычная точка входа)
from app.services.rewards import Reward, grant
from app.store import social, users

EVENT_KEYS = {"luck_event": (1.0, 0.5, 5.0), "race_mult": (1.0, 0.5, 5.0)}


async def events(conn: Connection) -> dict[str, float]:
    result = {}
    for key, (default, low, high) in EVENT_KEYS.items():
        try:
            value = float(await social.get_kv(conn, key, str(default)))
        except ValueError:
            value = default
        result[key] = max(low, min(high, value))
    return result


async def set_event(conn: Connection, key: str, value: float) -> float:
    if key not in EVENT_KEYS:
        raise NotFound("Нет такого события")
    _, low, high = EVENT_KEYS[key]
    clamped = round(max(low, min(high, value)), 2)
    await social.set_kv(conn, key, str(clamped))
    return clamped


async def task_list(ctx: AppContext, user_id: int) -> list[dict]:
    day, week = clock.day_key(), clock.week_key()
    active = tasks.active_tasks(user_id, day, week)
    progress = await social.task_progress(ctx.db.conn, user_id, [day, week])
    result = []
    for period, task in active:
        done, claimed = progress.get((period, task.id), (0, False))
        result.append({"id": task.id, "period": task.period, "title": task.title, "goal": task.goal,
                       "progress": done, "claimed": claimed, "ready": done >= task.goal and not claimed,
                       "coins": task.coins, "xp": task.xp, "keys": task.keys})
    return result


async def claim_task(ctx: AppContext, user_id: int, task_id: str) -> dict:
    day, week = clock.day_key(), clock.week_key()
    match = next(((period, task) for period, task in tasks.active_tasks(user_id, day, week) if task.id == task_id), None)
    if match is None:
        raise NotFound("Такого задания сейчас нет")
    period, task = match
    async with ctx.db.tx() as conn:
        user = await users.get(conn, user_id)
        if user is None:
            raise NotFound("Нет такого игрока")
        require_active(user)
        if not await social.claim_task(conn, user_id, period, task.id, task.goal):
            raise GameError("Задание ещё не выполнено или награда уже получена")
        reward = Reward(coins=task.coins, xp=task.xp, keys=dict(task.keys))
        return await grant(ctx, conn, user_id, reward, f"task:{task.id}")


def daily_state(streak: int, daily_last: str | None) -> dict:
    """Что показать на карточке бонуса: можно ли забрать сейчас и какой день серии следующий."""
    last = clock.parse(daily_last).astimezone(clock.GAME_TZ).date() if daily_last else None
    upcoming = daily.next_streak(last, clock.game_day(), streak)
    claimable = upcoming is not None
    next_streak = upcoming if claimable else streak + 1
    coins, keys = daily.reward_for(next_streak)
    cycle = len(daily.DAILY_REWARDS)
    return {"claimable": claimable, "streak": next_streak - 1, "day": (next_streak - 1) % cycle + 1,
            "coins": coins, "keys": keys, "reset_in": clock.seconds_to_next_day(),
            "week": [{"day": i + 1, "coins": c, "keys": k} for i, (c, k) in enumerate(daily.DAILY_REWARDS)]}


async def claim_daily(ctx: AppContext, user_id: int) -> dict:
    async with ctx.db.tx() as conn:
        user = await users.get(conn, user_id)
        if user is None:
            raise NotFound("Нет такого игрока")
        require_active(user)
        last = clock.parse(user.daily_last).astimezone(clock.GAME_TZ).date() if user.daily_last else None
        streak = daily.next_streak(last, clock.game_day(), user.streak)
        if streak is None:
            raise GameError("Бонус за сегодня уже получен — заходите завтра")
        coins, keys = daily.reward_for(streak)
        await users.update(conn, user_id, streak=streak, daily_last=clock.iso())
        summary = await grant(ctx, conn, user_id, Reward(coins=coins, keys=dict(keys), xp=10), "daily")
        return {**summary, "streak": streak}
