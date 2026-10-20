"""Ежедневные и недельные задания. Набор дневных заданий у каждого игрока свой, но стабильный в течение суток."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

DAILY_COUNT = 4


@dataclass(frozen=True)
class TaskDef:
    id: str
    period: str
    event: str
    goal: int
    title: str
    coins: int
    xp: int
    keys: dict[str, int] = field(default_factory=dict)


DAILY_POOL = (
    TaskDef("d_cases", "daily", "case_open", 3, "Открой 3 кейса", 150, 30),
    TaskDef("d_races", "daily", "race_finish", 2, "Финишируй в 2 гонках", 200, 40),
    TaskDef("d_gates", "daily", "gates", 40, "Пролети 40 ворот", 200, 40),
    TaskDef("d_medal", "daily", "medal", 1, "Возьми любую медаль", 250, 50),
    TaskDef("d_workshop", "daily", "workshop", 1, "Сделай апгрейд или контракт", 150, 30),
    TaskDef("d_repair", "daily", "repair", 1, "Почини дрон после краша", 100, 20),
    TaskDef("d_sell", "daily", "sell", 3, "Продай 3 детали", 100, 20),
)

WEEKLY = (
    TaskDef("w_cases", "weekly", "case_open", 25, "Открой 25 кейсов", 1500, 200, {"daily": 2}),
    TaskDef("w_races", "weekly", "race_finish", 15, "Финишируй в 15 гонках", 2000, 250),
    TaskDef("w_gold", "weekly", "gold", 5, "Возьми 5 золотых медалей", 2500, 300, {"racing": 1}),
    TaskDef("w_invite", "weekly", "invite", 1, "Пригласи друга в игру", 1000, 150),
)

BY_ID = {task.id: task for task in DAILY_POOL + WEEKLY}


def daily_tasks(user_id: int, day_key: str) -> list[TaskDef]:
    seed = int(hashlib.sha256(f"{user_id}:{day_key}".encode()).hexdigest()[:12], 16)
    return random.Random(seed).sample(list(DAILY_POOL), DAILY_COUNT)


def active_tasks(user_id: int, day_key: str, week_key: str) -> list[tuple[str, TaskDef]]:
    """Пары (ключ периода, задание) на текущие сутки и неделю."""
    return [(day_key, task) for task in daily_tasks(user_id, day_key)] + [(week_key, task) for task in WEEKLY]
