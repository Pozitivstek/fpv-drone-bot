"""Сборка дрона: совместимость деталей и характеристики полёта для мини-игры.

Качество детали (q, 0–100) с износом падает: при износе 100 % деталь сломана и дрон не взлетит.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.catalog import Item
from app.game.defs import CLASS_TITLES, SLOT_TITLES, SLOTS, SYSTEM_TITLES

BROKEN_WEAR = 100
WEAR_QUALITY_LOSS = 250  # при износе w качество умножается на (1 - w / 250)


@dataclass(frozen=True)
class ClassProfile:
    speed: float      # базовая крейсерская скорость, м/с
    lateral: float    # базовая боковая скорость, м/с
    agility: float    # множитель отклика на стики
    crashes: int      # сколько ударов выдержит без поломки
    flight: float     # базовое время полёта, с
    hitbox: float     # радиус дрона, м


PROFILES = {
    "whoop": ClassProfile(speed=15, lateral=8.5, agility=1.15, crashes=4, flight=70, hitbox=0.16),
    "cine": ClassProfile(speed=21, lateral=8.0, agility=0.95, crashes=4, flight=80, hitbox=0.26),
    "five": ClassProfile(speed=34, lateral=9.5, agility=1.05, crashes=2, flight=75, hitbox=0.30),
    "seven": ClassProfile(speed=32, lateral=7.0, agility=0.75, crashes=2, flight=120, hitbox=0.38),
}
CLASS_RATING = {"whoop": 0.8, "cine": 0.9, "five": 1.0, "seven": 0.95}


@dataclass(frozen=True)
class Part:
    item: Item
    wear: int = 0
    uid: int = 0

    @property
    def broken(self) -> bool:
        return self.wear >= BROKEN_WEAR

    @property
    def quality(self) -> float:
        return self.item.q * (1 - min(self.wear, BROKEN_WEAR) / WEAR_QUALITY_LOSS)


@dataclass(frozen=True)
class Flight:
    """Параметры для мини-игры: их же сервер использует при проверке результата."""
    cls: str
    top_speed: float
    lateral: float
    response: float
    max_crashes: int
    flight_time: float
    clarity: float
    noise: float
    view: float
    latency: int
    smooth: float
    hitbox: float
    system: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BuildReport:
    cls: str | None
    issues: tuple[str, ...]
    flight: Flight | None
    stats: dict
    rating: int

    @property
    def ready(self) -> bool:
        return not self.issues and self.flight is not None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def check(parts: dict[str, Part | None], goggles: Part | None, radio: Part | None) -> tuple[str | None, list[str]]:
    """Класс дрона (по раме) и список проблем, мешающих взлететь."""
    issues: list[str] = []
    frame = parts.get("frame")
    cls = frame.item.cls[0] if frame else None
    for slot in SLOTS:
        part = parts.get(slot)
        if part is None:
            issues.append(f"Не установлено: {SLOT_TITLES[slot].lower()}")
            continue
        if cls and slot != "frame" and cls not in part.item.cls:
            issues.append(f"{part.item.name} не подходит к классу «{CLASS_TITLES[cls]}»")
        if part.broken:
            issues.append(f"{part.item.name} сломан(а) — нужен ремонт")
    video = parts.get("video")
    if goggles is None:
        issues.append("Нет очков — нечем смотреть картинку")
    elif goggles.broken:
        issues.append(f"{goggles.item.name} сломаны — нужен ремонт")
    elif video and video.item.system not in goggles.item.systems:
        issues.append(f"{goggles.item.name} не принимают {SYSTEM_TITLES[video.item.system]}")
    if radio is None:
        issues.append("Нет пульта — нечем управлять")
    elif radio.broken:
        issues.append(f"{radio.item.name} сломан — нужен ремонт")
    return cls, issues


def evaluate(parts: dict[str, Part | None], goggles: Part | None, radio: Part | None) -> BuildReport:
    cls, issues = check(parts, goggles, radio)
    flight = _flight(cls, parts, goggles, radio) if cls and all(parts.get(slot) for slot in SLOTS) else None
    stats = _stats(flight) if flight else {}
    rating = _rating(cls, parts, goggles, radio)
    return BuildReport(cls=cls, issues=tuple(issues), flight=flight, stats=stats, rating=rating)


def _q(part: Part | None) -> float:
    return part.quality if part else 0.0


def _flight(cls: str, parts: dict[str, Part | None], goggles: Part | None, radio: Part | None) -> Flight:
    profile = PROFILES[cls]
    motors, battery, frame = _q(parts["motors"]), _q(parts["battery"]), _q(parts["frame"])
    props, stack, video = _q(parts["props"]), _q(parts["stack"]), _q(parts["video"])
    handling = (frame * 0.3 + props * 0.35 + motors * 0.2 + stack * 0.15) / 100
    video_item = parts["video"].item
    clarity = (video * 0.6 + _q(goggles) * 0.4) / 100
    analog = video_item.system == "analog"
    radio_lat = radio.item.lat if radio else 20
    return Flight(
        cls=cls,
        top_speed=round(profile.speed * (0.7 + 0.45 * (0.6 * motors + 0.4 * battery) / 100), 2),
        lateral=round(profile.lateral * (0.75 + 0.4 * handling), 2),
        response=round(profile.agility * (2.6 + 4.0 * handling), 2),
        max_crashes=profile.crashes + int(frame // 40),
        flight_time=round(profile.flight * (0.75 + 0.5 * battery / 100), 1),
        clarity=round(clarity, 3),
        noise=round(0.08 + 0.42 * (1 - clarity), 3) if analog else 0.0,
        view=round(70 + 130 * clarity, 1),
        latency=int(video_item.lat + radio_lat),
        smooth=round(_clamp((_q(radio) * 0.6 + stack * 0.4) / 100, 0.0, 1.0), 3),
        hitbox=profile.hitbox,
        system=video_item.system,
    )


def _stats(flight: Flight) -> dict:
    """Человекочитаемые характеристики для карточки сборки (шкалы 0–100)."""
    return {
        "speed_kmh": round(flight.top_speed * 3.6),
        "speed": round(_clamp(flight.top_speed / 0.5, 0, 100)),
        "handling": round(_clamp((flight.response - 2) / 0.07, 0, 100)),
        "durability": round(_clamp(flight.max_crashes * 16, 0, 100)),
        "flight_time": round(flight.flight_time),
        "video": round(flight.clarity * 100),
        "latency": flight.latency,
        "control": round(flight.smooth * 100),
    }


def _rating(cls: str | None, parts: dict[str, Part | None], goggles: Part | None, radio: Part | None) -> int:
    """Рейтинг сборки (0–1000) для профиля и таблиц лидеров."""
    qualities = [_q(parts.get(slot)) for slot in SLOTS] + [_q(goggles), _q(radio)]
    return round(sum(qualities) / len(qualities) * 10 * CLASS_RATING.get(cls or "", 0.8))
