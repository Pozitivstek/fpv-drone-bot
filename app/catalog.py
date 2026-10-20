"""Каталог из data/*.json: детали, кейсы, готовые комплекты и трассы. Загружается один раз при старте."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.game.defs import ALL_SLOTS, CLASSES, GEAR, RARITIES, SYSTEMS, TIER, item_value


class CatalogError(ValueError):
    """Ошибка в файлах данных — ловим на старте, а не посреди игры."""


@dataclass(frozen=True)
class Item:
    id: str
    slot: str
    name: str
    rarity: str
    q: int
    value: int
    cls: tuple[str, ...] = ()
    spec: str = ""
    desc: str = ""
    system: str = ""
    systems: tuple[str, ...] = ()
    lat: int = 0

    @property
    def tier(self) -> int:
        return TIER[self.rarity]

    @property
    def is_gear(self) -> bool:
        return self.slot in GEAR


@dataclass(frozen=True)
class CaseDef:
    id: str
    name: str
    price: int
    weights: dict[str, float]
    color: str = "#00f0ff"
    tagline: str = ""
    slots: tuple[str, ...] = ()
    cls: tuple[str, ...] = ()
    gear: bool = False
    buyable: bool = True
    min_level: int = 1

    def matches(self, item: Item) -> bool:
        if item.rarity not in self.weights:
            return False
        if self.slots:
            return item.slot in self.slots
        if item.is_gear:
            return self.gear
        return not self.cls or bool(set(self.cls) & set(item.cls))


@dataclass(frozen=True)
class Kit:
    id: str
    name: str
    items: tuple[str, ...]
    desc: str = ""


@dataclass(frozen=True)
class Track:
    id: str
    name: str
    theme: str
    seed: int
    gates: int
    spacing: float
    gate_size: float
    wiggle: float
    obstacles: float
    fee: int
    reward: int
    xp: int
    min_level: int = 1
    desc: str = ""

    LEAD_IN = 40.0

    @property
    def length(self) -> float:
        """Путь от старта до финишной арки (м): разгон + промежутки между воротами."""
        return self.LEAD_IN + self.gates * self.spacing


@dataclass
class Catalog:
    items: dict[str, Item]
    cases: dict[str, CaseDef]
    kits: dict[str, Kit]
    tracks: dict[str, Track]
    _pools: dict[str, dict[str, tuple[Item, ...]]] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dir(cls, data_dir: Path) -> "Catalog":
        items = {raw["id"]: _item(raw) for raw in _load(data_dir / "items.json")}
        cases = {raw["id"]: _case(raw) for raw in _load(data_dir / "cases.json")}
        kits = {raw["id"]: Kit(raw["id"], raw["name"], tuple(raw["items"]), raw.get("desc", ""))
                for raw in _load(data_dir / "kits.json")}
        tracks = {raw["id"]: Track(**raw) for raw in _load(data_dir / "tracks.json")}
        catalog = cls(items, cases, kits, tracks)
        catalog.validate()
        return catalog

    def validate(self) -> None:
        for kit in self.kits.values():
            missing = [item_id for item_id in kit.items if item_id not in self.items]
            if missing:
                raise CatalogError(f"комплект {kit.id}: нет деталей {missing}")
        for case in self.cases.values():
            if not any(self.pool(case.id).values()):
                raise CatalogError(f"кейс {case.id}: пустой пул")

    def pool(self, case_id: str) -> dict[str, tuple[Item, ...]]:
        """Детали кейса, сгруппированные по редкости (только редкости с весом)."""
        if case_id not in self._pools:
            case = self.cases[case_id]
            grouped = {rarity: tuple(item for item in self.items.values()
                                     if item.rarity == rarity and case.matches(item))
                       for rarity in RARITIES if rarity in case.weights}
            self._pools[case_id] = {rarity: group for rarity, group in grouped.items() if group}
        return self._pools[case_id]

    def by_rarity(self, rarity: str) -> list[Item]:
        return [item for item in self.items.values() if item.rarity == rarity]


def _load(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"{path.name}: {exc}") from exc
    if not isinstance(data, list):
        raise CatalogError(f"{path.name}: ожидался список")
    ids = [entry.get("id") for entry in data]
    if len(ids) != len(set(ids)):
        raise CatalogError(f"{path.name}: повторяются id")
    return data


def _item(raw: dict) -> Item:
    slot, rarity = raw.get("slot"), raw.get("rarity")
    if slot not in ALL_SLOTS or rarity not in RARITIES:
        raise CatalogError(f"деталь {raw.get('id')}: неверный слот или редкость")
    cls = tuple(raw.get("cls", ()))
    systems = tuple(raw.get("systems", ()))
    system = raw.get("system", "")
    if any(c not in CLASSES for c in cls) or any(s not in SYSTEMS for s in systems) \
            or (system and system not in SYSTEMS):
        raise CatalogError(f"деталь {raw['id']}: неизвестный класс или видеосистема")
    if slot not in GEAR and not cls:
        raise CatalogError(f"деталь {raw['id']}: не указан класс дрона")
    if slot == "video" and not system:
        raise CatalogError(f"деталь {raw['id']}: у видеосистемы нет system")
    if slot == "goggles" and not systems:
        raise CatalogError(f"деталь {raw['id']}: у очков нет systems")
    quality = int(raw["q"])
    return Item(id=raw["id"], slot=slot, name=raw["name"], rarity=rarity, q=quality,
                value=int(raw.get("value") or item_value(rarity, quality)), cls=cls, spec=raw.get("spec", ""),
                desc=raw.get("desc", ""), system=system, systems=systems, lat=int(raw.get("lat", 0)))


def _case(raw: dict) -> CaseDef:
    weights = {rarity: float(weight) for rarity, weight in raw["weights"].items()}
    if any(rarity not in RARITIES for rarity in weights) or any(weight <= 0 for weight in weights.values()):
        raise CatalogError(f"кейс {raw['id']}: неверные веса")
    return CaseDef(id=raw["id"], name=raw["name"], price=int(raw["price"]), weights=weights,
                   color=raw.get("color", "#00f0ff"), tagline=raw.get("tagline", ""),
                   slots=tuple(raw.get("slots", ())), cls=tuple(raw.get("cls", ())), gear=bool(raw.get("gear")),
                   buyable=bool(raw.get("buyable", True)), min_level=int(raw.get("min_level", 1)))
