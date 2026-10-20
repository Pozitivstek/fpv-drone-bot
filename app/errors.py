"""Ошибки, текст которых показывается игроку как есть (API отвечает 400/403/404)."""

from __future__ import annotations


class GameError(ValueError):
    """Действие нельзя выполнить (не хватает монет, деталь занята и т. п.)."""


class NotFound(GameError):
    """Нет такого предмета, кейса, трассы или игрока."""


class Forbidden(GameError):
    """Нет прав (бан или не админ)."""
