import io
import json
from urllib import error

import pytest

from app import telegram
from app.telegram import TelegramApi, TelegramError


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def sent(monkeypatch):
    requests = []
    replies = []

    def fake_urlopen(req, timeout):
        requests.append(req)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(reply)

    monkeypatch.setattr(telegram.request, "urlopen", fake_urlopen)
    return requests, replies


def ok(result):
    return json.dumps({"ok": True, "result": result}).encode()


def test_send_message_posts_html_json(sent):
    requests, replies = sent
    replies.append(ok({"message_id": 42}))
    assert TelegramApi("T").send_message(7, "<b>hi</b>", {"inline_keyboard": []}) == 42
    body = json.loads(requests[0].data)
    assert requests[0].full_url.endswith("/botT/sendMessage")
    assert body["parse_mode"] == "HTML" and body["chat_id"] == 7 and "reply_markup" in body


def test_api_errors_are_raised_with_description(sent):
    _, replies = sent
    replies.append(error.HTTPError("u", 400, "Bad", {}, io.BytesIO(b'{"ok":false,"description":"chat not found","error_code":400}')))
    with pytest.raises(TelegramError) as info:
        TelegramApi("T").call("sendMessage", {})
    assert info.value.description == "chat not found" and info.value.code == 400


def test_network_errors_do_not_leak_the_token(sent):
    _, replies = sent
    replies.append(error.URLError("timed out"))
    with pytest.raises(TelegramError) as info:
        TelegramApi("SECRET").call("getMe")
    assert "SECRET" not in str(info.value)


def test_send_document_is_multipart(sent):
    requests, replies = sent
    replies.append(ok({"message_id": 1}))
    TelegramApi("T").send_document(7, 'a"b.po', b"msgid", caption="done")
    req = requests[0]
    assert req.get_header("Content-type").startswith("multipart/form-data; boundary=")
    assert b'filename="ab.po"' in req.data and b"msgid" in req.data and b"done" in req.data


def test_download_checks_size(sent):
    _, replies = sent
    replies.append(ok({"file_path": "documents/x.po", "file_size": 5}))
    replies.append(b"hello")
    assert TelegramApi("T").download("id", 10) == b"hello"
    replies.append(ok({"file_path": "documents/x.po", "file_size": 50}))
    with pytest.raises(TelegramError):
        TelegramApi("T").download("id", 10)


def test_helpers_swallow_errors(sent):
    _, replies = sent
    replies.extend([error.URLError("x"), error.URLError("y")])
    api = TelegramApi("T")
    api.clear_keyboard(1, 2)
    api.answer_callback("cb", "text")
