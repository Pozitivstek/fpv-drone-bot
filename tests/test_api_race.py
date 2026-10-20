"""Гонки через API: старт, приём результата, античит, награды, износ, рекорды и призрак."""

from __future__ import annotations

from datetime import timedelta

from app import clock
from app.catalog import Track
from app.game.builds import Flight
from app.game.racing import ideal_ms
from app.store import users
from tests.conftest import PLAYER, fail, ok
from tests.paths import perfect_path


async def start(client, track_id="hangar", training=False) -> dict:
    return await ok(await client.post("/api/race/start", json={"track_id": track_id, "training": training}))


async def backdate(ctx, race_id: int, seconds: int) -> None:
    moment = clock.iso(clock.now() - timedelta(seconds=seconds))
    async with ctx.db.tx() as conn:
        await conn.execute("UPDATE races SET started_at = ? WHERE id = ?", (moment, race_id))


def good_time(ctx, race: dict, factor: float = 1.0) -> int:
    track: Track = ctx.catalog.tracks[race["track_id"]]
    return round(ideal_ms(track, Flight(**race["flight"])) * factor)


def run(ctx, race: dict, time_ms: int, **extra) -> dict:
    track = ctx.catalog.tracks[race["track_id"]]
    return {"finished": True, "time_ms": time_ms, "gates": track.gates, "missed": 0, "crashes": 0,
            "path": perfect_path(track, time_ms), **extra}


async def test_full_race_gives_coins_xp_record_and_ghost(client, ctx):
    race = await start(client)
    assert race["fee"] == 0 and race["ghost"] is None and race["flight"]["cls"] == "whoop"
    await backdate(ctx, race["race_id"], 120)
    result = await ok(await client.post(f"/api/race/{race['race_id']}/finish", json=run(ctx, race, good_time(ctx, race))))
    assert result["medal"] == "gold" and result["coins"] == 60 and result["new_record"] and result["place"] == 1
    assert result["wear"]["props"] == 4 and not result["broken"]
    assert "завершён" in await fail(await client.post(f"/api/race/{race['race_id']}/finish", json=run(ctx, race, 1000)))
    again = await start(client)
    assert again["ghost"]["time_ms"] == result["total_ms"] and len(again["ghost"]["path"]) > 100
    board = await ok(await client.get("/api/tracks/hangar/leaderboard"))
    assert board[0]["user_id"] == PLAYER
    tracks = await ok(await client.get("/api/tracks"))
    assert tracks[0]["my_best"] == result["total_ms"] and tracks[1]["locked"]
    me = await ok(await client.get("/api/me"))
    assert me["stats"]["races"] == 1 and me["stats"]["golds"] == 1


async def test_impossible_time_is_rejected_and_cannot_be_resubmitted(client, ctx):
    race = await start(client)
    detail = await fail(await client.post(f"/api/race/{race['race_id']}/finish", json=run(ctx, race, good_time(ctx, race, 0.3))))
    assert "не засчитан" in detail
    assert "завершён" in await fail(await client.post(f"/api/race/{race['race_id']}/finish",
                                                      json=run(ctx, race, good_time(ctx, race))))


async def test_dnf_and_crashes_wear_parts(client, ctx):
    race = await start(client)
    track = ctx.catalog.tracks["hangar"]
    await backdate(ctx, race["race_id"], 60)
    result = await ok(await client.post(f"/api/race/{race['race_id']}/finish",
                                        json={"finished": False, "time_ms": 12_000, "gates": 4, "missed": 0, "crashes": 9,
                                              "path": perfect_path(track, 12_000, reach=4)}))
    assert not result["finished"] and result["coins"] == 0 and result["xp"] > 0
    assert result["wear"]["frame"] > 50 and result["broken"]
    detail = await fail(await client.post("/api/race/start", json={"track_id": "hangar"}))
    assert "ремонт" in detail


async def test_training_is_free_and_gives_nothing(client, ctx):
    race = await start(client, training=True)
    await backdate(ctx, race["race_id"], 120)
    result = await ok(await client.post(f"/api/race/{race['race_id']}/finish", json=run(ctx, race, good_time(ctx, race))))
    assert result["training"] and result["coins"] == 0 and result["xp"] == 0 and result["wear"] == {}


async def test_level_gate_fee_and_expired_race(client, ctx):
    assert "уровне" in await fail(await client.post("/api/race/start", json={"track_id": "forest"}))
    assert (await client.post("/api/race/start", json={"track_id": "nope"})).status_code == 404
    async with ctx.db.tx() as conn:
        await users.update(conn, PLAYER, level=2)
    race = await start(client, "forest")
    assert race["fee"] == 40 and (await ok(await client.get("/api/me")))["coins"] == 460
    await backdate(ctx, race["race_id"], 3600)
    assert "долго" in await fail(await client.post(f"/api/race/{race['race_id']}/finish",
                                                   json=run(ctx, race, good_time(ctx, race))))
    assert (await client.post("/api/race/999/finish", json=run(ctx, race, 1000))).status_code == 404


async def test_no_active_build(client, ctx):
    await ok(await client.get("/api/me"))
    async with ctx.db.tx() as conn:
        await users.update(conn, PLAYER, active_build_id=None)
    assert "сборку" in await fail(await client.post("/api/race/start", json={"track_id": "hangar"}))


async def test_instant_dnf_cannot_farm_xp(client, ctx):
    race = await start(client)
    detail = await fail(await client.post(f"/api/race/{race['race_id']}/finish",
                                          json={"finished": False, "time_ms": 0, "gates": 12, "missed": 0, "crashes": 0}))
    assert "не засчитан" in detail


async def test_daily_reward_cap(client, ctx, monkeypatch):
    from app.services import racing as racing_service
    monkeypatch.setattr(racing_service, "DAILY_REWARDED_RACES", 1)
    for expected_capped in (False, True):
        race = await start(client)
        await backdate(ctx, race["race_id"], 120)
        result = await ok(await client.post(f"/api/race/{race['race_id']}/finish",
                                            json=run(ctx, race, good_time(ctx, race))))
        assert result["capped"] is expected_capped and (result["coins"] == 0) is expected_capped


async def test_banned_player_cannot_finish(client, ctx):
    race = await start(client)
    async with ctx.db.tx() as conn:
        await users.update(conn, PLAYER, banned=1)
    assert (await client.post(f"/api/race/{race['race_id']}/finish", json=run(ctx, race, 1000))).status_code == 403
