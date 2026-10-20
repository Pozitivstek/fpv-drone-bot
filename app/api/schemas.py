"""Тела запросов. Ограничения длины и диапазонов — здесь, чтобы мусор не доходил до сервисов."""

from __future__ import annotations

from typing import Annotated

from fastapi import Path as FastPath
from pydantic import BaseModel, Field

MAX_ID = 2**62
Uid = Annotated[int, Field(ge=1, le=MAX_ID)]
UidList = list[Uid]
Finite = Annotated[float, Field(allow_inf_nan=False)]
PathPoint = Annotated[list[Finite], Field(min_length=4, max_length=4)]
IdPath = Annotated[int, FastPath(ge=1, le=MAX_ID)]


class OpenCase(BaseModel):
    count: int = Field(default=1, ge=1, le=5)
    use_keys: bool = False


class Uids(BaseModel):
    uids: UidList = Field(min_length=1, max_length=200)


class SellBulk(BaseModel):
    max_rarity: str = Field(max_length=16)


class Buy(BaseModel):
    item_id: str = Field(max_length=64)
    qty: int = Field(default=1, ge=1, le=10)


class Upgrade(BaseModel):
    uids: UidList = Field(min_length=1, max_length=6)
    target: str = Field(max_length=64)


class Contract(BaseModel):
    uids: UidList = Field(min_length=5, max_length=5)


class Name(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class Slot(BaseModel):
    uid: Uid | None = None


class Promo(BaseModel):
    code: str = Field(min_length=1, max_length=40)


class RaceStart(BaseModel):
    track_id: str = Field(max_length=32)
    training: bool = False


class RaceFinish(BaseModel):
    finished: bool
    time_ms: int = Field(ge=0, le=3_600_000)
    gates: int = Field(ge=0, le=1000)
    missed: int = Field(ge=0, le=1000)
    crashes: int = Field(ge=0, le=1000)
    path: list[PathPoint] = Field(default_factory=list, max_length=2400)


class CoinsDelta(BaseModel):
    delta: int = Field(ge=-10_000_000, le=10_000_000)


class Level(BaseModel):
    level: int = Field(ge=-1000, le=1000)


class RankIndex(BaseModel):
    rank: int = Field(ge=-1000, le=1000)


class Luck(BaseModel):
    luck: Finite


class Ban(BaseModel):
    banned: bool


class GiveReward(BaseModel):
    coins: int = Field(default=0, ge=-MAX_ID, le=MAX_ID)
    xp: int = Field(default=0, ge=-MAX_ID, le=MAX_ID)
    items: list[str] = Field(default_factory=list, max_length=50)
    keys: dict[str, Annotated[int, Field(ge=-1000, le=1000)]] = Field(default_factory=dict, max_length=20)
    kits: list[str] = Field(default_factory=list, max_length=10)


class PromoCreate(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    reward: GiveReward
    max_uses: int = Field(default=0, ge=0, le=MAX_ID)
    days: int | None = Field(default=None, ge=-1000, le=100_000)
    note: str = Field(default="", max_length=120)


class PromoToggle(BaseModel):
    active: bool


class Event(BaseModel):
    key: str = Field(max_length=32)
    value: Finite


class Broadcast(BaseModel):
    text: str = Field(min_length=1, max_length=3500)
