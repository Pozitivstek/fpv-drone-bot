"""Гонки: проверка присланного результата, медали, награды и износ деталей.

Мини-игра идёт в браузере, поэтому сервер не верит цифрам на слово. Он строит ту же трассу по seed
(app/game/track.py) и проверяет запись полёта: время идёт вперёд и совпадает с заявленным, дрон не летит
быстрее, чем позволяет сборка, заявленные ворота действительно пролетены, а «пробитые» препятствия
засчитаны как краши. Плюс физические пределы: не быстрее возможного, не дольше батареи и реального времени.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.catalog import Track
from app.game.builds import Flight
from app.game.track import Layout, build_layout

BOOST = 1.3
MISS_PENALTY_MS = 3000
MIN_TIME_SLACK = 0.93
CLOCK_SLACK_MS = 2500
BATTERY_SLACK_MS = 1500
MAX_PATH_POINTS = 2400
PATH_BOUND = 60.0
PATH_STEP_MS = 100
MIN_SAMPLE_SHARE = 0.6        # запись не реже, чем раз в ~170 мс
PATH_TIME_SLACK_MS = 1500
SPEED_SLACK = 1.15
Z_SLACK = 0.6                 # округление z в записи и шаг кадра
GATE_TOLERANCE = 0.7          # погрешность интерполяции между точками записи
OBSTACLE_CORE = 0.5           # «явное» попадание: ближе половины радиуса стойки
OBSTACLE_TOP_MARGIN = 1.0
REACH_SLACK_S = 0.3           # последняя точка может отставать от ворот/финиша на долю секунды

MEDAL_RATIO = (("gold", 1.12), ("silver", 1.3), ("bronze", 1.6))
MEDAL_REWARD = {"gold": 1.0, "silver": 0.7, "bronze": 0.5, "": 0.25}
DNF_XP_SHARE = 0.3
GOLD_XP_BONUS = 0.5

WEAR_BASE = {"props": 4, "battery": 3, "motors": 1, "frame": 1}
WEAR_PER_CRASH = {"frame": 9, "props": 14, "motors": 4, "video": 3, "stack": 1}
REPAIR_RATE = 0.35


class RaceRejected(ValueError):
    """Результат не прошёл проверку."""


@dataclass(frozen=True)
class RaceClaim:
    finished: bool
    time_ms: int
    gates: int
    missed: int
    crashes: int
    path: tuple[tuple[float, ...], ...] = ()  # точки (t мс, x, y, z) для «призрака» и проверки

    @property
    def reached(self) -> int:
        return self.gates + self.missed


def ideal_ms(track: Track, flight: Flight) -> float:
    return track.length / flight.top_speed * 1000


def min_possible_ms(track: Track, flight: Flight, distance: float | None = None) -> float:
    return (track.length if distance is None else distance) / (flight.top_speed * BOOST) * 1000 * MIN_TIME_SLACK


def _interpolate(path: tuple[tuple[float, ...], ...], z: float) -> tuple[float, float] | None:
    """Положение (x, y) дрона в момент, когда он пересёк плоскость z."""
    for before, after in zip(path, path[1:]):
        if before[3] <= z <= after[3]:
            span = after[3] - before[3]
            k = 0.0 if span <= 0 else (z - before[3]) / span
            return before[1] + (after[1] - before[1]) * k, before[2] + (after[2] - before[2]) * k
    return None


def count_passes(layout: Layout, path: tuple[tuple[float, ...], ...], hitbox: float) -> int:
    passes = 0
    for gate in layout.gates:
        point = _interpolate(path, gate.z)
        if point is None:
            continue
        limit = gate.size - hitbox + GATE_TOLERANCE
        if abs(point[0] - gate.x) < limit and abs(point[1] - gate.y) < limit:
            passes += 1
    return passes


def obstacle_hits(layout: Layout, path: tuple[tuple[float, ...], ...]) -> int:
    hits = 0
    for obstacle in layout.obstacles:
        point = _interpolate(path, obstacle.z)
        if point and abs(point[0] - obstacle.x) < obstacle.r * OBSTACLE_CORE \
                and point[1] < obstacle.h - OBSTACLE_TOP_MARGIN:
            hits += 1
    return hits


def _check_path_shape(flight: Flight, claim: RaceClaim) -> None:
    path = claim.path
    if any(not math.isfinite(value) for point in path for value in point):
        raise RaceRejected("битая запись полёта")
    if any(abs(value) > PATH_BOUND for point in path for value in point[1:3]):
        raise RaceRejected("запись полёта вне трассы")
    if abs(path[-1][0] - claim.time_ms) > max(PATH_TIME_SLACK_MS, claim.time_ms * 0.05):
        raise RaceRejected("запись полёта не совпадает со временем")
    if len(path) < claim.time_ms / PATH_STEP_MS * MIN_SAMPLE_SHARE:
        raise RaceRejected("слишком редкая запись полёта")
    max_speed = flight.top_speed * BOOST * SPEED_SLACK
    if path[0][3] > max_speed * max(0.0, path[0][0]) / 1000 + Z_SLACK:
        raise RaceRejected("быстрее, чем летает сборка")
    for before, after in zip(path, path[1:]):
        dt = (after[0] - before[0]) / 1000
        if dt < 0 or after[3] < before[3] - Z_SLACK:
            raise RaceRejected("время или путь в записи идут назад")
        if after[3] - before[3] > max_speed * dt + Z_SLACK:
            raise RaceRejected("быстрее, чем летает сборка")


def _check_path(track: Track, layout: Layout, flight: Flight, claim: RaceClaim) -> None:
    if not claim.path:
        if claim.reached or claim.finished:
            raise RaceRejected("нет записи полёта")
        return
    _check_path_shape(flight, claim)
    last_z = claim.path[-1][3]
    lag = flight.top_speed * BOOST * REACH_SLACK_S
    if claim.reached and last_z < layout.gates[claim.reached - 1].z - lag:
        raise RaceRejected("до этих ворот дрон не долетел")
    if claim.finished and last_z < track.length - lag:
        raise RaceRejected("финиш не достигнут")
    if claim.gates > count_passes(layout, claim.path, flight.hitbox):
        raise RaceRejected("заявленные ворота не пройдены")
    if claim.crashes < obstacle_hits(layout, claim.path):
        raise RaceRejected("краши о препятствия не засчитаны")


def validate(track: Track, flight: Flight, claim: RaceClaim, elapsed_ms: float) -> None:
    if min(claim.time_ms, claim.gates, claim.missed, claim.crashes) < 0:
        raise RaceRejected("отрицательные значения")
    if claim.reached > track.gates:
        raise RaceRejected("ворот больше, чем на трассе")
    if claim.time_ms > elapsed_ms + CLOCK_SLACK_MS:
        raise RaceRejected("время больше, чем прошло на самом деле")
    if len(claim.path) > MAX_PATH_POINTS:
        raise RaceRejected("слишком длинная запись полёта")
    layout = build_layout(track)
    reached_z = layout.gates[claim.reached - 1].z if claim.reached else 0.0
    if claim.time_ms < min_possible_ms(track, flight, reached_z):
        raise RaceRejected("быстрее, чем позволяет сборка")
    if claim.finished:
        if claim.reached != track.gates:
            raise RaceRejected("финиш без прохождения всех ворот")
        if claim.crashes > flight.max_crashes:
            raise RaceRejected("дрон не мог долететь с такими повреждениями")
        if claim.time_ms > flight.flight_time * 1000 + BATTERY_SLACK_MS:
            raise RaceRejected("аккумулятор столько не держит")
        if claim.time_ms < min_possible_ms(track, flight):
            raise RaceRejected("быстрее, чем позволяет сборка")
    _check_path(track, layout, flight, claim)


def total_ms(claim: RaceClaim) -> int:
    return claim.time_ms + claim.missed * MISS_PENALTY_MS


def medal_for(track: Track, flight: Flight, claim: RaceClaim) -> str:
    if not claim.finished:
        return ""
    ratio = total_ms(claim) / ideal_ms(track, flight)
    return next((medal for medal, limit in MEDAL_RATIO if ratio <= limit), "")


def rewards(track: Track, medal: str, finished: bool, race_mult: float = 1.0, progress: float = 1.0) -> tuple[int, int]:
    """Монеты и опыт за заезд. Сход даёт только часть опыта — пропорционально пройденным воротам."""
    if not finished:
        return 0, round(track.xp * DNF_XP_SHARE * max(0.0, min(1.0, progress)))
    coins = round(track.reward * MEDAL_REWARD[medal] * race_mult)
    xp = round(track.xp * (1 + (GOLD_XP_BONUS if medal == "gold" else 0)))
    return coins, xp


def wear_after(crashes: int, frame_quality: float) -> dict[str, int]:
    """Сколько процентов износа получит каждая деталь. Хорошая рама бережёт остальное."""
    protection = 1 - frame_quality / 250
    slots = set(WEAR_BASE) | set(WEAR_PER_CRASH)
    return {slot: round(WEAR_BASE.get(slot, 0) + crashes * WEAR_PER_CRASH.get(slot, 0) * protection)
            for slot in sorted(slots)}


def repair_cost(value: int, wear: int) -> int:
    return math.ceil(value * wear / 100 * REPAIR_RATE) if wear > 0 else 0
