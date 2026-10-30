"""Turns one Telegram update into a handler call."""

from __future__ import annotations

import logging
from typing import Callable, Dict

from app.bot import common, translate, upload
from app.bot.context import Ctx, Deps

log = logging.getLogger(__name__)

_QUESTION_STATES = ("ask_name", "ask_email", "ask_lang", "confirm")

_COMMANDS: Dict[str, Callable[[Ctx], None]] = {
    "/start": common.start,
    "/help": common.help_text,
    "/about": common.about,
    "/language": common.ask_ui_language,
    "/profile": common.profile,
    "/continue": translate.resume,
    "/status": translate.status,
    "/save": translate.save,
    "/cancel": translate.ask_finish,
}


def dispatch(update: dict, deps: Deps) -> None:
    if "callback_query" in update:
        query = update["callback_query"]
        message = query.get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") != "private":
            deps.api.answer_callback(query["id"])
            return
        with deps.files.lock(query["from"]["id"]):
            ctx = Ctx(deps, deps.store.get_user(query["from"]["id"]), chat["id"])
            deps.api.answer_callback(query["id"])
            _on_callback(ctx, query.get("data") or "")
        return

    message = update.get("message")
    if not message or (message.get("chat") or {}).get("type") != "private" or "from" not in message:
        return
    with deps.files.lock(message["from"]["id"]):
        ctx = Ctx(deps, deps.store.get_user(message["from"]["id"]), message["chat"]["id"])
        _on_message(ctx, message)


def _on_message(ctx: Ctx, message: dict) -> None:
    text = (message.get("text") or "").strip()
    if text.startswith("/"):
        command = text.split()[0].split("@")[0].lower()
        if not ctx.user.ui_lang and command != "/start":
            common.ask_ui_language(ctx)
            return
        handler = _COMMANDS.get(command)
        if handler:
            # A command abandons any question the bot was waiting an answer for.
            if ctx.user.state in _QUESTION_STATES:
                ctx = ctx.set_state("")
            handler(ctx)
        else:
            ctx.send(ctx.t("Unknown command. See /help"))
        return
    if not ctx.user.ui_lang:
        common.ask_ui_language(ctx)
        return
    if "document" in message:
        upload.handle_document(ctx, message["document"])
        return
    if not text:
        ctx.send(ctx.t("Please send a .po file or a text message."))
        return
    _on_text(ctx, text)


def _on_text(ctx: Ctx, text: str) -> None:
    state = ctx.user.state
    if state == "ask_name":
        common.handle_name(ctx, text)
    elif state == "ask_email":
        ctx, resume = common.handle_email(ctx, text)
        if resume:
            upload.start_from_pending(ctx)
    elif state == "ask_lang":
        upload.handle_language(ctx, text)
    else:
        # A new message while a warning is open counts as a corrected translation.
        if state == "confirm":
            ctx = ctx.set_state("translating")
        translate.handle_text(ctx, text)


def _on_callback(ctx: Ctx, data: str) -> None:
    head, _, rest = data.partition(":")
    if head == "ui":
        common.choose_ui_language(ctx, rest)
        return
    if not ctx.user.ui_lang:
        common.ask_ui_language(ctx)
        return
    if head == "profile":
        common.ask_name(ctx, resume_upload=False)
    elif head == "note":
        common.hide_reserve_note(ctx)
    elif head == "mode":
        translate.choose_mode(ctx, rest)
    elif head == "lang":
        upload.handle_language(ctx, rest)
    elif head == "up":
        if rest == "new":
            upload.replace_current(ctx)
        else:
            upload.keep_current(ctx)
            translate.resume(ctx)
    elif head in ("nav", "warn"):
        action, _, position = rest.partition(":")
        if not position.isdigit():
            return
        if head == "nav":
            translate.navigate(ctx, action, int(position))
        else:
            translate.confirm_warning(ctx, action == "keep", int(position))
    elif head == "save":
        translate.save(ctx)
    elif head == "finish":
        translate.ask_finish(ctx)
    elif head == "fin":
        action, _, token = rest.partition(":")
        if action == "back":
            translate.resume(ctx)
        else:
            translate.close(ctx, save_first=(action == "save"), token=token)
    else:
        log.info("unknown callback %r", head)
