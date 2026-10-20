"""Ошибки сценариев — общие для всего приложения, см. app.errors."""

from __future__ import annotations

from app.errors import Forbidden, GameError, NotFound

__all__ = ["Forbidden", "GameError", "NotFound"]
