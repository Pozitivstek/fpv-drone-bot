"""Настройки из переменных окружения (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def _bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _ids(value: str | None) -> frozenset[int]:
    parts = (part.strip() for part in (value or "").replace(";", ",").split(","))
    return frozenset(int(part) for part in parts if part.lstrip("-").isdigit())


@dataclass(frozen=True)
class Settings:
    bot_token: str
    webapp_url: str
    db_path: Path
    data_dir: Path
    webapp_dir: Path
    host: str
    port: int
    dev_mode: bool
    dev_user_id: int
    init_data_ttl: int
    admin_ids: frozenset[int]
    bot_username: str = ""

    @property
    def bot_enabled(self) -> bool:
        return bool(self.bot_token)

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    db_path = Path(os.getenv("DB_PATH", str(ROOT / "storage" / "fpv.db")))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        webapp_url=os.getenv("WEBAPP_URL", "").strip().rstrip("/") + "/",
        db_path=db_path,
        data_dir=Path(os.getenv("DATA_DIR", str(ROOT / "data"))),
        webapp_dir=Path(os.getenv("WEBAPP_DIR", str(ROOT / "webapp"))),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        dev_mode=_bool(os.getenv("DEV_MODE")),
        dev_user_id=int(os.getenv("DEV_USER_ID", "1")),
        init_data_ttl=int(os.getenv("INIT_DATA_TTL", str(24 * 3600))),
        admin_ids=_ids(os.getenv("ADMIN_IDS")),
        bot_username=os.getenv("BOT_USERNAME", "").strip().lstrip("@"),
    )
