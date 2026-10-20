"""Засчитывание действий игрока в текущие задания (общая точка для всех сценариев)."""

from __future__ import annotations

from aiosqlite import Connection

from app import clock
from app.game import tasks
from app.store import social


async def track(conn: Connection, user_id: int, event: str, amount: int = 1) -> None:
    """Засчитывает действие во все текущие задания с таким событием."""
    if amount <= 0:
        return
    for period, task in tasks.active_tasks(user_id, clock.day_key(), clock.week_key()):
        if task.event == event:
            await social.add_task_progress(conn, user_id, period, task.id, amount, task.goal)
