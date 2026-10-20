"""Проверка бана — без зависимостей, чтобы её могли звать все сценарии."""

from __future__ import annotations

from app.errors import Forbidden
from app.store.users import User


def require_active(user: User) -> None:
    if user.banned:
        raise Forbidden("Аккаунт заблокирован администратором")
