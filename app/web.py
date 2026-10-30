"""WSGI entry: the landing page and the Telegram webhook.

  GET  {base}/          landing page (also registers the webhook on first visit)
  POST {base}/webhook   Telegram updates, authenticated by the secret header
  GET  {base}/health    plain "ok" for monitoring
"""

from __future__ import annotations

import hmac
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

from app import bootstrap, maintenance
from app.bot.context import Deps
from app.bot.router import dispatch
from app.config import Config, load
from app.files import FileStore
from app.landing import render_landing
from app.storage import Store
from app.telegram import TelegramApi

log = logging.getLogger("app")

MAX_BODY_BYTES = 1024 * 1024
SECRET_HEADER = "HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN"

StartResponse = Callable[[str, List[Tuple[str, str]]], None]


def _setup_logging(data_dir: Path) -> None:
    if log.handlers:
        return
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(str(data_dir / "logs" / "bot.log"), maxBytes=512 * 1024, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


class App:
    def __init__(self, config: Config, api: Optional[TelegramApi] = None) -> None:
        self.config = config
        config.data_dir.mkdir(parents=True, exist_ok=True)
        _setup_logging(config.data_dir)
        self.deps = Deps(
            api=api or TelegramApi(config.bot_token, relay_url=config.relay_url, relay_key=config.relay_key),
            store=Store(config.data_dir / "bot.db"),
            files=FileStore(config.data_dir),
            config=config,
        )

    def _path(self, environ: dict) -> str:
        path = environ.get("PATH_INFO") or "/"
        base = self.config.base_path
        if base and (path == base or path.startswith(base + "/")):
            path = path[len(base):]
        return "/" + path.strip("/")

    def __call__(self, environ: dict, start_response: StartResponse) -> Iterable[bytes]:
        path = self._path(environ)
        method = environ.get("REQUEST_METHOD", "GET").upper()
        if path == "/webhook" and method == "POST":
            return self._webhook(environ, start_response)
        if path == "/health" and method in ("GET", "HEAD"):
            return _respond(start_response, "200 OK", b"ok", "text/plain; charset=utf-8")
        if path == "/" and method in ("GET", "HEAD"):
            return self._landing(start_response, method == "HEAD")
        return _respond(start_response, "404 Not Found", b"not found", "text/plain; charset=utf-8")

    def _landing(self, start_response: StartResponse, head_only: bool) -> Iterable[bytes]:
        state = bootstrap.ensure_setup(self.config, self.deps.api)
        body = render_landing(self.config, state.get("username", "")).encode("utf-8")
        return _respond(start_response, "200 OK", b"" if head_only else body, "text/html; charset=utf-8",
                        [("Cache-Control", "public, max-age=600")])

    def _webhook(self, environ: dict, start_response: StartResponse) -> Iterable[bytes]:
        if not self.config.bot_token:
            return _respond(start_response, "503 Service Unavailable", b"not configured", "text/plain")
        given = environ.get(SECRET_HEADER, "").encode("utf-8", "replace")
        expected = bootstrap.webhook_secret(self.config).encode("ascii")
        if not given or not hmac.compare_digest(given, expected):
            return _respond(start_response, "403 Forbidden", b"forbidden", "text/plain")
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            return _respond(start_response, "400 Bad Request", b"bad request", "text/plain")
        try:
            update = json.loads(environ["wsgi.input"].read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return _respond(start_response, "400 Bad Request", b"bad request", "text/plain")
        if not isinstance(update, dict):
            return _respond(start_response, "400 Bad Request", b"bad request", "text/plain")

        update_id = update.get("update_id")
        if isinstance(update_id, int) and self.deps.store.claim_update(update_id):
            try:
                dispatch(update, self.deps)
            except Exception:  # noqa: BLE001 - one bad update must not stop Telegram's queue
                log.exception("update %s failed", update_id)
                _apologize(self.deps, update)
            try:
                maintenance.maybe_cleanup(self.config, self.deps.store, self.deps.files)
            except OSError:
                log.exception("cleanup failed")
        # Always 200 so Telegram does not retry an update we already handled.
        return _respond(start_response, "200 OK", b"ok", "text/plain")


def _apologize(deps: Deps, update: dict) -> None:
    message = update.get("message") or (update.get("callback_query") or {}).get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    if not chat_id:
        return
    try:
        deps.api.send_message(chat_id, "⚠️ Something went wrong. Please try again, or send /continue.")
    except Exception:  # noqa: BLE001
        log.exception("could not send apology")


def _respond(start_response: StartResponse, status: str, body: bytes, content_type: str,
             extra: Optional[List[Tuple[str, str]]] = None) -> Iterable[bytes]:
    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("X-Content-Type-Options", "nosniff"),
    ] + (extra or [])
    start_response(status, headers)
    return [body]


def create_app(config: Optional[Config] = None) -> App:
    return App(config or load())
