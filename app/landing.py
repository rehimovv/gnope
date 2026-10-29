"""Public landing page at the base URL (what people find on Google)."""

from __future__ import annotations

import html
import json
from pathlib import Path

from app.config import Config

TEMPLATE = Path(__file__).resolve().parent / "templates" / "landing.html"


def render_landing(config: Config, bot_username: str) -> str:
    bot_url = "https://t.me/{}".format(bot_username) if bot_username else ""
    values = {
        "BASE_URL": config.base_url + "/",
        "BOT_URL": bot_url or "#",
        "BOT_USERNAME": "@" + bot_username if bot_username else "",
        "DEV_NAME": config.developer_name,
        "DEV_URL": config.developer_url,
        "DEV_TG": config.developer_telegram,
        "SOURCE_URL": config.source_url,
    }
    page = TEMPLATE.read_text(encoding="utf-8")
    for key, value in values.items():
        page = page.replace("{{" + key + "}}", html.escape(value))
    # JSON for the redirect script (empty when the bot is not configured yet).
    return page.replace("{{BOT_URL_JSON}}", json.dumps(bot_url).replace("</", "<\\/"))
