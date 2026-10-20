"""Бот: команды через фейковую сессию aiogram (без сети), тексты и настройка меню."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import GetMe, SendMessage
from aiogram.types import Chat, Message, Update, User

from app.bot import build_bot, configure, texts
from app.bot.handlers import build_router, open_button
from app.services import promo
from app.store import users
from tests.conftest import ADMIN, BOT_TOKEN, PLAYER


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.sent: list[SendMessage] = []
        self.calls: list = []

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage):
            self.sent.append(method)
            return Message(message_id=len(self.sent), date=datetime.now(timezone.utc),
                           chat=Chat(id=method.chat_id, type="private"), text=method.text)
        if isinstance(method, GetMe):
            return User(id=1, is_bot=True, first_name="FPV", username="fpvdronsplaybot")
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover - не используется
        yield b""

    async def close(self):
        return None


@pytest.fixture
def telegram(ctx):
    session = FakeSession()
    bot = Bot(BOT_TOKEN, session=session)
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(ctx))
    counter = {"n": 0}

    async def send(text: str, user_id: int = PLAYER) -> str:
        counter["n"] += 1
        message = Message(message_id=counter["n"], date=datetime.now(timezone.utc), chat=Chat(id=user_id, type="private"),
                          from_user=User(id=user_id, is_bot=False, first_name="Тест"), text=text)
        before = len(session.sent)
        await dispatcher.feed_update(bot, Update(update_id=counter["n"], message=message))
        return "\n".join(method.text for method in session.sent[before:])

    return send


async def test_start_registers_with_referral(telegram, ctx):
    assert "Добро пожаловать" in await telegram("/start", ADMIN)
    assert "Добро пожаловать" in await telegram(f"/start ref_{ADMIN}")
    assert (await users.get(ctx.db.conn, PLAYER)).referrer_id == ADMIN
    assert "С возвращением" in await telegram("/start")


async def test_profile_daily_top_invite_help(telegram):
    await telegram("/start")
    assert "Монеты" in await telegram("/profile")
    assert "+100 монет" in await telegram("/daily")
    assert "уже получен" in await telegram("/daily")
    assert "Лучшие пилоты" in await telegram("/top")
    assert "start=ref_42" in await telegram("/invite")
    assert "Как играть" in await telegram("/help")
    assert "Ангар открыт" in await telegram("/play")
    assert "Не понял" in await telegram("просто текст")


async def test_promo_command(telegram, ctx):
    await telegram("/start")
    assert "Введите код" in await telegram("/promo")
    assert "нет" in await telegram("/promo NOPE1")
    await promo.create(ctx, ADMIN, "BOTCODE", {"coins": 77}, 0, None)
    assert "активирован" in await telegram("/promo botcode")


async def test_admin_commands(telegram, ctx):
    await telegram("/start")
    assert "Не понял" in await telegram("/admin")
    assert "Не понял" in await telegram("/give 42 100")
    assert "Админка" in await telegram("/admin", ADMIN)
    assert "Формат" in await telegram("/give abc", ADMIN)
    assert "+100" in await telegram(f"/give {PLAYER} 100", ADMIN)
    assert "❌" in await telegram("/give 123 100", ADMIN)
    assert (await users.get(ctx.db.conn, PLAYER)).coins == 600


async def test_banned_player_cannot_claim_daily(telegram, ctx):
    await telegram("/start")
    async with ctx.db.tx() as conn:
        await users.update(conn, PLAYER, banned=1)
    assert "заблокирован" in await telegram("/daily")


async def test_configure_and_notifier(ctx):
    session = FakeSession()
    bot = Bot(BOT_TOKEN, session=session)
    assert await configure(bot, "https://example.test/") == "fpvdronsplaybot"
    assert await configure(bot, "http://insecure/") == "fpvdronsplaybot"
    real_bot, _ = build_bot(ctx)
    real_bot.session = session
    await ctx.notifier(PLAYER, "привет", "Играть")
    assert session.sent[-1].text == "привет" and session.sent[-1].reply_markup is not None


def test_texts_and_button(ctx):
    assert open_button(ctx) is not None
    profile = {"name": "<b>x</b>", "coins": 12345, "keys": {"starter": 2},
               "progress": {"level": 3, "pct": 40, "rank": {"icon": "🛫", "title": "Первый взлёт"}},
               "stats": {"cases_opened": 1, "races": 2, "golds": 0, "items": 9, "collection": 1500}}
    rendered = texts.profile(profile)
    assert "&lt;b&gt;" in rendered and "12 345" in rendered
    assert texts.top([]).startswith("Рейтинг пока пуст")
