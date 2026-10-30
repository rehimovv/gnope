"""Registers the webhook, commands and descriptions with Telegram.

Runs automatically the first time the landing page is opened (and again
whenever SETUP_VERSION changes), so deploying needs no shell access.
It can also be run by hand:  python -m app.bootstrap
or from cron, retrying until Telegram accepts it:  python -m app.bootstrap --if-needed
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict

from app.config import Config, load
from app.i18n import N_, UI_LANGUAGES, tr
from app.telegram import TelegramApi, TelegramError

log = logging.getLogger(__name__)

SETUP_VERSION = 1
RETRY_AFTER_SECONDS = 300

COMMANDS = [
    ("start", N_("Start and choose the language")),
    ("continue", N_("Show the current string again")),
    ("status", N_("Progress of the current file")),
    ("save", N_("Get the translated file now")),
    ("cancel", N_("Close the current file")),
    ("profile", N_("Your name and email for the header")),
    ("language", N_("Change the interface language")),
    ("help", N_("How to use the bot")),
    ("about", N_("About this bot")),
]
DESCRIPTION = N_(
    "Translate gettext .po files for GNOME and other open source projects right in Telegram. "
    "Send a .po file, translate it string by string and get the finished file back. "
    "Free and open source, made by a volunteer to support the GNOME translation community."
)
SHORT_DESCRIPTION = N_("Translate GNOME .po files right in Telegram. Free and open source.")


def secret_path(config: Config) -> Path:
    return config.data_dir / "webhook_secret"


def webhook_secret(config: Config) -> str:
    """Secret Telegram sends with every webhook request; created on first use."""
    path = secret_path(config)
    if path.is_file():
        return path.read_text(encoding="ascii").strip()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("{}.{}".format(path.name, secrets.token_hex(4)))
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(secrets.token_urlsafe(48))
    try:
        # link() fails if another request created the secret first; theirs wins.
        os.link(str(tmp), str(path))
    except FileExistsError:
        pass
    finally:
        tmp.unlink()
    return path.read_text(encoding="ascii").strip()


def _state_path(config: Config) -> Path:
    return config.data_dir / "setup.json"


def read_state(config: Config) -> Dict[str, Any]:
    try:
        return json.loads(_state_path(config).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_state(config: Config, state: Dict[str, Any]) -> None:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    _state_path(config).write_text(json.dumps(state, indent=2), encoding="utf-8")


def _register(config: Config, api: TelegramApi) -> Dict[str, Any]:
    me = api.call("getMe")
    webhook: Dict[str, Any] = {
        "url": config.webhook_url,
        "secret_token": webhook_secret(config),
        "allowed_updates": ["message", "callback_query"],
        "max_connections": 10,
    }
    if config.webhook_ip and not config.relay_url:
        # Lets Telegram skip DNS, for hosts whose nameservers answer slowly.
        webhook["ip_address"] = config.webhook_ip
    api.call("setWebhook", webhook)
    for code in UI_LANGUAGES:
        scope = {} if code == "en" else {"language_code": code}
        api.call("setMyCommands", dict(scope, commands=[
            {"command": name, "description": tr(code, text)} for name, text in COMMANDS
        ]))
        api.call("setMyDescription", dict(scope, description=tr(code, DESCRIPTION)))
        api.call("setMyShortDescription", dict(scope, short_description=tr(code, SHORT_DESCRIPTION)))
    return {
        "version": SETUP_VERSION,
        "webhook_url": config.webhook_url,
        "webhook_ip": config.webhook_ip,
        "username": me.get("username", ""),
    }


def ensure_setup(config: Config, api: TelegramApi, force: bool = False) -> Dict[str, Any]:
    state = read_state(config)
    current = (
        state.get("version") == SETUP_VERSION
        and state.get("webhook_url") == config.webhook_url
        and state.get("webhook_ip", "") == config.webhook_ip
    )
    if not config.bot_token or (current and not force):
        return state
    if not force and time.time() - state.get("last_attempt", 0) < RETRY_AFTER_SECONDS:
        return state
    try:
        new_state = _register(config, api)
    except TelegramError as exc:
        log.error("Telegram setup failed: %s", exc)
        failed = dict(state, last_attempt=time.time(), error=exc.description)
        _write_state(config, failed)
        return failed
    _write_state(config, new_state)
    log.info("Telegram webhook registered for @%s", new_state["username"])
    return new_state


if __name__ == "__main__":  # pragma: no cover - manual use on the server
    logging.basicConfig(level=logging.INFO)
    import sys

    cfg = load()
    # --if-needed (for cron): no-op once registered, retries after failures.
    api = TelegramApi(cfg.bot_token, relay_url=cfg.relay_url, relay_key=cfg.relay_key)
    result = ensure_setup(cfg, api, force="--if-needed" not in sys.argv)
    print(json.dumps({k: v for k, v in result.items() if k != "secret"}, indent=2))  # noqa: T201
