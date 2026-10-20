"""Гонки: список трасс, старт заезда (снимок сборки) и приём результата мини-игры."""

from __future__ import annotations

from app import clock
from app.catalog import Track
from app.context import AppContext
from app.game.builds import Flight, Part
from app.game.racing import (
    RaceClaim, RaceRejected, medal_for, rewards, total_ms, validate, wear_after,
)
from app.services import progress
from app.services.errors import GameError, NotFound
from app.services.hangar import active_build
from app.services.players import require_active
from app.services.rewards import add_xp
from app.store import items, races, users
from app.store.users import User

RACE_TTL_S = 15 * 60
LEADERBOARD_SIZE = 20
DESTROYED_FRAME_WEAR = 30
DAILY_REWARDED_RACES = 60  # дальше заезды засчитываются в рекорды, но без монет и опыта


def _track(ctx: AppContext, track_id: str) -> Track:
    track = ctx.catalog.tracks.get(track_id)
    if track is None:
        raise NotFound("Нет такой трассы")
    return track


async def tracks(ctx: AppContext, user: User) -> list[dict]:
    conn = ctx.db.conn
    mine = await races.user_records(conn, user.id)
    result = []
    for track in ctx.catalog.tracks.values():
        top = await races.leaderboard(conn, track.id, 1)
        result.append({"id": track.id, "locked": user.level < track.min_level, "my_best": mine.get(track.id),
                       "record": {"name": top[0].name, "time_ms": top[0].time_ms, "cls": top[0].cls} if top else None})
    return result


async def leaderboard(ctx: AppContext, track_id: str) -> list[dict]:
    _track(ctx, track_id)
    return [{"place": index + 1, "user_id": rec.user_id, "name": rec.name, "time_ms": rec.time_ms, "cls": rec.cls,
             "build": rec.build_name} for index, rec in enumerate(await races.leaderboard(ctx.db.conn, track_id,
                                                                                         LEADERBOARD_SIZE))]


async def start(ctx: AppContext, user_id: int, track_id: str, training: bool) -> dict:
    track = _track(ctx, track_id)
    async with ctx.db.tx() as conn:
        user = await users.get(conn, user_id)
        if user is None:
            raise NotFound("Нет такого игрока")
        require_active(user)
        if user.level < track.min_level:
            raise GameError(f"Трасса откроется на {track.min_level} уровне")
        build, report, parts = await active_build(ctx, conn, user)
        if build is None:
            raise GameError("Выберите сборку в ангаре")
        if not report.ready or report.flight is None:
            raise GameError(report.issues[0] if report.issues else "Дрон не готов к полёту")
        fee = 0 if training else track.fee
        if not await users.spend(conn, user_id, fee):
            raise GameError(f"Взнос за участие {fee} монет — не хватает")
        uids = {slot: part.uid for slot, part in parts.items() if part}
        race_id = await races.create(conn, user_id, track_id, training, fee, build.id, build.name,
                                     report.flight.cls, report.flight.to_dict(), uids)
        ghost = await races.ghost(conn, track_id)
        own = await races.ghost(conn, track_id, user_id)
    return {"race_id": race_id, "track_id": track_id, "training": training, "fee": fee,
            "flight": report.flight.to_dict(), "build": {"name": build.name, "cls": report.cls, "rating": report.rating},
            "ghost": ghost, "own_best": own["time_ms"] if own else None}


def _claim(payload: dict) -> RaceClaim:
    try:
        path = tuple(tuple(float(value) for value in point[:4]) for point in payload.get("path") or ()
                     if isinstance(point, (list, tuple)) and len(point) >= 4)
        return RaceClaim(finished=bool(payload.get("finished")), time_ms=int(payload["time_ms"]),
                         gates=int(payload.get("gates", 0)), missed=int(payload.get("missed", 0)),
                         crashes=int(payload.get("crashes", 0)), path=path)
    except (KeyError, TypeError, ValueError) as exc:
        raise GameError("Неверные данные заезда") from exc


async def _apply_wear(ctx: AppContext, conn, user_id: int, parts: dict[str, int], crashes: int,
                      max_crashes: int) -> tuple[dict[str, int], list[str]]:
    owned = {o.uid: o for o in await items.get_many(conn, user_id, list(parts.values()))
             if o.item_id in ctx.catalog.items}
    frame = owned.get(parts.get("frame", 0))
    frame_quality = Part(ctx.catalog.items[frame.item_id], frame.wear).quality if frame else 0.0
    deltas = wear_after(crashes, frame_quality)
    if crashes > max_crashes:
        deltas["frame"] = deltas.get("frame", 0) + DESTROYED_FRAME_WEAR
    applied, broken = {}, []
    for slot, delta in deltas.items():
        found = owned.get(parts.get(slot, 0))
        if found is None or delta <= 0:
            continue
        await items.add_wear(conn, found.uid, delta)
        applied[slot] = delta
        if found.wear + delta >= 100:
            broken.append(ctx.catalog.items[found.item_id].name)
    return applied, broken


async def finish(ctx: AppContext, user_id: int, race_id: int, payload: dict) -> dict:
    claim = _claim(payload)
    async with ctx.db.tx() as conn:
        user = await users.get(conn, user_id)
        if user is None:
            raise NotFound("Нет такого игрока")
        require_active(user)
        race = await races.get(conn, user_id, race_id)
        if race is None:
            raise NotFound("Нет такого заезда")
        if race.status != "started":
            raise GameError("Этот заезд уже завершён")
        elapsed_ms = (clock.now() - clock.parse(race.started_at)).total_seconds() * 1000
        track = _track(ctx, race.track_id)
        flight = Flight(**race.flight)
        try:
            if elapsed_ms > RACE_TTL_S * 1000:
                raise RaceRejected("заезд длился слишком долго")
            validate(track, flight, claim, elapsed_ms)
        except RaceRejected as exc:
            # статус «rejected» должен сохраниться, поэтому ошибку поднимаем уже после COMMIT
            await races.finish(conn, race_id, "rejected")
            rejection = str(exc)
        else:
            return await _settle(ctx, conn, user_id, race, track, flight, claim)
    raise GameError(f"Результат не засчитан: {rejection}")


async def _settle(ctx: AppContext, conn, user_id: int, race, track: Track, flight: Flight, claim: RaceClaim) -> dict:
    medal = medal_for(track, flight, claim)
    events = await progress.events(conn)
    capped = not race.training and await races.count_rewarded_since(
        conn, user_id, clock.iso(clock.day_start())) >= DAILY_REWARDED_RACES
    coins, xp = (0, 0) if race.training or capped else \
        rewards(track, medal, claim.finished, events["race_mult"], claim.reached / track.gates)
    wear, broken = ({}, []) if race.training else \
        await _apply_wear(ctx, conn, user_id, race.parts, claim.crashes, flight.max_crashes)
    total = total_ms(claim)
    await users.add_coins(conn, user_id, coins)
    if claim.finished and not race.training:
        await users.bump(conn, user_id, "races")
        await progress.track(conn, user_id, "race_finish")
        await progress.track(conn, user_id, "medal", 1 if medal else 0)
        if medal == "gold":
            await users.bump(conn, user_id, "golds")
            await progress.track(conn, user_id, "gold")
    if not race.training:
        await progress.track(conn, user_id, "gates", claim.gates)
    level_up = await add_xp(ctx, conn, user_id, xp)
    best = await races.record(conn, user_id, track.id)
    new_record = claim.finished and (best is None or total < best.time_ms)
    if new_record:
        await races.save_record(conn, user_id, track.id, total, race.cls, race.build_name, [list(p) for p in claim.path])
    place = await races.place(conn, track.id, total) if claim.finished else None
    await races.finish(conn, race.id, "finished" if claim.finished else "dnf", total, claim.gates, claim.crashes,
                       medal, coins, xp)
    fresh = await users.get(conn, user_id)
    return {"finished": claim.finished, "medal": medal, "time_ms": claim.time_ms, "total_ms": total,
            "penalty_ms": total - claim.time_ms, "gates": claim.gates, "missed": claim.missed,
            "crashes": claim.crashes, "coins": coins, "xp": xp, "level_up": level_up, "wear": wear, "broken": broken,
            "new_record": new_record, "best_ms": total if new_record else (best.time_ms if best else None),
            "place": place, "training": race.training, "capped": capped, "balance": fresh.coins if fresh else 0}
