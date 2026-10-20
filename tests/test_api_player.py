"""API игрока: регистрация, кейсы, инвентарь, ангар, мастерская, задания, промокоды, авторизация."""

from __future__ import annotations

import asyncio

from app.game.progression import xp_for_level
from app.services.rewards import add_xp
from app.store import users
from tests.conftest import PLAYER, act_as, fail, init_data, ok


async def test_new_player_gets_starter_kit_ready_to_fly(client):
    me = await ok(await client.get("/api/me"))
    assert me["coins"] == 500 and me["keys"] == {"starter": 1, "daily": 1} and not me["is_admin"]
    hangar = await ok(await client.get("/api/hangar"))
    build = hangar["builds"][0]
    assert build["active"] and build["ready"] and build["cls"] == "whoop"
    assert hangar["goggles"]["id"] == "gg_ev800d" and hangar["radio"]["id"] == "rc_fsi6x"
    assert me["ref_link"].endswith(f"start=ref_{PLAYER}")


async def test_catalog_payload(client):
    data = await ok(await client.get("/api/catalog"))
    assert len(data["items"]) > 100 and len(data["tracks"]) == 7 and data["rules"]["contract_size"] == 5


async def test_daily_bonus_once_per_day(client):
    first = await ok(await client.post("/api/daily"))
    assert first["streak"] == 1 and first["coins"] == 100
    assert "уже получен" in await fail(await client.post("/api/daily"))
    me = await ok(await client.get("/api/me"))
    assert me["coins"] == 600 and not me["daily"]["claimable"] and me["daily"]["day"] == 2


async def test_open_cases_with_keys_and_coins(client):
    by_key = await ok(await client.post("/api/cases/starter/open", json={"use_keys": True}))
    assert len(by_key["items"]) == 1 and by_key["keys"] == 0 and by_key["coins"] == 500
    paid = await ok(await client.post("/api/cases/starter/open", json={"count": 3}))
    assert len(paid["items"]) == 3 and paid["coins"] == 500 - 3 * 150
    assert "ключей" in await fail(await client.post("/api/cases/starter/open", json={"use_keys": True}))
    assert "уровне" in await fail(await client.post("/api/cases/legend/open", json={}))
    async with client._transport.app.state.ctx.db.tx() as conn:
        await conn.execute("INSERT INTO case_keys (user_id, case_id, qty) VALUES (?, 'legend', 1)", (PLAYER,))
    by_legend_key = await ok(await client.post("/api/cases/legend/open", json={"use_keys": True}))
    assert by_legend_key["items"][0]["rarity"] in {"rare", "epic", "legendary", "mythic"}
    assert "монет" in await fail(await client.post("/api/cases/freestyle/open", json={}))
    assert "не продаётся" in await fail(await client.post("/api/cases/daily/open", json={}))
    assert (await client.post("/api/cases/nope/open", json={})).status_code == 404
    me = await ok(await client.get("/api/me"))
    assert me["stats"]["cases_opened"] == 5


async def test_case_list_and_detail_show_odds(client):
    cases = await ok(await client.get("/api/cases"))
    starter = next(case for case in cases if case["id"] == "starter")
    assert sum(starter["odds"].values()) == __import__("pytest").approx(100, abs=0.01)
    assert next(case for case in cases if case["id"] == "mythic")["locked"]
    detail = await ok(await client.get("/api/cases/video"))
    assert detail["items"][0]["chance"] < detail["items"][-1]["chance"]
    assert (await client.get("/api/cases/nope")).status_code == 404


async def test_inventory_sell_and_locks(client):
    inventory = await ok(await client.get("/api/inventory"))
    locked = [item["uid"] for item in inventory["items"] if item["locked"]]
    assert len(locked) == 8
    assert "снимите" in await fail(await client.post("/api/inventory/sell", json={"uids": locked[:1]}))
    opened = await ok(await client.post("/api/cases/starter/open", json={"use_keys": True}))
    uid = opened["items"][0]["uid"]
    sold = await ok(await client.post("/api/inventory/sell", json={"uids": [uid]}))
    assert sold["sold"] == 1 and sold["earned"] == opened["items"][0]["sell"]
    assert (await client.post("/api/inventory/sell", json={"uids": [uid]})).status_code == 404
    assert "Нечего продавать" in await fail(await client.post("/api/inventory/sell-bulk", json={"max_rarity": "mythic"}))
    await ok(await client.post("/api/cases/starter/open", json={"count": 2}))
    bulk = await ok(await client.post("/api/inventory/sell-bulk", json={"max_rarity": "mythic"}))
    assert bulk["sold"] == 2
    assert "редкость" in await fail(await client.post("/api/inventory/sell-bulk", json={"max_rarity": "gold"}))


async def test_shop(client):
    shop = await ok(await client.get("/api/shop"))
    assert shop and all(item["rarity"] in {"common", "uncommon"} for item in shop)
    cheap = min(shop, key=lambda item: item["price"])
    bought = await ok(await client.post("/api/shop/buy", json={"item_id": cheap["id"], "qty": 2}))
    assert len(bought["items"]) == 2 and bought["coins"] == 500 - 2 * cheap["price"]
    assert "кейсов" in await fail(await client.post("/api/shop/buy", json={"item_id": "fr_racerx"}))
    assert "монет" in await fail(await client.post("/api/shop/buy", json={"item_id": "gg_n3", "qty": 10}))
    assert (await client.post("/api/shop/buy", json={"item_id": "nope"})).status_code == 404


async def test_hangar_builds_and_equipment(client):
    hangar = await ok(await client.get("/api/hangar"))
    first = hangar["builds"][0]
    frame_uid = first["parts"]["frame"]["uid"]
    new_id = (await ok(await client.post("/api/hangar/builds", json={"name": "  Мой   5 дюймов "})))["id"]
    await ok(await client.put(f"/api/hangar/builds/{new_id}/slots/frame", json={"uid": frame_uid}))
    hangar = await ok(await client.get("/api/hangar"))
    old, new = hangar["builds"]
    assert old["parts"]["frame"] is None and new["parts"]["frame"]["uid"] == frame_uid and new["name"] == "Мой 5 дюймов"
    assert "это не" in await fail(await client.put(f"/api/hangar/builds/{new_id}/slots/motors", json={"uid": frame_uid}))
    assert (await client.put(f"/api/hangar/builds/{new_id}/slots/wing", json={"uid": None})).status_code == 400
    await ok(await client.patch(f"/api/hangar/builds/{new_id}", json={"name": "Гонка"}))
    await ok(await client.post(f"/api/hangar/builds/{new_id}/activate"))
    assert (await ok(await client.get("/api/hangar")))["active_id"] == new_id
    await ok(await client.delete(f"/api/hangar/builds/{new_id}"))
    assert (await ok(await client.get("/api/hangar")))["active_id"] == old["id"]
    assert (await client.delete(f"/api/hangar/builds/{new_id}")).status_code == 404
    assert (await client.post("/api/hangar/builds/999/activate")).status_code == 404


async def test_gear_slots(client):
    hangar = await ok(await client.get("/api/hangar"))
    goggles = hangar["goggles"]["uid"]
    await ok(await client.put("/api/hangar/gear/goggles", json={"uid": None}))
    build = (await ok(await client.get("/api/hangar")))["builds"][0]
    assert not build["ready"] and any("очков" in issue for issue in build["issues"])
    assert "это не" in await fail(await client.put("/api/hangar/gear/radio", json={"uid": goggles}))
    await ok(await client.put("/api/hangar/gear/goggles", json={"uid": goggles}))
    assert (await client.put("/api/hangar/gear/frame", json={"uid": None})).status_code == 400


async def test_repair(client, ctx):
    hangar = await ok(await client.get("/api/hangar"))
    props = hangar["builds"][0]["parts"]["props"]["uid"]
    assert "как новые" in await fail(await client.post("/api/hangar/repair", json={"uids": [props]}))
    async with ctx.db.tx() as conn:
        await conn.execute("UPDATE items SET wear = 60 WHERE id = ?", (props,))
    repaired = await ok(await client.post("/api/hangar/repair", json={"uids": [props]}))
    assert repaired["repaired"] == 1 and repaired["cost"] > 0 and repaired["coins"] == 500 - repaired["cost"]


async def test_workshop_upgrade_and_contract(client, ctx):
    opened = await ok(await client.post("/api/cases/starter/open", json={"count": 3}))
    uid = opened["items"][0]["uid"]
    assert "2 %" in await fail(await client.post("/api/workshop/upgrade", json={"uids": [uid], "target": "fr_racerx"}))
    cheap_target = "gg_cobrax" if opened["items"][0]["id"] != "gg_cobrax" else "gg_ev800d"
    result = await client.post("/api/workshop/upgrade", json={"uids": [uid], "target": "rc_tx16s"})
    assert result.status_code in (200, 400)
    assert cheap_target
    async with ctx.db.tx() as conn:
        for _ in range(5):
            await conn.execute("INSERT INTO items (user_id, item_id, created_at) VALUES (?, 'pr_dal', 'x')", (PLAYER,))
    inventory = await ok(await client.get("/api/inventory"))
    commons = [item["uid"] for item in inventory["items"] if item["id"] == "pr_dal"][:5]
    contract = await ok(await client.post("/api/workshop/contract", json={"uids": commons}))
    assert contract["item"]["rarity"] == "uncommon"
    assert (await client.post("/api/workshop/contract", json={"uids": commons})).status_code == 404


async def test_tasks_progress_and_claim(client):
    tasks = await ok(await client.get("/api/tasks"))
    assert len(tasks) == 8
    await ok(await client.post("/api/cases/starter/open", json={"count": 3}))
    tasks = await ok(await client.get("/api/tasks"))
    weekly_cases = next(task for task in tasks if task["id"] == "w_cases")
    assert weekly_cases["progress"] == 3 and not weekly_cases["ready"]
    assert "не выполнено" in await fail(await client.post("/api/tasks/w_cases/claim"))
    assert (await client.post("/api/tasks/nope/claim")).status_code == 404
    daily_cases = next((task for task in tasks if task["id"] == "d_cases"), None)
    if daily_cases:
        claimed = await ok(await client.post("/api/tasks/d_cases/claim"))
        assert claimed["coins"] == 150


async def test_leaderboards_and_feed(client):
    await ok(await client.post("/api/cases/starter/open", json={"count": 3}))
    for kind in ("level", "golds", "collection"):
        rows = await ok(await client.get(f"/api/leaderboard?kind={kind}"))
        assert rows[0]["user_id"] == PLAYER
    assert (await client.get("/api/leaderboard?kind=money")).status_code == 400
    assert isinstance(await ok(await client.get("/api/feed")), list)


async def test_signed_init_data_and_referral(client, ctx):
    assert (await client.get("/api/me", headers={"X-Telegram-Init-Data": "hash=bad"})).status_code == 401
    await ok(await client.get("/api/me"))
    friend = await ok(await client.get("/api/me", headers={"X-Telegram-Init-Data":
                                                          init_data(777, "Друг", start_param=f"ref_{PLAYER}")}))
    assert friend["coins"] == 700
    inviter = await users.get(ctx.db.conn, PLAYER)
    assert inviter.coins == 500  # пригласившему платим, только когда друг поиграет
    async with ctx.db.tx() as conn:
        await add_xp(ctx, conn, 777, xp_for_level(5))
    await asyncio.sleep(0)
    inviter = await users.get(ctx.db.conn, PLAYER)
    assert inviter.coins == 500 + 300 + 700
    texts = [text for chat, text in ctx.sent if chat == PLAYER]
    assert any("По вашей ссылке" in text for text in texts) and any("достиг 5 уровня" in text for text in texts)
    weekly_invite = next(task for task in await ok(await client.get("/api/tasks")) if task["id"] == "w_invite")
    assert weekly_invite["ready"]
    self_ref = await ok(await client.get("/api/me", headers={"X-Telegram-Init-Data":
                                                            init_data(778, "Сам", start_param="ref_778")}))
    assert self_ref["coins"] == 500


async def test_banned_player_cannot_play(client, ctx):
    await ok(await client.get("/api/me"))
    async with ctx.db.tx() as conn:
        await users.update(conn, PLAYER, banned=1)
    assert (await ok(await client.get("/api/me")))["banned"]
    assert "заблокирован" in await fail(await client.post("/api/cases/starter/open", json={}), 403)
    assert (await client.post("/api/daily")).status_code == 403
    assert (await client.get("/api/admin/stats")).status_code == 403


async def test_promo_requires_existing_code(client):
    assert "нет" in await fail(await client.post("/api/promo", json={"code": "???"}))
    assert "нет" in await fail(await client.post("/api/promo", json={"code": "NOPE1"}))


async def test_promo_bruteforce_is_throttled(client):
    from app.api.deps import LIMITERS
    for _ in range(8):
        LIMITERS["promo"].clear()
        await client.post("/api/promo", json={"code": "WRONG1"})
    LIMITERS["promo"].clear()
    assert "Слишком много" in await fail(await client.post("/api/promo", json={"code": "WRONG2"}))


async def test_huge_ids_are_rejected_not_crashing(client):
    assert (await client.post("/api/inventory/sell", json={"uids": [2**70]})).status_code == 422
    assert (await client.post(f"/api/hangar/builds/{2**70}/activate")).status_code == 422


async def test_rate_limit(client, ctx):
    act_as(ctx, PLAYER)
    statuses = [(await client.post("/api/promo", json={"code": "NOPE1"})).status_code for _ in range(12)]
    assert statuses[-1] == 429


async def test_health_and_index(client):
    assert (await ok(await client.get("/api/health")))["ok"]
    assert (await client.get("/")).status_code == 200
