"""Раскладка трассы по seed — побитовая копия webapp/js/game/track.js.

Сервер строит те же ворота и препятствия, что и мини-игра, и по присланной траектории сам
проверяет, через какие ворота дрон действительно пролетел.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from app.catalog import Track

MASK = 0xFFFFFFFF
BASE_HEIGHT = 2.6
MIN_HEIGHT = 1.4
MAX_HEIGHT = 6.0


@dataclass(frozen=True)
class Gate:
    z: float
    x: float
    y: float
    size: float


@dataclass(frozen=True)
class Obstacle:
    z: float
    x: float
    r: float
    h: float


@dataclass(frozen=True)
class Layout:
    gates: tuple[Gate, ...]
    obstacles: tuple[Obstacle, ...]


def mulberry32(seed: int) -> Callable[[], float]:
    """Тот же генератор, что в JS: 32-битная арифметика с переполнением."""
    state = seed & MASK

    def imul(a: int, b: int) -> int:
        return (a * b) & MASK

    def rand() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & MASK
        t = state
        t = imul(t ^ (t >> 15), t | 1)
        t ^= (t + imul(t ^ (t >> 7), t | 61)) & MASK
        return ((t ^ (t >> 14)) & MASK) / 4294967296

    return rand


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@lru_cache(maxsize=64)
def build_layout(track: Track) -> Layout:
    rand = mulberry32(track.seed)
    bound = 3 + track.wiggle
    gates: list[Gate] = []
    x = 0.0
    for index in range(track.gates):
        x = _clamp(x + (rand() * 2 - 1) * track.wiggle, -bound, bound)
        y = _clamp(BASE_HEIGHT + (rand() * 2 - 1) * track.wiggle * 0.45, MIN_HEIGHT, MAX_HEIGHT)
        gates.append(Gate(z=track.LEAD_IN + (index + 0.5) * track.spacing, x=x, y=y, size=track.gate_size))
    obstacles: list[Obstacle] = []
    for index, gate in enumerate(gates):
        if rand() >= track.obstacles:
            continue
        previous_z, previous_x = (gates[index - 1].z, gates[index - 1].x) if index else (track.LEAD_IN * 0.5, 0.0)
        t = 0.35 + rand() * 0.3
        side = -1 if rand() < 0.5 else 1
        offset = gate.size * 0.6 + 0.8 + rand() * 2.5
        r = 0.35 + rand() * 0.45
        h = 5 + rand() * 9
        obstacles.append(Obstacle(z=previous_z + (gate.z - previous_z) * t,
                                  x=previous_x + (gate.x - previous_x) * t + side * offset, r=r, h=h))
    return Layout(gates=tuple(gates), obstacles=tuple(obstacles))
