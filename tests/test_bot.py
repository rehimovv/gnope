"""End-to-end conversations through the WSGI app with a fake Telegram API."""

import io
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from app import bootstrap
from app.config import load
from app.i18n import tr
from app.po.document import PoDocument
from app.web import App

FIXTURES = Path(__file__).parent / "fixtures"
USER = 1001


class FakeApi:
    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []
        self.documents: List[Dict[str, Any]] = []
        self.calls: List[str] = []
        self.files: Dict[str, bytes] = {}
        self._next_id = 100

    def send_message(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> int:
        self._next_id += 1
        self.messages.append({"chat_id": chat_id, "text": text, "markup": reply_markup, "id": self._next_id})
        return self._next_id

    def clear_keyboard(self, chat_id: int, message_id: int) -> None:
        self.calls.append("clear:{}".format(message_id))

    def answer_callback(self, callback_id: str, text: Optional[str] = None, alert: bool = False) -> None:
        self.calls.append("answer")

    def send_document(self, chat_id: int, filename: str, content: bytes, caption: str = "") -> None:
        self.documents.append({"name": filename, "content": content, "caption": caption})

    def download(self, file_id: str, max_bytes: int) -> bytes:
        return self.files[file_id]

    def call(self, method: str, params: Optional[dict] = None) -> Any:
        self.calls.append(method)
        return {"username": "GnomePoBot"} if method == "getMe" else True

    # helpers for assertions
    @property
    def last(self) -> Dict[str, Any]:
        return self.messages[-1]

    def buttons(self, message: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        markup = (message or self.last)["markup"] or {"inline_keyboard": []}
        return {b["text"]: b.get("callback_data", "") for row in markup["inline_keyboard"] for b in row}


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("BOT_TOKEN=123:test\nBASE_URL=https://example.org/tools/poeditor\n")
        self.config = load(tmp_path, environ={})
        self.api = FakeApi()
        self.app = App(self.config, api=self.api)  # type: ignore[arg-type]
        self.secret = bootstrap.webhook_secret(self.config)
        self.update_id = 0

    def request(self, method: str, path: str, body: bytes = b"", headers: Optional[dict] = None):
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
        }
        environ.update(headers or {})
        status: List[str] = []
        result = b"".join(self.app(environ, lambda s, h: status.append(s)))
        return status[0], result

    def post(self, update: dict, secret: Optional[str] = None) -> str:
        self.update_id += 1
        update = dict(update, update_id=self.update_id)
        status, _ = self.request(
            "POST", "/tools/poeditor/webhook", json.dumps(update).encode(),
            {"HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": self.secret if secret is None else secret},
        )
        return status

    def text(self, text: str) -> None:
        self.post({"message": {"message_id": 1, "from": {"id": USER}, "chat": {"id": USER, "type": "private"}, "text": text}})

    def tap(self, data: str) -> None:
        self.post({"callback_query": {"id": "cb", "from": {"id": USER}, "data": data,
                                      "message": {"message_id": 5, "chat": {"id": USER, "type": "private"}}}})

    def upload(self, name: str, data: bytes) -> None:
        self.api.files[name] = data
        self.post({"message": {"message_id": 2, "from": {"id": USER}, "chat": {"id": USER, "type": "private"},
                               "document": {"file_id": name, "file_name": name, "file_size": len(data)}}})


@pytest.fixture
def bot(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


def onboard(bot: Harness, lang: str = "en") -> None:
    bot.text("/start")
    bot.tap("ui:" + lang)
    bot.text("Ramal Rahimov")
    bot.text("ramal@example.org")


def test_webhook_rejects_wrong_secret_and_bad_bodies(bot):
    assert bot.post({"message": {}}, secret="nope").startswith("403")
    assert bot.post({"message": {}}, secret="").startswith("403")
    status, _ = bot.request("POST", "/tools/poeditor/webhook", b"{not json",
                            {"HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": bot.secret})
    assert status.startswith("400")
    assert bot.request("GET", "/tools/poeditor/nope")[0].startswith("404")
    assert bot.request("GET", "/tools/poeditor/health") == ("200 OK", b"ok")


def test_landing_page_registers_webhook_once(bot):
    status, body = bot.request("GET", "/tools/poeditor/")
    assert status == "200 OK"
    assert b"https://t.me/GnomePoBot" in body and b"Ramal Rahimov" in body
    assert "setWebhook" in bot.api.calls
    bot.api.calls.clear()
    bot.request("GET", "/tools/poeditor")
    assert "setWebhook" not in bot.api.calls


def test_duplicate_updates_are_processed_once(bot):
    update = {"update_id": 77, "message": {"message_id": 1, "from": {"id": USER},
                                           "chat": {"id": USER, "type": "private"}, "text": "/start"}}
    body = json.dumps(update).encode()
    headers = {"HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": bot.secret}
    bot.request("POST", "/tools/poeditor/webhook", body, headers)
    bot.request("POST", "/tools/poeditor/webhook", body, headers)
    assert len(bot.api.messages) == 1


def test_first_contact_is_english_with_language_choice(bot):
    bot.text("hello")
    assert "Welcome to <b>GNOME PO Translator</b>" in bot.api.last["text"]
    assert set(bot.api.buttons().values()) == {"ui:en", "ui:tr", "ui:az"}


def test_full_translation_flow_in_azerbaijani(bot):
    onboard(bot, "az")
    assert tr("az", "Now send me a .po or .pot file to start translating.") in bot.api.last["text"]

    bot.upload("gnome-sample.main.az.po", (FIXTURES / "sample.az.po").read_bytes())
    assert "gnome-sample.main.az.po" in bot.api.last["text"]
    assert "mode:u" in bot.api.buttons().values()

    bot.tap("mode:u")
    assert "_Undo %s" in bot.api.last["text"]
    bot.text("Geri al %s")  # missing accelerator -> warning
    assert "warn:keep:0" in bot.api.buttons().values()
    bot.text("_Geri al %s")  # a new message counts as a correction

    assert "Deleted %d file" in bot.api.last["text"]
    bot.text("%d fayl silindi")          # form 1
    bot.text("%d fayl silindi")          # form 2
    assert "This is a long description" in bot.api.last["text"]
    bot.text("Uzun təsvir")             # newline is mirrored from the source
    bot.tap("nav:skip:3")               # skip markup string
    assert tr("az", "You reached the end of this list. Here is your file:") in bot.api.messages[-2]["text"]

    out = bot.api.documents[-1]
    assert out["name"] == "gnome-sample.main.az.po"
    text = out["content"].decode("utf-8")
    assert 'msgstr "_Geri al %s"' in text
    assert 'msgstr[1] "%d fayl silindi"' in text
    assert 'msgstr "Uzun təsvir\\n"' in text
    assert "Last-Translator: Ramal Rahimov <ramal@example.org>" in text
    doc = PoDocument.from_bytes(out["content"])
    assert doc.stats().untranslated == 1


def test_format_error_blocks_the_translation(bot):
    onboard(bot)
    bot.upload("x.az.po", (FIXTURES / "sample.az.po").read_bytes())
    bot.tap("mode:f")
    assert "Could not open the file" in bot.api.last["text"]
    assert "nav:ok:0" in bot.api.buttons().values()
    bot.text("fayl açılmadı")  # %s missing
    assert "This translation would break the file" in bot.api.last["text"]
    bot.tap("nav:ok:0")  # approve the existing fuzzy translation instead
    assert bot.api.documents  # end of the fuzzy list -> file sent


def test_pot_upload_asks_language_and_names_output(bot):
    onboard(bot)
    bot.upload("gnome-sample.main.pot", (FIXTURES / "sample.pot").read_bytes())
    assert "language code" in bot.api.last["text"]
    bot.text("not a language")
    assert "not a language code" in bot.api.last["text"]
    bot.text("tr")
    bot.tap("mode:u")
    bot.text("Örnek")
    bot.text("%d öğe")  # Turkish has one plural form
    out = bot.api.documents[-1]
    assert out["name"] == "gnome-sample.main.tr.po"
    text = out["content"].decode("utf-8")
    assert "Plural-Forms: nplurals=1; plural=0;" in text
    assert 'msgstr[0] "%d öğe"' in text


def test_upload_before_profile_resumes_after_profile(bot):
    bot.text("/start")
    bot.tap("ui:en")
    bot.upload("a.az.po", (FIXTURES / "sample.az.po").read_bytes())
    bot.text("Ramal Rahimov")
    bot.text("ramal@example.org")
    assert "a.az.po" in bot.api.last["text"]
    assert "mode:a" in bot.api.buttons().values()


def test_second_upload_offers_choice_and_save_close(bot):
    onboard(bot)
    data = (FIXTURES / "sample.az.po").read_bytes()
    bot.upload("one.az.po", data)
    bot.upload("two.az.po", data)
    assert set(bot.api.buttons().values()) == {"up:new", "up:old"}
    bot.tap("up:new")
    assert "two.az.po" in bot.api.last["text"]
    bot.tap("mode:a")
    bot.text("/save")
    assert bot.api.documents[-1]["name"] == "two.az.po"
    bot.text("/cancel")
    drop = next(v for v in bot.api.buttons().values() if v.startswith("fin:drop:"))
    bot.tap(drop)
    bot.text("/status")
    assert "No file is open" in bot.api.last["text"]


def test_stale_close_button_does_not_close_a_newer_file(bot):
    onboard(bot)
    data = (FIXTURES / "sample.az.po").read_bytes()
    bot.upload("one.az.po", data)
    bot.text("/cancel")
    old_drop = next(v for v in bot.api.buttons().values() if v.startswith("fin:drop:"))
    bot.tap(old_drop)
    bot.upload("two.az.po", data)
    bot.tap(old_drop)  # button from the first file
    assert "out of date" in bot.api.last["text"]
    bot.text("/status")
    assert "two.az.po" in bot.api.last["text"]
    bot.tap("up:new")  # no pending upload any more
    assert "out of date" in bot.api.last["text"]


def test_html_sensitive_prompts_are_escaped(bot):
    bot.text("/start")
    bot.tap("ui:tr")
    bot.text("Ramal Rahimov")
    assert "<e-posta>" not in bot.api.last["text"] and "&lt;e-posta&gt;" in bot.api.last["text"]


def test_commands_cancel_pending_questions(bot):
    onboard(bot)
    bot.text("/profile")
    bot.tap("profile:edit")
    bot.text("/help")
    bot.text("some text")
    assert "No file is open" in bot.api.last["text"]


def test_non_object_json_is_rejected(bot):
    status, _ = bot.request("POST", "/tools/poeditor/webhook", b"[1, 2]",
                            {"HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": bot.secret})
    assert status.startswith("400")
    status, _ = bot.request("POST", "/tools/poeditor/webhook", b"{}",
                            {"HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": "şifrə"})
    assert status.startswith("403")
    assert bot.request("GET", "/tools/poeditorx")[0].startswith("404")


def test_stale_card_buttons_resend_current_card(bot):
    onboard(bot)
    bot.upload("x.az.po", (FIXTURES / "sample.az.po").read_bytes())
    bot.tap("mode:a")
    bot.tap("nav:skip:0")
    bot.tap("nav:skip:0")  # old card pressed again
    assert "out of date" in bot.api.messages[-2]["text"]


def test_rejects_wrong_files(bot):
    onboard(bot)
    bot.upload("notes.txt", b"hello")
    assert "Please send a .po or .pot file." in bot.api.last["text"]
    bot.upload("broken.po", b'msgid "x\n')
    assert "could not read" in bot.api.last["text"]


def test_group_chats_are_ignored(bot):
    bot.post({"message": {"message_id": 1, "from": {"id": USER}, "chat": {"id": -5, "type": "group"}, "text": "/start"}})
    assert bot.api.messages == []


def test_about_mentions_developer_and_gnome(bot):
    onboard(bot, "tr")
    bot.text("/about")
    text = bot.api.last["text"]
    assert "Ramal Rahimov" in text and "@rahimovramal" in text and "GNOME" in text


def test_config_defaults(tmp_path):
    cfg = load(tmp_path, environ={})
    assert cfg.base_path == "/tools/poeditor"
    assert cfg.webhook_url == "https://azelinux.com/tools/poeditor/webhook"
    assert replace(cfg, base_url="https://bot.example.org").base_path == ""


def test_webhook_ip_is_sent_when_configured(tmp_path):
    (tmp_path / ".env").write_text("BOT_TOKEN=1:x\nWEBHOOK_IP=203.0.113.5\n")
    cfg = load(tmp_path, environ={})
    sent = {}

    class Api(FakeApi):
        def call(self, method, params=None):
            if method == "setWebhook":
                sent.update(params)
            return super().call(method, params)

    state = bootstrap.ensure_setup(cfg, Api())  # type: ignore[arg-type]
    assert sent["ip_address"] == "203.0.113.5" and state["username"] == "GnomePoBot"


def test_relay_url_becomes_the_webhook(tmp_path):
    (tmp_path / ".env").write_text("BOT_TOKEN=1:x\nWEBHOOK_IP=1.2.3.4\nTELEGRAM_RELAY_URL=https://relay.example/r.php\n")
    cfg = load(tmp_path, environ={})
    sent = {}

    class Api(FakeApi):
        def call(self, method, params=None):
            if method == "setWebhook":
                sent.update(params)
            return super().call(method, params)

    bootstrap.ensure_setup(cfg, Api())  # type: ignore[arg-type]
    assert sent["url"] == "https://relay.example/r.php" and "ip_address" not in sent
