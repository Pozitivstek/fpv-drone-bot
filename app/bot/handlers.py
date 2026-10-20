"""Обработчики команд бота. Вся игровая логика — в сервисах, здесь только Telegram-обвязка."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from app.bot import texts
from app.context import AppContext
from app.services import admin, players, progress, promo, social
from app.services.errors import GameError
from app.services.rewards import REF_STAGES
from app.store import users

log = logging.getLogger(__name__)


def open_button(ctx: AppContext, label: str = "🚁 Играть", path: str = "") -> InlineKeyboardMarkup | None:
    url = ctx.settings.webapp_url
    if not url.startswith("https://"):
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, web_app=WebAppInfo(url=url + path))]])


def build_router(ctx: AppContext) -> Router:
    router = Router()

    async def player(message: Message, start_param: str | None = None):
        sender = message.from_user
        assert sender is not None
        return await players.ensure(ctx, sender.id, sender.first_name or "", sender.username or "", start_param)

    @router.message(CommandStart())
    async def start(message: Message, command: CommandObject) -> None:
        sender = message.from_user
        if sender is None:
            return
        existed = await users.get(ctx.db.conn, sender.id) is not None
        user = await player(message, command.args)
        template = texts.WELCOME_BACK if existed else texts.WELCOME_NEW
        markup = open_button(ctx)
        await message.answer(template.format(name=texts.name(user.display_name)) + ("" if markup else
                             "\n\n" + texts.NO_WEBAPP), reply_markup=markup)

    @router.message(Command("play"))
    async def play(message: Message) -> None:
        await player(message)
        markup = open_button(ctx)
        await message.answer("Ангар открыт 👇" if markup else texts.NO_WEBAPP, reply_markup=markup)

    @router.message(Command("help"))
    async def help_(message: Message) -> None:
        await message.answer(texts.HELP, reply_markup=open_button(ctx))

    @router.message(Command("profile"))
    async def profile(message: Message) -> None:
        user = await player(message)
        await message.answer(texts.profile(await players.profile(ctx, user)), reply_markup=open_button(ctx))

    @router.message(Command("daily"))
    async def daily(message: Message) -> None:
        user = await player(message)
        try:
            players.require_active(user)
            result = await progress.claim_daily(ctx, user.id)
        except GameError as exc:
            await message.answer(f"⏳ {exc}")
            return
        keys = ", ".join(f"ключ «{ctx.catalog.cases[k].name}» ×{q}" for k, q in result["keys"].items())
        await message.answer(f"🎁 День {result['streak']} серии: +{result['coins']} монет" + (f", {keys}" if keys else ""),
                             reply_markup=open_button(ctx))

    @router.message(Command("promo"))
    async def redeem(message: Message, command: CommandObject) -> None:
        user = await player(message)
        if not command.args:
            await message.answer("Введите код так: <code>/promo КОД</code>")
            return
        try:
            result = await promo.redeem(ctx, user.id, command.args)
        except GameError as exc:
            await message.answer(f"❌ {exc}")
            return
        await message.answer(f"✅ Промокод <b>{result['code']}</b> активирован: {texts.name(result['text'])}",
                             reply_markup=open_button(ctx))

    @router.message(Command("top"))
    async def top(message: Message) -> None:
        await player(message)
        await message.answer(texts.top(await social.leaderboard(ctx, "level")))

    @router.message(Command("invite"))
    async def invite(message: Message) -> None:
        user = await player(message)
        link = players.ref_link(ctx, user.id)
        stages = ", ".join(f"+{coins} на {level} уровне" for level, coins in REF_STAGES)
        await message.answer(f"🤝 Зовите друзей! Другу +{players.NEW_PLAYER_REF_BONUS} монет на старте, вам — "
                             f"когда друг подрастёт: {stages}.\n\n{link}")

    @router.message(Command("admin"))
    async def admin_panel(message: Message) -> None:
        user = await player(message)
        if not ctx.settings.is_admin(user.id):
            await message.answer(texts.UNKNOWN)
            return
        data = await admin.stats(ctx)
        await message.answer(
            f"🛡 <b>Админка</b>\nИгроков: {data['users']} (за сутки активны {data['active_24h']}, новых {data['new_24h']})\n"
            f"Гонок за сутки: {data['races_24h']} · редких дропов: {data['rare_drops_24h']}\n"
            f"Удача ×{data['events']['luck_event']} · награды за гонки ×{data['events']['race_mult']}\n\n"
            "Быстро: <code>/give ID монеты</code>", reply_markup=open_button(ctx, "🛡 Открыть админку", "#/admin"))

    @router.message(Command("give"))
    async def give(message: Message, command: CommandObject) -> None:
        user = await player(message)
        if not ctx.settings.is_admin(user.id):
            await message.answer(texts.UNKNOWN)
            return
        parts = (command.args or "").split()
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].lstrip("-").isdigit():
            await message.answer("Формат: <code>/give ID монеты</code>")
            return
        try:
            result = await admin.adjust_coins(ctx, user.id, int(parts[0]), int(parts[1]))
        except GameError as exc:
            await message.answer(f"❌ {exc}")
            return
        await message.answer(f"✅ Игроку {parts[0]}: {result['applied']:+} монет")

    @router.message(F.text)
    async def fallback(message: Message) -> None:
        await message.answer(texts.UNKNOWN, reply_markup=open_button(ctx))

    return router
