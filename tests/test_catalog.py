"""Каталог: данные валидны, комплекты собираются, экономика кейсов сбалансирована."""

from __future__ import annotations

import json

import pytest

from app.catalog import Catalog, CatalogError
from app.game.builds import Part, evaluate
from app.game.defs import ALL_SLOTS, BASE_VALUE, RARITIES, item_value, next_rarity
from app.game.drops import case_odds, expected_value

EV_MIN, EV_MAX = 0.75, 0.9


def test_catalog_has_items_for_every_slot_and_rarity(catalog):
    assert len(catalog.items) >= 120
    assert {item.slot for item in catalog.items.values()} == set(ALL_SLOTS)
    assert {item.rarity for item in catalog.items.values()} == set(RARITIES)


@pytest.mark.parametrize("kit_id", ["starter", "meteor75_hd", "cine_dji", "freestyle_hdz", "racer_analog",
                                    "lr_walksnail", "racerx"])
def test_every_kit_is_a_flyable_drone(catalog, kit_id):
    parts = [catalog.items[item_id] for item_id in catalog.kits[kit_id].items]
    slots = {item.slot: Part(item) for item in parts if not item.is_gear}
    gear = {item.slot: Part(item) for item in parts if item.is_gear}
    report = evaluate(slots, gear.get("goggles"), gear.get("radio"))
    assert report.ready, report.issues


def test_buyable_cases_return_about_eighty_percent_of_price(catalog):
    for case in catalog.cases.values():
        if not case.buyable:
            continue
        ratio = expected_value(case_odds(case, catalog.pool(case.id), 1.0)) / case.price
        assert EV_MIN <= ratio <= EV_MAX, (case.id, ratio)


def test_case_pool_respects_filters(catalog):
    assert all(item.slot in {"video", "goggles"} for group in catalog.pool("video").values() for item in group)
    whoop = [item for group in catalog.pool("whoop").values() for item in group]
    assert whoop and all("whoop" in item.cls for item in whoop)
    assert "common" not in catalog.pool("racing")


def test_item_value_grows_with_rarity_and_quality():
    assert item_value("common", 10) < item_value("common", 90) < item_value("uncommon", 10)
    assert item_value("mythic", 100) == round(BASE_VALUE["mythic"] * 1.4 / 5) * 5
    assert next_rarity("epic") == "legendary" and next_rarity("mythic") is None


def _write(tmp_path, items, cases=None, kits=None, tracks=None):
    for name, data in (("items", items), ("cases", cases or []), ("kits", kits or []), ("tracks", tracks or [])):
        (tmp_path / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")


GOOD_ITEM = {"id": "a", "slot": "frame", "name": "A", "rarity": "common", "q": 10, "cls": ["five"]}


@pytest.mark.parametrize("items, message", [
    ([GOOD_ITEM, GOOD_ITEM], "повторяются"),
    ([{**GOOD_ITEM, "slot": "wing"}], "слот"),
    ([{**GOOD_ITEM, "cls": []}], "класс"),
    ([{**GOOD_ITEM, "cls": ["huge"]}], "неизвестный"),
    ([{**GOOD_ITEM, "slot": "video"}], "system"),
    ([{**GOOD_ITEM, "slot": "goggles", "cls": []}], "systems"),
])
def test_bad_items_are_rejected(tmp_path, items, message):
    _write(tmp_path, items)
    with pytest.raises(CatalogError, match=message):
        Catalog.from_dir(tmp_path)


def test_bad_cases_and_kits_are_rejected(tmp_path):
    _write(tmp_path, [GOOD_ITEM], kits=[{"id": "k", "name": "K", "items": ["missing"]}])
    with pytest.raises(CatalogError, match="нет деталей"):
        Catalog.from_dir(tmp_path)
    _write(tmp_path, [GOOD_ITEM], cases=[{"id": "c", "name": "C", "price": 1, "weights": {"epic": 1}}])
    with pytest.raises(CatalogError, match="пустой пул"):
        Catalog.from_dir(tmp_path)
    _write(tmp_path, [GOOD_ITEM], cases=[{"id": "c", "name": "C", "price": 1, "weights": {"common": -1}}])
    with pytest.raises(CatalogError, match="веса"):
        Catalog.from_dir(tmp_path)
    (tmp_path / "items.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(CatalogError):
        Catalog.from_dir(tmp_path)
    (tmp_path / "items.json").write_text("{}", encoding="utf-8")
    with pytest.raises(CatalogError, match="список"):
        Catalog.from_dir(tmp_path)
