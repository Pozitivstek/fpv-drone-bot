"""Сборка FastAPI-приложения: API под /api, мини-приложение — статикой с корня."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import routes_admin, routes_hangar, routes_items, routes_player
from app.context import AppContext
from app.services.errors import Forbidden, GameError, NotFound

log = logging.getLogger(__name__)
NO_CACHE = {"Cache-Control": "no-cache"}


def create_app(ctx: AppContext) -> FastAPI:
    dev = ctx.settings.dev_mode
    app = FastAPI(title="FPV-Drons", docs_url="/api/docs" if dev else None, redoc_url=None,
                  openapi_url="/api/openapi.json" if dev else None)
    app.state.ctx = ctx
    for module in (routes_player, routes_items, routes_hangar, routes_admin):
        app.include_router(module.router)

    @app.exception_handler(GameError)
    async def game_error(request: Request, exc: GameError) -> JSONResponse:
        code = 404 if isinstance(exc, NotFound) else 403 if isinstance(exc, Forbidden) else 400
        return JSONResponse({"detail": str(exc)}, status_code=code)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"detail": "Что-то пошло не так. Попробуйте ещё раз."}, status_code=500)

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "items": len(ctx.catalog.items), "tracks": len(ctx.catalog.tracks)}

    @app.middleware("http")
    async def revalidate_static(request: Request, call_next):
        # Мини-приложение обновляется без смены имён файлов — просим клиента сверять ETag.
        response = await call_next(request)
        if not request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-cache")
        return response

    webapp = ctx.settings.webapp_dir

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(webapp / "index.html", headers=NO_CACHE)

    if webapp.exists():
        app.mount("/", StaticFiles(directory=webapp), name="webapp")
    return app
