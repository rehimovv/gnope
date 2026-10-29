"""Receiving a .po/.pot file and opening a translation session for it."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from app.bot import common, ui
from app.bot.context import Ctx
from app.po.document import PoDocument, PoParseError
from app.po.plurals import language_name, normalize_lang_code
from app.storage import Session
from app.telegram import TelegramError

_LANG_IN_NAME = re.compile(r"(?:^|[._-])([a-z]{2,3}(?:_[A-Z]{2})?(?:@[a-z]+)?)\.po$")
EXTENSIONS = (".po", ".pot")


def handle_document(ctx: Ctx, document: dict) -> None:
    cfg = ctx.deps.config
    file_name = (document.get("file_name") or "").strip() or "translation.po"
    if not file_name.lower().endswith(EXTENSIONS):
        ctx.send("❌ " + ctx.t("Please send a .po or .pot file."))
        return
    if int(document.get("file_size") or 0) > cfg.max_file_bytes:
        ctx.send("❌ " + ctx.t("This file is too large. The limit is {mb} MB.", mb=cfg.max_file_bytes // (1024 * 1024)))
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    count = ctx.user.upload_count if ctx.user.upload_day == today else 0
    if count >= cfg.daily_upload_limit:
        ctx.send("⏳ " + ctx.t("You have reached today's upload limit. Please try again tomorrow."))
        return
    ctx = ctx.update_user(upload_day=today, upload_count=count + 1)

    try:
        data = ctx.deps.api.download(document["file_id"], cfg.max_file_bytes)
    except TelegramError:
        ctx.send("❌ " + ctx.t("I could not download the file. Please send it again."))
        return
    try:
        doc = PoDocument.from_bytes(data)
    except PoParseError as exc:
        ctx.send("❌ " + ctx.t("I could not read this file as a PO file.") + "\n<code>{}</code>".format(ui.esc(ui.clip(str(exc), 300))))
        return
    if not doc.active_indices():
        ctx.send("❌ " + ctx.t("This file has no strings to translate."))
        return

    uid = ctx.user.user_id
    ctx.deps.files.write_pending(uid, file_name, data)
    if not ctx.user.has_profile:
        ctx.send("📝 " + ctx.t("Before we start I need your name and email for the file header. This is asked only once."))
        common.ask_name(ctx, resume_upload=True)
        return
    if ctx.deps.store.get_session(uid):
        ctx.send(
            "📂 " + ctx.t("You already have a file open. What should I do?"),
            ui.keyboard(
                [
                    [ui.button("🆕 " + ctx.t("Open the new file"), "up:new")],
                    [ui.button("↩️ " + ctx.t("Keep the current file"), "up:old")],
                ]
            ),
        )
        return
    start_from_pending(ctx)


def detect_language(doc: PoDocument, file_name: str) -> Optional[str]:
    code = normalize_lang_code(doc.metadata.get("Language", ""))
    if code:
        return code
    match = _LANG_IN_NAME.search(file_name)
    return normalize_lang_code(match.group(1)) if match else None


def output_name(file_name: str, lang: str) -> str:
    if file_name.lower().endswith(".pot"):
        return "{}.{}.po".format(file_name[:-4], lang)
    return file_name


def start_from_pending(ctx: Ctx) -> None:
    pending = ctx.deps.files.read_pending(ctx.user.user_id)
    if pending is None:
        ctx.send("📎 " + ctx.t("Now send me a .po or .pot file to start translating."))
        return
    file_name, data = pending
    lang = detect_language(PoDocument.from_bytes(data), file_name)
    if lang is None:
        ask_language(ctx)
        return
    open_session(ctx, lang)


def ask_language(ctx: Ctx) -> None:
    ctx = ctx.set_state("ask_lang")
    suggestions = [ui.button(language_name(c) + " ({})".format(c), "lang:" + c) for c in [ctx.user.last_lang] if c]
    ctx.send(
        "🌍 " + ctx.t("Which language are you translating into? Send a language code such as az, tr, de or pt_BR."),
        ui.keyboard([suggestions]) if suggestions else None,
    )


def handle_language(ctx: Ctx, text: str) -> None:
    code = normalize_lang_code(text)
    if code is None:
        ctx.send(ctx.t("That is not a language code. Examples: az, tr, de, pt_BR, sr@latin."))
        return
    open_session(ctx, code)


def open_session(ctx: Ctx, lang: str) -> None:
    uid = ctx.user.user_id
    pending = ctx.deps.files.read_pending(uid)
    if pending is None:
        return
    file_name, data = pending
    doc = PoDocument.from_bytes(data)
    ctx.deps.files.write_work(uid, data)
    ctx.deps.files.drop_pending(uid)
    session = Session(user_id=uid, file_name=file_name, out_name=output_name(file_name, lang), lang=lang)
    ctx.deps.store.save_session(session)
    ctx = ctx.update_user(last_lang=lang, state="", state_data={})
    ctx.send(
        ui.file_summary(ctx, file_name, lang, doc.stats())
        + "\n\n"
        + ctx.t("What do you want to translate?"),
        ui.mode_keyboard(ctx, doc),
    )


def replace_current(ctx: Ctx) -> None:
    """The user chose to drop the open file in favour of the new upload."""
    if ctx.deps.files.read_pending(ctx.user.user_id) is None:
        ctx.send(ctx.t("This question is out of date."))
        return
    ctx.deps.store.delete_session(ctx.user.user_id)
    start_from_pending(ctx)


def keep_current(ctx: Ctx) -> None:
    ctx.deps.files.drop_pending(ctx.user.user_id)
