"""Скользящее окно в памяти: не больше limit событий за window секунд на ключ."""

from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _trim(self, key: str, moment: float) -> deque[float]:
        hits = self._hits[key]
        while hits and moment - hits[0] > self.window:
            hits.popleft()
        return hits

    def allow(self, key: str, now: float | None = None) -> bool:
        """Учитывает попытку, если лимит не исчерпан."""
        moment = now if now is not None else time.monotonic()
        hits = self._trim(key, moment)
        if len(hits) >= self.limit:
            return False
        hits.append(moment)
        return True

    def blocked(self, key: str, now: float | None = None) -> bool:
        """Лимит исчерпан? (без учёта новой попытки)"""
        return len(self._trim(key, now if now is not None else time.monotonic())) >= self.limit

    def hit(self, key: str, now: float | None = None) -> None:
        self._hits[key].append(now if now is not None else time.monotonic())

    def clear(self) -> None:
        self._hits.clear()
