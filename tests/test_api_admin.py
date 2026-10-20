"""Админка: доступ, статистика, действия над игроком, промокоды, события, рассылка, журнал."""

from __future__ import annotations

import asyncio

from app.game.progression import xp_for_level
from app.store import users
from tests.conftest import ADMIN, PLAYER, act_as, fail, ok


async def test_only_admin_has_access(client, ctx):
    assert (await client.get("/api/admin/stats")).status_code == 403
    act_as(ctx, ADMIN)
    assert (await ok(await client.get("/api/me")))["is_admin"]
    assert (await ok(await client.get("/api/admin/stats")))["users"] == 2


async def test_search_and_card(admin):
    found = await ok(await admin.get(f"/api/admin/users?q={PLAYER}"))
    assert found[0]["id"] == PLAYER
    assert len(await ok(await admin.get("/api/admin/users?q="))) == 2
    assert await ok(await admin.get("/api/admin/users?q=Разраб"))
    card = await ok(await admin.get(f"/api/admin/users/{PLAYER}"))
    assert card["stats"]["items"] == 8 and card["hangar"]["builds"]
    assert (await admin.get("/api/admin/users/123456")).status_code == 404


async def test_coins_level_rank_luck(admin, ctx):
    assert (await ok(await admin.post(f"/api/admin/users/{PLAYER}/coins", json={"delta": 1000})))["applied"] == 1000
    assert (await ok(await admin.post(f"/api/admin/users/{PLAYER}/coins", json={"delta": -99999})))["applied"] == -1500
    assert (await admin.post(f"/api/admin/users/{PLAYER}/coins", json={"delta": 0})).status_code == 400
    await ok(await admin.post(f"/api/admin/users/{PLAYER}/level", json={"level": 12}))
    player = await users.get(ctx.db.conn, PLAYER)
    assert player.level == 12 and player.xp == xp_for_level(12) and player.coins == 0
    await ok(await admin.post(f"/api/admin/users/{PLAYER}/rank", json={"rank": 8}))
    assert (await users.get(ctx.db.conn, PLAYER)).level == 30
    assert (await admin.post(f"/api/admin/users/{PLAYER}/rank", json={"rank": 99})).status_code == 400
    assert (await admin.post(f"/api/admin/users/{PLAYER}/level", json={"level": 0})).status_code == 400
    await ok(await admin.post(f"/api/admin/users/{PLAYER}/luck", json={"luck": 4}))
    assert (await admin.post(f"/api/admin/users/{PLAYER}/luck", json={"luck": 50})).status_code == 400
    await asyncio.sleep(0)
    texts = [text for chat, text in ctx.sent if chat == PLAYER]
    assert any("начислил" in text for text in texts) and any("повысил" in text for text in texts)


async def test_luck_changes_visible_odds(admin, ctx):
    act_as(ctx, PLAYER)
    before = await ok(await admin.get("/api/cases"))
    act_as(ctx, ADMIN)
    await ok(await admin.post(f"/api/admin/users/{PLAYER}/luck", json={"luck": 3}))
    act_as(ctx, PLAYER)
    after = await ok(await admin.get("/api/cases"))
    assert after[1]["odds"]["rare"] > before[1]["odds"]["rare"]


async def test_give_items_cases_kits(admin, ctx):
    summary = await ok(await admin.post(f"/api/admin/users/{PLAYER}/give",
                                        json={"coins": 50, "xp": 400, "items": ["fr_racerx"], "keys": {"mythic": 2},
                                              "kits": ["cine_dji"]}))
    assert len(summary["items"]) == 9 and summary["level_up"]["to"] >= 3
    act_as(ctx, PLAYER)
    hangar = await ok(await admin.get("/api/hangar"))
    assert len(hangar["builds"]) == 2 and hangar["builds"][1]["name"] == "Синевуп на DJI O4"
    assert (await ok(await admin.get("/api/me")))["keys"]["mythic"] == 2
    act_as(ctx, ADMIN)
    for bad in ({"items": ["nope"]}, {"keys": {"nope": 1}}, {"kits": ["nope"]}, {}, {"coins": -5}):
        assert (await admin.post(f"/api/admin/users/{PLAYER}/give", json=bad)).status_code == 400


async def test_ban_take_and_repair(admin, ctx):
    assert "Себя" in await fail(await admin.post(f"/api/admin/users/{ADMIN}/ban", json={"banned": True}))
    await ok(await admin.post(f"/api/admin/users/{PLAYER}/ban", json={"banned": True}))
    assert (await users.get(ctx.db.conn, PLAYER)).banned
    await ok(await admin.post(f"/api/admin/users/{PLAYER}/ban", json={"banned": False}))
    card = await ok(await admin.get(f"/api/admin/users/{PLAYER}"))
    uid = card["inventory"]["items"][0]["uid"]
    async with ctx.db.tx() as conn:
        await conn.execute("UPDATE items SET wear = 70 WHERE user_id = ?", (PLAYER,))
    assert (await ok(await admin.post(f"/api/admin/users/{PLAYER}/repair")))["repaired"] == 8
    await ok(await admin.delete(f"/api/admin/users/{PLAYER}/items/{uid}"))
    assert (await admin.delete(f"/api/admin/users/{PLAYER}/items/{uid}")).status_code == 404


async def test_promo_lifecycle(admin, ctx):
    created = await ok(await admin.post("/api/admin/promos", json={"code": "launch", "reward": {"coins": 1000},
                                                                   "max_uses": 1, "days": 7, "note": "старт"}))
    assert created["code"] == "LAUNCH" and created["expires_at"]
    auto = await ok(await admin.post("/api/admin/promos", json={"reward": {"keys": {"freestyle": 1}}}))
    assert auto["code"].startswith("FPV-")
    assert "уже есть" in await fail(await admin.post("/api/admin/promos", json={"code": "LAUNCH",
                                                                                "reward": {"coins": 1}}))
    assert (await admin.post("/api/admin/promos", json={"code": "a b", "reward": {"coins": 1}})).status_code == 400
    assert (await admin.post("/api/admin/promos", json={"reward": {"coins": 1}, "days": 999})).status_code == 400
    act_as(ctx, PLAYER)
    redeemed = await ok(await admin.post("/api/promo", json={"code": " launch "}))
    assert redeemed["coins"] == 1000 and "1 000 монет" in redeemed["text"]
    assert "использован" in await fail(await admin.post("/api/promo", json={"code": "LAUNCH"}))
    act_as(ctx, ADMIN)
    assert "использован" in await fail(await admin.post("/api/promo", json={"code": "LAUNCH"}))  # лимит 1
    await ok(await admin.patch(f"/api/admin/promos/{auto['code']}", json={"active": False}))
    assert "нет" in await fail(await admin.post("/api/promo", json={"code": auto["code"]}))
    async with ctx.db.tx() as conn:
        await conn.execute("UPDATE promos SET active = 1, expires_at = '2000-01-01T00:00:00+00:00' WHERE code = ?",
                           (auto["code"],))
    assert "истёк" in await fail(await admin.post("/api/promo", json={"code": auto["code"]}))
    listed = await ok(await admin.get("/api/admin/promos"))
    assert {promo["code"] for promo in listed} == {"LAUNCH", auto["code"]}
    await ok(await admin.delete("/api/admin/promos/LAUNCH"))
    assert (await admin.delete("/api/admin/promos/LAUNCH")).status_code == 404
    assert (await admin.patch("/api/admin/promos/LAUNCH", json={"active": True})).status_code == 404


async def test_events_and_log(admin, ctx):
    assert (await ok(await admin.post("/api/admin/events", json={"key": "luck_event", "value": 9})))["value"] == 5.0
    await ok(await admin.post("/api/admin/events", json={"key": "race_mult", "value": 2}))
    assert (await admin.post("/api/admin/events", json={"key": "nope", "value": 2})).status_code == 404
    stats = await ok(await admin.get("/api/admin/stats"))
    assert stats["events"] == {"luck_event": 5.0, "race_mult": 2.0}
    log = await ok(await admin.get("/api/admin/log"))
    assert [entry["action"] for entry in log[:2]] == ["event", "event"]


async def test_broadcast(admin, ctx):
    started = await ok(await admin.post("/api/admin/broadcast", json={"text": "Новый сезон!"}))
    assert started["total"] == 2
    await ctx.broadcast_state["_task"]
    stats = await ok(await admin.get("/api/admin/stats"))
    assert stats["broadcast"]["sent"] == 2 and not stats["broadcast"]["running"]
    assert sum(text == "Новый сезон!" for _, text in ctx.sent) == 2
    assert (await admin.post("/api/admin/broadcast", json={"text": "   "})).status_code == 400


async def test_kit_swaps_goggles_that_cannot_see_its_video(admin, ctx):
    await ok(await admin.post(f"/api/admin/users/{PLAYER}/give", json={"kits": ["racerx"]}))
    act_as(ctx, PLAYER)
    hangar = await ok(await admin.get("/api/hangar"))
    assert hangar["goggles"]["id"] == "gg_gold" and hangar["radio"]["id"] == "rc_fsi6x"
    assert all(build["ready"] for build in hangar["builds"])
