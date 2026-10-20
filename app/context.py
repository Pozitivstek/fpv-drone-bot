"""Общий контекст приложения: настройки, база, каталог, генератор случайностей и связь с ботом."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from app.catalog import Catalog
from app.config import Settings
from app.db import Database

# (chat_id, текст, подпись кнопки мини-приложения или None) → отправка сообщения ботом
Notifier = Callable[[int, str, str | None], Awaitable[None]]


@dataclass
class AppContext:
    settings: Settings
    db: Database
    catalog: Catalog
    rng: random.Random = field(default_factory=random.SystemRandom)
    notifier: Notifier | None = None
    broadcast_state: dict = field(default_factory=dict)

    def notify_after_commit(self, chat_id: int, text: str, button: str | None = "Открыть игру") -> None:
        """Отправит сообщение игроку, когда текущая транзакция успешно завершится."""
        notifier = self.notifier
        if notifier is None:
            return

        async def send() -> None:
            await notifier(chat_id, text, button)

        self.db.on_commit(send)
