"""The string-by-string translation loop, saving and closing a file."""

from __future__ import annotations

from dataclasses import replace
from typing import List, Optional, Sequence, Tuple

from app.bot import ui
from app.bot.context import Ctx
from app.po import checks, header
from app.po.document import PoDocument
from app.po.edit import approve, current_translations, mirror_edges, set_translation, source_for_form
from app.po.plurals import parse_plural_forms, plural_forms_for
from app.storage import Session

MODES = ("u", "f", "uf", "a")


# -- helpers -----------------------------------------------------------------

def _session(ctx: Ctx) -> Optional[Session]:
    return ctx.deps.store.get_session(ctx.user.user_id)


def _load(ctx: Ctx) -> Optional[PoDocument]:
    data = ctx.deps.files.read_work(ctx.user.user_id)
    return PoDocument.from_bytes(data) if data else None


def _store(ctx: Ctx, doc: PoDocument) -> None:
    ctx.deps.files.write_work(ctx.user.user_id, doc.to_bytes())


def plural_info(doc: PoDocument, lang: str) -> Tuple[int, str]:
    rule = doc.metadata.get("Plural-Forms", "")
    parsed = parse_plural_forms(rule)
    if parsed is None:
        rule, _ = plural_forms_for(lang)
        parsed = parse_plural_forms(rule)
    return (parsed[0] if parsed else 2), rule


def _no_file(ctx: Ctx) -> None:
    ctx.send("📎 " + ctx.t("No file is open. Send me a .po or .pot file to start."))


def _queue_for(doc: PoDocument, mode: str) -> List[int]:
    if mode == "u":
        return doc.untranslated_indices()
    if mode == "f":
        return doc.fuzzy_indices()
    if mode == "uf":
        return sorted(set(doc.untranslated_indices()) | set(doc.fuzzy_indices()))
    return doc.active_indices()


# -- showing the current string ----------------------------------------------

def show_card(ctx: Ctx, s: Session, doc: Optional[PoDocument] = None) -> None:
    doc = doc or _load(ctx)
    if doc is None:
        _no_file(ctx)
        return
    if s.card_message_id:
        ctx.deps.api.clear_keyboard(ctx.chat_id, s.card_message_id)
    if s.current is None or s.current >= len(doc):
        _reached_end(ctx, s, doc)
        return
    nplurals, rule = plural_info(doc, s.lang)
    text, keyboard = ui.card(ctx, doc, s, nplurals, rule)
    message_id = ctx.send(text, keyboard)
    ctx.deps.store.save_session(replace(s, card_message_id=message_id))


def _reached_end(ctx: Ctx, s: Session, doc: PoDocument) -> None:
    ctx.deps.store.save_session(replace(s, card_message_id=0))
    ctx.send("🎉 " + ctx.t("You reached the end of this list. Here is your file:"))
    export(ctx)
    ctx.send(ctx.t("What next?"), ui.end_keyboard(ctx, s.token))


def resume(ctx: Ctx) -> None:
    s = _session(ctx)
    doc = _load(ctx) if s else None
    if s is None or doc is None:
        _no_file(ctx)
        return
    if not s.mode:
        ctx.send(ui.file_summary(ctx, s.file_name, s.lang, doc.stats()) + "\n\n" + ctx.t("What do you want to translate?"),
                 ui.mode_keyboard(ctx, doc))
        return
    ctx.set_state("translating")
    show_card(ctx, s, doc)


def status(ctx: Ctx) -> None:
    s = _session(ctx)
    doc = _load(ctx) if s else None
    if s is None or doc is None:
        _no_file(ctx)
        return
    text = ui.file_summary(ctx, s.file_name, s.lang, doc.stats())
    if s.mode:
        text += "\n\n" + ctx.t("Position: {pos} / {total}", pos=min(s.position + 1, len(s.queue)), total=len(s.queue))
    ctx.send(text)


def choose_mode(ctx: Ctx, mode: str) -> None:
    s = _session(ctx)
    doc = _load(ctx) if s else None
    if s is None or doc is None or mode not in MODES:
        _no_file(ctx)
        return
    queue = _queue_for(doc, mode)
    if not queue:
        ctx.send(ctx.t("There is nothing to translate in this selection."), ui.mode_keyboard(ctx, doc))
        return
    s = ctx.deps.store.save_session(
        replace(s, mode=mode, queue=tuple(queue), position=0, plural_form=0, plural_draft=())
    )
    ctx.set_state("translating")
    show_card(ctx, s, doc)


# -- answering ---------------------------------------------------------------

def handle_text(ctx: Ctx, text: str) -> None:
    s = _session(ctx)
    doc = _load(ctx) if s else None
    if s is None or doc is None:
        _no_file(ctx)
        return
    if not s.mode:
        ctx.send(ctx.t("Choose what to translate first:"), ui.mode_keyboard(ctx, doc))
        return
    index = s.current
    if index is None:
        # The file was already sent when the list ended; do not resend it.
        ctx.send(ctx.t("What next?"), ui.end_keyboard(ctx, s.token))
        return

    entry = doc.entry(index)
    nplurals, _ = plural_info(doc, s.lang)
    source = source_for_form(entry, s.plural_form)
    value = text.strip() if entry.msgid == "translator-credits" else mirror_edges(source, text)

    if entry.msgid_plural:
        draft = list(s.plural_draft) or current_translations(entry, nplurals)
        draft = (draft + [""] * nplurals)[:nplurals]
        draft[s.plural_form] = value
        if s.plural_form + 1 < nplurals:
            s = ctx.deps.store.save_session(replace(s, plural_form=s.plural_form + 1, plural_draft=tuple(draft)))
            show_card(ctx, s, doc)
            return
        translations = draft
    else:
        translations = [value]

    issues = checks.check(entry, translations)
    if checks.has_errors(issues):
        ctx.send(
            "⛔ " + ctx.t("This translation would break the file:") + "\n"
            + "\n".join(ui.issue_text(ctx, issues)) + "\n\n" + ctx.t("Please send a corrected translation.")
        )
        return
    if issues:
        ctx.set_state("confirm", translations=translations, position=s.position)
        ctx.send(
            "⚠️ " + ctx.t("Please check this translation:") + "\n" + "\n".join(ui.issue_text(ctx, issues)),
            ui.keyboard(
                [
                    [ui.button("✅ " + ctx.t("Keep it"), "warn:keep:{}".format(s.position)),
                     ui.button("✏️ " + ctx.t("Edit"), "warn:edit:{}".format(s.position))],
                ]
            ),
        )
        return
    _commit(ctx, s, doc, translations)


def _commit(ctx: Ctx, s: Session, doc: PoDocument, translations: Sequence[str]) -> None:
    set_translation(doc, s.current, translations)
    _store(ctx, doc)
    s = ctx.deps.store.save_session(
        replace(s, position=s.position + 1, plural_form=0, plural_draft=(), changed=True)
    )
    ctx.set_state("translating")
    show_card(ctx, s, doc)


def confirm_warning(ctx: Ctx, keep: bool, position: int) -> None:
    s = _session(ctx)
    data = ctx.user.state_data
    if s is None or ctx.user.state != "confirm" or data.get("position") != position or s.position != position:
        ctx.send(ctx.t("This question is out of date."))
        return
    doc = _load(ctx)
    if doc is None:
        _no_file(ctx)
        return
    if keep:
        _commit(ctx, s, doc, data.get("translations", []))
        return
    ctx.set_state("translating")
    ctx.send("✏️ " + ctx.t("Send the corrected translation."))
    if doc.entry(s.current).msgid_plural:
        s = ctx.deps.store.save_session(replace(s, plural_form=0))
        show_card(ctx, s, doc)


def navigate(ctx: Ctx, action: str, position: int) -> None:
    s = _session(ctx)
    doc = _load(ctx) if s else None
    if s is None or doc is None or not s.mode:
        _no_file(ctx)
        return
    if position != s.position:
        ctx.send(ctx.t("That card is out of date. Here is the current one:"))
        show_card(ctx, s, doc)
        return
    if action == "back":
        new_position = max(0, s.position - 1)
    elif action == "ok" and s.current is not None:
        approve(doc, s.current)
        _store(ctx, doc)
        s = replace(s, changed=True)
        new_position = s.position + 1
    else:
        new_position = s.position + 1
    s = ctx.deps.store.save_session(replace(s, position=new_position, plural_form=0, plural_draft=()))
    ctx.set_state("translating")
    show_card(ctx, s, doc)


# -- saving and closing ------------------------------------------------------

def export(ctx: Ctx) -> bool:
    s = _session(ctx)
    doc = _load(ctx) if s else None
    if s is None or doc is None:
        _no_file(ctx)
        return False
    translator = header.Translator(ctx.user.name, ctx.user.email)
    notes = header.apply(doc, translator, s.lang, ctx.now())
    data = doc.to_bytes()
    ctx.deps.files.write_work(ctx.user.user_id, data)
    st = doc.stats()
    caption = [
        "✅ <b>{}</b>".format(ui.esc(s.out_name)),
        ctx.t("{done} of {total} translated · {fuzzy} fuzzy · {todo} untranslated",
              done=st.translated, total=st.total, fuzzy=st.fuzzy, todo=st.untranslated),
        ctx.t("Upload it to Damned Lies (l10n.gnome.org) or send it to your team."),
    ]
    if "plural_guess" in notes:
        caption.append("⚠️ " + ctx.t("I do not know the plural rules of this language. Please check the Plural-Forms line in the header."))
    ctx.deps.api.send_document(ctx.chat_id, s.out_name, data, "\n".join(caption))
    ctx.deps.store.save_session(replace(s, changed=False))
    return True


def save(ctx: Ctx) -> None:
    if export(ctx):
        s = _session(ctx)
        if s and s.mode and s.current is not None:
            show_card(ctx, s)


def ask_finish(ctx: Ctx) -> None:
    s = _session(ctx)
    if s is None:
        _no_file(ctx)
        return
    text = "❔ " + ctx.t("Close {name}?", name=ui.esc(s.file_name))
    if s.changed:
        text += "\n" + ctx.t("You have changes that were not downloaded yet.")
    ctx.send(text, ui.finish_keyboard(ctx, s.token))


def close(ctx: Ctx, save_first: bool, token: str) -> None:
    s = _session(ctx)
    if s is None:
        _no_file(ctx)
        return
    if token != s.token:
        ctx.send(ctx.t("This question is out of date."))
        return
    if save_first and not export(ctx):
        return
    if s.card_message_id:
        ctx.deps.api.clear_keyboard(ctx.chat_id, s.card_message_id)
    ctx.deps.store.delete_session(ctx.user.user_id)
    ctx.deps.files.delete_user(ctx.user.user_id)
    ctx.set_state("")
    ctx.send("👋 " + ctx.t("File closed and deleted from the server. Send a new .po file whenever you like."))
