"""Чистая игровая логика: сборка, шансы, мастерская, прогресс, гонки, задания, бонус."""

from __future__ import annotations

import random
from datetime import date

import pytest

from app.catalog import Track
from app.game import daily, tasks
from app.game.builds import Part, evaluate
from app.game.drops import case_odds, luck_factor, rarity_odds, roll
from app.game.progression import RANKS, level_for_xp, level_reward, progress, rank_for_level, xp_for_level
from app.game.racing import (
    RaceClaim, RaceRejected, ideal_ms, medal_for, min_possible_ms, obstacle_hits, repair_cost, rewards, total_ms,
    validate, wear_after,
)
from app.game.track import build_layout, mulberry32
from tests.paths import perfect_path
from app.game.workshop import WorkshopError, contract_rarity, upgrade_chance


def kit_parts(catalog, kit_id, **overrides):
    items = [catalog.items[i] for i in catalog.kits[kit_id].items]
    slots = {item.slot: Part(item) for item in items if not item.is_gear}
    gear = {item.slot: Part(item) for item in items if item.is_gear}
    for slot, item_id in overrides.items():
        target = gear if slot in gear else slots
        target[slot] = Part(catalog.items[item_id]) if item_id else None
    return slots, gear.get("goggles"), gear.get("radio")


def test_missing_parts_are_listed(catalog):
    slots, goggles, radio = kit_parts(catalog, "starter", motors=None, props=None)
    report = evaluate(slots, goggles, radio)
    assert not report.ready and report.flight is None
    assert any("моторы" in issue for issue in report.issues) and any("пропеллеры" in issue for issue in report.issues)


def test_class_and_video_compatibility(catalog):
    slots, goggles, radio = kit_parts(catalog, "starter", motors="mo_f90")
    assert any("не подходит" in issue for issue in evaluate(slots, goggles, radio).issues)
    slots, goggles, radio = kit_parts(catalog, "starter", goggles="gg_dji3")
    assert any("не принимают Аналог" in issue for issue in evaluate(slots, goggles, radio).issues)
    slots, _, radio = kit_parts(catalog, "starter")
    assert any("очков" in issue for issue in evaluate(slots, None, radio).issues)
    assert any("пульта" in issue for issue in evaluate(slots, Part(catalog.items["gg_ev800d"]), None).issues)


def test_broken_parts_block_flight(catalog):
    slots, goggles, radio = kit_parts(catalog, "starter")
    slots["props"] = Part(slots["props"].item, wear=100)
    report = evaluate(slots, Part(goggles.item, 100), Part(radio.item, 100))
    assert sum("ремонт" in issue for issue in report.issues) == 3


def test_better_parts_fly_faster_and_cleaner(catalog):
    cheap = evaluate(*kit_parts(catalog, "starter")).flight
    good = evaluate(*kit_parts(catalog, "meteor75_hd")).flight
    racer = evaluate(*kit_parts(catalog, "racerx")).flight
    assert cheap.top_speed < good.top_speed < racer.top_speed
    assert cheap.noise > 0 and good.noise == 0  # аналог шумит, цифра — нет
    worn = evaluate(*kit_parts(catalog, "starter")).flight
    assert worn == cheap


def test_odds_sum_to_one_and_luck_favours_rare(catalog):
    case = catalog.cases["freestyle"]
    pool = catalog.pool("freestyle")
    assert sum(entry.chance for entry in case_odds(case, pool, 1.0)) == pytest.approx(1.0)
    normal, lucky = rarity_odds(case, pool, 1.0), rarity_odds(case, pool, 3.0)
    assert lucky["mythic"] > normal["mythic"] * 5 and lucky["common"] < normal["common"]
    assert luck_factor(100, 5) == luck_factor(10, 5)  # удача ограничена сверху


def test_roll_is_deterministic_with_seeded_rng(catalog):
    odds = case_odds(catalog.cases["starter"], catalog.pool("starter"), 1.0)
    first = [roll(odds, random.Random(1)).id for _ in range(3)]
    assert first == [roll(odds, random.Random(1)).id for _ in range(3)]
    assert roll(odds, type("R", (), {"random": lambda self: 0.999999999})()) in [e.item for e in odds]


def test_upgrade_chance_rules():
    assert upgrade_chance(100, 200) == pytest.approx(0.45)
    assert upgrade_chance(100, 110, luck=5) == 0.8
    for stake, target in ((0, 100), (100, 100), (10, 10_000)):
        with pytest.raises(WorkshopError):
            upgrade_chance(stake, target)


def test_contract_rules():
    assert contract_rarity(["rare"] * 5) == "epic"
    for rarities in (["rare"] * 4, ["rare"] * 4 + ["epic"], ["mythic"] * 5):
        with pytest.raises(WorkshopError):
            contract_rarity(rarities)


def test_levels_and_ranks():
    assert xp_for_level(1) == 0 and level_for_xp(0) == 1
    assert level_for_xp(xp_for_level(10)) == 10 and level_for_xp(xp_for_level(10) - 1) == 9
    assert rank_for_level(1) == RANKS[0] and rank_for_level(30).title == "Легенда DRL"
    assert level_reward(10) == (500, {"freestyle": 1, "legend": 1})
    assert progress(xp_for_level(5))["level_xp"] == 0 and progress(10**9)["pct"] == 100


TRACK = Track(id="t", name="T", theme="hangar", seed=1, gates=10, spacing=30, gate_size=2.5, wiggle=2, obstacles=0,
              fee=10, reward=100, xp=20)


@pytest.fixture
def flight(catalog):
    return evaluate(*kit_parts(catalog, "freestyle_hdz")).flight


def claim(flight, track=TRACK, factor=1.0, path=None, **kwargs) -> RaceClaim:
    time_ms = kwargs.pop("time_ms", round(ideal_ms(track, flight) * factor))
    data = {"finished": True, "time_ms": time_ms, "gates": track.gates, "missed": 0, "crashes": 0, **kwargs}
    if path is None:
        reach = None if data["finished"] else data["gates"] + data["missed"]
        path = perfect_path(track, time_ms, reach)
    return RaceClaim(**data, path=tuple(tuple(point) for point in path))


def test_python_layout_is_deterministic():
    first, second = build_layout(TRACK), build_layout(TRACK)
    assert first == second and len(first.gates) == 10
    assert mulberry32(42)() == mulberry32(42)()


def test_valid_race_passes_and_earns_medal(flight):
    good = claim(flight)
    validate(TRACK, flight, good, elapsed_ms=60_000)
    assert medal_for(TRACK, flight, good) == "gold"
    assert medal_for(TRACK, flight, claim(flight, factor=1.5)) == "bronze"
    assert medal_for(TRACK, flight, claim(flight, finished=False, gates=3)) == ""
    assert total_ms(claim(flight, missed=2, gates=8)) == good.time_ms + 6_000


@pytest.mark.parametrize("bad, reason", [
    ({"crashes": -1}, "отрицательные"),
    ({"gates": 11}, "ворот больше"),
    ({"time_ms": 90_000}, "прошло"),
    ({"path": [[i, 0.0, 0.0, 0.0] for i in range(2500)]}, "длинная"),
    ({"gates": 5}, "всех ворот"),
    ({"crashes": 99}, "повреждениями"),
    ({"time_ms": 1}, "быстрее"),
])
def test_cheats_are_rejected(flight, bad, reason):
    with pytest.raises(RaceRejected, match=reason):
        validate(TRACK, flight, claim(flight, **bad), elapsed_ms=60_000)


def test_forged_flight_records_are_rejected(flight):
    time_ms = round(ideal_ms(TRACK, flight))
    good = perfect_path(TRACK, time_ms)
    forged = {
        "нет записи": [],
        "битая": [[float("nan"), 0, 0, float("nan")]] + good[1:],
        "вне трассы": [[0, 500.0, 0, 0]] + good[1:],
        "не совпадает": [[p[0] / 2, *p[1:]] for p in good],
        "редкая": good[::5],
        "назад": good[:10] + good[5:],
        "заявленные ворота": perfect_path(TRACK, time_ms, shift=8.0),
        "финиш не достигнут": [[p[0], p[1], p[2], p[3] * 0.93] for p in good],
    }
    for reason, path in forged.items():
        with pytest.raises(RaceRejected, match=reason):
            validate(TRACK, flight, claim(flight, path=path), elapsed_ms=60_000)
    sprint = [list(p) for p in good]
    sprint[5][3] = sprint[6][3] = sprint[7][3] = 200.0
    with pytest.raises(RaceRejected, match="быстрее"):
        validate(TRACK, flight, claim(flight, path=sprint), elapsed_ms=60_000)


def test_obstacle_hits_must_be_counted_as_crashes(catalog, flight):
    track = catalog.tracks["city"]
    layout = build_layout(track)
    obstacle = layout.obstacles[0]
    time_ms = round(ideal_ms(track, flight) * 1.2)
    path = perfect_path(track, time_ms)
    near = min(range(len(path)), key=lambda i: abs(path[i][3] - obstacle.z))
    for index in (near - 1, near, near + 1):
        path[index][1], path[index][2] = obstacle.x, 1.0
    assert obstacle_hits(layout, tuple(map(tuple, path))) == 1
    with pytest.raises(RaceRejected, match="препятствия"):
        validate(track, flight, claim(flight, track, path=path, time_ms=time_ms), elapsed_ms=10**6)
    validate(track, flight, claim(flight, track, path=path, time_ms=time_ms, crashes=1), elapsed_ms=10**6)


def test_dnf_needs_physical_time_and_flight(flight):
    with pytest.raises(RaceRejected, match="быстрее"):
        validate(TRACK, flight, claim(flight, finished=False, gates=8, time_ms=0, path=[]), elapsed_ms=60_000)
    with pytest.raises(RaceRejected, match="нет записи"):
        validate(TRACK, flight, claim(flight, finished=False, gates=3, time_ms=8_000, path=[]), elapsed_ms=60_000)
    validate(TRACK, flight, claim(flight, finished=False, gates=3, time_ms=8_000), elapsed_ms=60_000)
    validate(TRACK, flight, claim(flight, finished=False, gates=0, time_ms=0, path=[]), elapsed_ms=60_000)


def test_battery_limit(flight):
    with pytest.raises(RaceRejected, match="аккумулятор"):
        validate(TRACK, flight, claim(flight, time_ms=round(flight.flight_time * 1000 + 5000)), elapsed_ms=10**6)
    assert min_possible_ms(TRACK, flight) < ideal_ms(TRACK, flight)


def test_rewards_wear_and_repair():
    assert rewards(TRACK, "gold", True) == (100, 30)
    assert rewards(TRACK, "", True, race_mult=2) == (50, 20)
    assert rewards(TRACK, "", False) == (0, 6)
    assert rewards(TRACK, "", False, progress=0.5) == (0, 3)
    soft, hard = wear_after(2, 90), wear_after(2, 10)
    assert soft["frame"] < hard["frame"] and wear_after(0, 50)["props"] == 4
    assert repair_cost(1000, 0) == 0 and repair_cost(1000, 50) == 175


def test_daily_tasks_are_stable_per_day():
    first = tasks.daily_tasks(1, "d:2026-10-20")
    assert first == tasks.daily_tasks(1, "d:2026-10-20") and len({t.id for t in first}) == tasks.DAILY_COUNT
    active = tasks.active_tasks(1, "d:x", "w:y")
    assert len(active) == tasks.DAILY_COUNT + len(tasks.WEEKLY)


def test_daily_streak():
    today = date(2026, 10, 20)
    assert daily.next_streak(today, today, 3) is None
    assert daily.next_streak(date(2026, 10, 19), today, 3) == 4
    assert daily.next_streak(date(2026, 10, 1), today, 3) == 1 and daily.next_streak(None, today, 0) == 1
    assert daily.reward_for(7) == (600, {"freestyle": 1}) and daily.reward_for(8) == daily.reward_for(1)
