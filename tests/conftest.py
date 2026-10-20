"""Общие фикстуры: каталог, временная БД, контекст с фальшивым ботом, ASGI-клиент."""

from __future__ import annotations

import dataclasses
import json
import random
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest

from app.api import create_app
from app.api.auth import sign
from app.api.deps import LIMITERS
from app.catalog import Catalog
from app.config import Settings
from app.context import AppContext
from app.db import connect

ROOT = Path(__file__).resolve().parent.parent
BOT_TOKEN = "123456:TEST-TOKEN"
PLAYER = 42
ADMIN = 900


def make_settings(tmp_path: Path, dev_user: int = PLAYER) -> Settings:
    return Settings(bot_token=BOT_TOKEN, webapp_url="https://example.test/", db_path=tmp_path / "test.db",
                    data_dir=ROOT / "data", webapp_dir=ROOT / "webapp", host="127.0.0.1", port=0, dev_mode=True,
                    dev_user_id=dev_user, init_data_ttl=3600, admin_ids=frozenset({ADMIN}), bot_username="fpvtestbot")


def init_data(user_id: int, first_name: str = "Тест", start_param: str | None = None, token: str = BOT_TOKEN) -> str:
    fields = {"auth_date": str(int(time.time())), "user": json.dumps({"id": user_id, "first_name": first_name})}
    if start_param:
        fields["start_param"] = start_param
    return urlencode({**fields, "hash": sign(fields, token)})


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return Catalog.from_dir(ROOT / "data")


@pytest.fixture(autouse=True)
def reset_limiters():
    for limiter in LIMITERS.values():
        limiter.clear()
    from app.services.promo import FAILED_ATTEMPTS
    FAILED_ATTEMPTS.clear()
    from app.services import social
    social.CACHE.clear()


@pytest.fixture
async def db(tmp_path):
    database = await connect(tmp_path / "test.db")
    yield database
    await database.close()


@pytest.fixture
async def ctx(tmp_path, db, catalog) -> AppContext:
    sent: list[tuple[int, str]] = []

    async def notifier(chat_id: int, text: str, button: str | None) -> None:
        sent.append((chat_id, text))

    context = AppContext(settings=make_settings(tmp_path), db=db, catalog=catalog, rng=random.Random(7),
                         notifier=notifier)
    context.sent = sent  # type: ignore[attr-defined]
    return context


def act_as(ctx: AppContext, user_id: int) -> None:
    """Переключает dev-пользователя (запросы без initData идут от его имени)."""
    ctx.settings = dataclasses.replace(ctx.settings, dev_user_id=user_id)


@pytest.fixture
async def client(ctx):
    app = create_app(ctx)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        yield http


@pytest.fixture
async def admin(ctx, client):
    """Клиент от имени администратора (игрок PLAYER тоже зарегистрирован)."""
    assert (await client.get("/api/me")).status_code == 200
    act_as(ctx, ADMIN)
    assert (await client.get("/api/me")).status_code == 200
    return client


async def ok(response: httpx.Response) -> dict | list:
    assert response.status_code == 200, response.text
    return response.json()


async def fail(response: httpx.Response, status: int = 400) -> str:
    assert response.status_code == status, response.text
    return response.json()["detail"]
