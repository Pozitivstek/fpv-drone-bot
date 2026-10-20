"""Тексты бота (HTML)."""

from __future__ import annotations

from html import escape

WELCOME_NEW = (
    "🚁 <b>Добро пожаловать в FPV-Drons, {name}!</b>\n\n"
    "Это игра про FPV-дроны: открывай кейсы с реальными деталями, собирай свой дрон, "
    "подбирай очки и пульт, улучшай сборку и гоняй по трассам от первого лица.\n\n"
    "🎁 В ангаре уже ждёт <b>стартовый вуп</b>, 500 монет и два ключа от кейсов.\n"
    "Жми кнопку ниже — и на взлёт!"
)
WELCOME_BACK = "🚁 <b>С возвращением, {name}!</b>\nАнгар на месте, трассы ждут. Жми кнопку ниже."
HELP = (
    "<b>Как играть</b>\n\n"
    "📦 <b>Кейсы</b> — реальные рамы, моторы, стеки, видеосистемы, пропы, батареи, очки и пульты. "
    "Шансы открыты прямо в кейсе.\n"
    "🛠 <b>Ангар</b> — собери дрон: всё должно подходить по классу (вуп, синевуп, 5\", 7\"), "
    "а очки — принимать твою видеосистему.\n"
    "🏁 <b>Гонки</b> — пилотируй сам: веди дрон пальцем через ворота. Скорость, отклик, картинка "
    "и задержка зависят от сборки. Краши изнашивают детали — чини их в ангаре.\n"
    "⚗️ <b>Мастерская</b> — апгрейд (рискни деталями ради дорогой) и контракт (5 одной редкости → 1 выше).\n"
    "🎯 Задания, ежедневный бонус и рефералы дают монеты и ключи.\n\n"
    "Команды: /profile, /daily, /promo КОД, /top, /invite"
)
NO_WEBAPP = "Мини-приложение ещё не настроено (нужен HTTPS-адрес). Загляните позже."
UNKNOWN = "Не понял 🤔 Нажмите «Играть» или наберите /help."


def name(value: str) -> str:
    return escape(value or "пилот")


def num(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def profile(data: dict) -> str:
    progress, stats = data["progress"], data["stats"]
    rank = progress["rank"]
    return "\n".join([
        f"{rank['icon']} <b>{name(data['name'])}</b> · {rank['title']}",
        f"Уровень {progress['level']} ({progress['pct']}%)",
        "",
        f"💰 Монеты: <b>{num(data['coins'])}</b>",
        f"🗝 Ключи от кейсов: {sum(data['keys'].values())}",
        f"📦 Открыто кейсов: {stats['cases_opened']}",
        f"🏁 Гонок: {stats['races']} · 🥇 золотых: {stats['golds']}",
        f"🧰 Деталей: {stats['items']} на {num(stats['collection'])} монет",
    ])


def top(rows: list[dict]) -> str:
    if not rows:
        return "Рейтинг пока пуст — станьте первым!"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = [f"{medals.get(row['place'], str(row['place']) + '.')} {row['rank']} {name(row['name'])} — ур. {row['level']}"
             for row in rows[:10]]
    return "<b>Лучшие пилоты</b>\n\n" + "\n".join(lines)
