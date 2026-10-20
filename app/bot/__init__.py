"""Создание бота aiogram, кнопка меню мини-приложения и отправка уведомлений игрокам."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from app.bot.handlers import build_router, open_button
from app.context import AppContext

log = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="start", description="Запустить игру"),
    BotCommand(command="play", description="Открыть мини-приложение"),
    BotCommand(command="profile", description="Мой профиль"),
    BotCommand(command="daily", description="Ежедневный бонус"),
    BotCommand(command="promo", description="Ввести промокод"),
    BotCommand(command="top", description="Лучшие пилоты"),
    BotCommand(command="invite", description="Пригласить друга"),
    BotCommand(command="help", description="Как играть"),
]


def build_bot(ctx: AppContext) -> tuple[Bot, Dispatcher]:
    bot = Bot(ctx.settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(ctx))

    async def notify(chat_id: int, text: str, button: str | None) -> None:
        markup = open_button(ctx, button) if button else None
        try:
            await bot.send_message(chat_id, text, reply_markup=markup)
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            await bot.send_message(chat_id, text, reply_markup=markup)

    ctx.notifier = notify
    return bot, dispatcher


async def configure(bot: Bot, webapp_url: str) -> str:
    """Команды и кнопка «Играть» рядом с полем ввода. Возвращает username бота."""
    await bot.set_my_commands(COMMANDS)
    if webapp_url.startswith("https://"):
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="🚁 Играть", web_app=WebAppInfo(url=webapp_url)))
    else:
        log.warning("WEBAPP_URL не https — кнопку меню мини-приложения не ставлю")
    me = await bot.get_me()
    return me.username or ""
