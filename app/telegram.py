"""Minimal synchronous Telegram Bot API client built on the standard library.

Shared hosting runs the bot as a short-lived WSGI request, so a plain
blocking client is all that is needed and keeps dependencies to polib only.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, Optional
from urllib import error, request

log = logging.getLogger(__name__)

API_ROOT = "https://api.telegram.org"
TIMEOUT_SECONDS = 20


class TelegramError(Exception):
    def __init__(self, method: str, description: str, code: int = 0) -> None:
        super().__init__("{}: {}".format(method, description))
        self.method = method
        self.description = description
        self.code = code


class TelegramApi:
    def __init__(self, token: str, timeout: int = TIMEOUT_SECONDS, relay_url: str = "", relay_key: str = "") -> None:
        self._token = token
        self._timeout = timeout
        self._relay_url = relay_url
        self._relay_key = relay_key

    # -- transport ---------------------------------------------------------

    def _request(self, path: str, data: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None) -> request.Request:
        """Build a request for an API path such as '/bot<token>/getMe'.

        With a relay (relay/telegram-relay.php) the path travels in a header,
        so the token never appears in the relay host's access log.
        """
        headers = dict(headers or {})
        if self._relay_url:
            headers.update({"X-Relay-Key": self._relay_key, "X-Relay-Path": path})
            return request.Request(self._relay_url, data=data, headers=headers)
        return request.Request(API_ROOT + path, data=data, headers=headers)

    def _open(self, req: request.Request, method: str) -> Any:
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310 (fixed https host)
                body = resp.read()
        except error.HTTPError as exc:
            body = exc.read()
        except (error.URLError, OSError) as exc:
            raise TelegramError(method, "network error: {}".format(getattr(exc, "reason", exc))) from None
        try:
            payload = json.loads(body.decode("utf-8"))
        except ValueError:
            raise TelegramError(method, "invalid response") from None
        if not payload.get("ok"):
            raise TelegramError(method, payload.get("description", "unknown error"), payload.get("error_code", 0))
        return payload.get("result")

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        data = json.dumps(params or {}).encode("utf-8")
        req = self._request("/bot{}/{}".format(self._token, method), data, {"Content-Type": "application/json"})
        return self._open(req, method)

    # -- helpers -----------------------------------------------------------

    def send_message(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> int:
        params: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if reply_markup:
            params["reply_markup"] = reply_markup
        return int(self.call("sendMessage", params)["message_id"])

    def clear_keyboard(self, chat_id: int, message_id: int) -> None:
        try:
            self.call("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": message_id})
        except TelegramError as exc:
            log.debug("could not clear keyboard: %s", exc.description)

    def answer_callback(self, callback_id: str, text: Optional[str] = None, alert: bool = False) -> None:
        params: Dict[str, Any] = {"callback_query_id": callback_id}
        if text:
            params["text"] = text
            params["show_alert"] = alert
        try:
            self.call("answerCallbackQuery", params)
        except TelegramError as exc:
            log.debug("answerCallbackQuery failed: %s", exc.description)

    def send_document(self, chat_id: int, filename: str, content: bytes, caption: str = "") -> None:
        boundary = uuid.uuid4().hex
        fields = {"chat_id": str(chat_id), "caption": caption, "parse_mode": "HTML"}
        parts = []
        for name, value in fields.items():
            parts.append(
                '--{}\r\nContent-Disposition: form-data; name="{}"\r\n\r\n{}\r\n'.format(boundary, name, value).encode("utf-8")
            )
        safe_name = filename.replace('"', "").replace("\r", "").replace("\n", "")
        parts.append(
            '--{}\r\nContent-Disposition: form-data; name="document"; filename="{}"\r\n'
            "Content-Type: text/x-gettext-translation\r\n\r\n".format(boundary, safe_name).encode("utf-8")
        )
        parts.append(content)
        parts.append("\r\n--{}--\r\n".format(boundary).encode("utf-8"))
        req = self._request(
            "/bot{}/sendDocument".format(self._token),
            b"".join(parts),
            {"Content-Type": "multipart/form-data; boundary={}".format(boundary)},
        )
        self._open(req, "sendDocument")

    def download(self, file_id: str, max_bytes: int) -> bytes:
        info = self.call("getFile", {"file_id": file_id})
        if int(info.get("file_size") or 0) > max_bytes:
            raise TelegramError("getFile", "file too large")
        req = self._request("/file/bot{}/{}".format(self._token, info["file_path"]))
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                data = resp.read(max_bytes + 1)
        except error.HTTPError as exc:
            raise TelegramError("download", "HTTP {}".format(exc.code)) from None
        except (error.URLError, OSError) as exc:
            raise TelegramError("download", "network error: {}".format(getattr(exc, "reason", exc))) from None
        if len(data) > max_bytes:
            raise TelegramError("download", "file too large")
        return data
