"""Точка входа: API + мини-приложение (uvicorn) и бот (long polling) в одном процессе."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import signal

import uvicorn

from app.api import create_app
from app.catalog import Catalog
from app.config import load_settings
from app.context import AppContext
from app.db import connect

log = logging.getLogger("fpv")


async def build_context() -> AppContext:
    settings = load_settings()
    if settings.dev_mode and settings.webapp_url.startswith("https://"):
        raise SystemExit("DEV_MODE=1 пускает без авторизации — на публичном HTTPS-адресе его включать нельзя")
    return AppContext(settings=settings, db=await connect(settings.db_path), catalog=Catalog.from_dir(settings.data_dir))


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", force=True)
    ctx = await build_context()
    log.info("catalog: %d items, %d cases, %d tracks", len(ctx.catalog.items), len(ctx.catalog.cases),
             len(ctx.catalog.tracks))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    tasks = []
    bot = None
    if ctx.settings.bot_enabled:
        from app.bot import build_bot, configure

        bot, dispatcher = build_bot(ctx)
        try:
            username = await configure(bot, ctx.settings.webapp_url)
            if username and not ctx.settings.bot_username:
                ctx.settings = dataclasses.replace(ctx.settings, bot_username=username)
        except Exception:
            log.exception("bot configure failed (продолжаю без кнопки меню)")
        tasks.append(asyncio.create_task(dispatcher.start_polling(bot, handle_signals=False)))
    else:
        log.warning("BOT_TOKEN не задан — работает только API")

    server = uvicorn.Server(uvicorn.Config(create_app(ctx), host=ctx.settings.host, port=ctx.settings.port,
                                           log_level="info", proxy_headers=True, forwarded_allow_ips="*"))
    server.install_signal_handlers = lambda: None
    tasks.append(asyncio.create_task(server.serve()))
    await stop.wait()
    log.info("shutting down")
    server.should_exit = True
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    if bot:
        await bot.session.close()
    await ctx.db.close()


if __name__ == "__main__":
    asyncio.run(main())
