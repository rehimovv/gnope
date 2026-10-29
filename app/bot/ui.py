"""Message text and inline keyboards. All PO content is HTML-escaped here."""

from __future__ import annotations

import html
from typing import Dict, List, Optional, Sequence, Tuple

import polib

from app.bot.context import Ctx
from app.i18n import UI_LANGUAGES
from app.po.checks import Issue
from app.po.document import PoDocument, Stats
from app.po.edit import current_translations
from app.po.plurals import form_examples, language_name
from app.storage import Session

COPY_TEXT_LIMIT = 256
MESSAGE_LIMIT = 4000

Button = Dict[str, object]


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def pre(text: str, limit: int) -> str:
    return "<pre>{}</pre>".format(esc(clip(text, limit))) if text else "<i>—</i>"


def button(text: str, data: str) -> Button:
    return {"text": text, "callback_data": data}


def copy_button(text: str, value: str) -> Optional[Button]:
    if not value or len(value) > COPY_TEXT_LIMIT:
        return None
    return {"text": text, "copy_text": {"text": value}}


def keyboard(rows: Sequence[Sequence[Optional[Button]]]) -> dict:
    clean = [[b for b in row if b] for row in rows]
    return {"inline_keyboard": [row for row in clean if row]}


def language_keyboard() -> dict:
    return keyboard([[button(label, "ui:" + code)] for code, label in UI_LANGUAGES.items()])


# -- summaries --------------------------------------------------------------

def stats_lines(ctx: Ctx, stats: Stats) -> str:
    return "\n".join(
        [
            ctx.t("Total: {n}", n=stats.total),
            "✅ " + ctx.t("Translated: {n}", n=stats.translated),
            "🟡 " + ctx.t("Fuzzy: {n}", n=stats.fuzzy),
            "⬜ " + ctx.t("Untranslated: {n}", n=stats.untranslated),
        ]
    )


def file_summary(ctx: Ctx, file_name: str, lang: str, stats: Stats) -> str:
    return "📄 <b>{}</b>\n{}\n\n{}".format(
        esc(file_name),
        ctx.t("Language: {name} ({code})", name=esc(language_name(lang)), code=esc(lang)),
        stats_lines(ctx, stats),
    )


def mode_keyboard(ctx: Ctx, doc: PoDocument) -> dict:
    untranslated = len(doc.untranslated_indices())
    fuzzy = len(doc.fuzzy_indices())
    rows: List[List[Optional[Button]]] = []
    if untranslated:
        rows.append([button("⬜ " + ctx.t("Untranslated ({n})", n=untranslated), "mode:u")])
    if fuzzy:
        rows.append([button("🟡 " + ctx.t("Fuzzy ({n})", n=fuzzy), "mode:f")])
    if untranslated and fuzzy:
        rows.append([button("⬜🟡 " + ctx.t("Both ({n})", n=untranslated + fuzzy), "mode:uf")])
    rows.append([button("📜 " + ctx.t("All strings ({n})", n=len(doc.active_indices())), "mode:a")])
    rows.append([button("✖️ " + ctx.t("Close file"), "finish")])
    return keyboard(rows)


def end_keyboard(ctx: Ctx, token: str) -> dict:
    return keyboard(
        [
            [button("📜 " + ctx.t("Review all strings"), "mode:a")],
            [button("✖️ " + ctx.t("Close file"), "fin:drop:" + token)],
        ]
    )


# -- translation card --------------------------------------------------------

def _status(ctx: Ctx, entry: polib.POEntry) -> str:
    if "fuzzy" in entry.flags:
        return "🟡 " + ctx.t("fuzzy")
    if entry.translated():
        return "✅ " + ctx.t("translated")
    return "⬜ " + ctx.t("untranslated")


def _meta_lines(ctx: Ctx, entry: polib.POEntry, limit: int) -> List[str]:
    lines = []
    if entry.occurrences:
        refs = ["{}:{}".format(f, n) if n else f for f, n in entry.occurrences[:2]]
        more = " …" if len(entry.occurrences) > 2 else ""
        lines.append("📍 <i>{}</i>{}".format(esc(", ".join(refs)), more))
    if entry.comment:
        lines.append("💬 {}: <i>{}</i>".format(ctx.t("Note for translators"), esc(clip(entry.comment, limit // 2))))
    if entry.tcomment:
        lines.append("📝 {}: <i>{}</i>".format(ctx.t("Translator comment"), esc(clip(entry.tcomment, limit // 2))))
    if entry.msgctxt:
        lines.append("🔤 {}: <code>{}</code>".format(ctx.t("Context"), esc(clip(entry.msgctxt, 200))))
    if "fuzzy" in entry.flags and entry.previous_msgid:
        lines.append("♻️ {}: <i>{}</i>".format(ctx.t("Previous source"), esc(clip(entry.previous_msgid, limit // 2))))
    return lines


def _whitespace_hints(ctx: Ctx, source: str) -> List[str]:
    hints = []
    if source.endswith("\n") or source.startswith("\n"):
        hints.append("↵ " + ctx.t("This text starts or ends with a line break. It is added to your translation automatically."))
    if source != source.strip() and source.strip("\n") != source.strip():
        hints.append("␣ " + ctx.t("This text starts or ends with spaces. They are kept automatically."))
    return hints


def _examples(values: List[int]) -> str:
    return ", ".join(str(v) for v in values) + ("…" if len(values) >= 4 else "")


def _render_card(ctx: Ctx, doc: PoDocument, s: Session, nplurals: int, plural_rule: str, limit: int) -> str:
    entry = doc.entry(s.current)
    flags = [f for f in entry.flags if f != "fuzzy"]
    head = "<b>{} / {}</b> · {}".format(s.position + 1, len(s.queue), _status(ctx, entry))
    if flags:
        head += " · <code>{}</code>".format(esc(", ".join(flags)))
    parts = [head] + _meta_lines(ctx, entry, limit) + [""]

    if entry.msgid_plural:
        parts += ["<b>{}</b>".format(ctx.t("Source (singular)")), pre(entry.msgid, limit)]
        parts += ["<b>{}</b>".format(ctx.t("Source (plural)")), pre(entry.msgid_plural, limit)]
    else:
        parts += ["<b>{}</b>".format(ctx.t("Source")), pre(entry.msgid, limit)]
    parts += _whitespace_hints(ctx, entry.msgid)
    if entry.msgid == "translator-credits":
        parts.append("👥 " + esc(ctx.t("Write the translators' names, one per line, e.g. Name Surname <email>.")))

    current = current_translations(entry, nplurals)
    draft = list(s.plural_draft) + current[len(s.plural_draft):]
    examples = form_examples(plural_rule) if entry.msgid_plural else []
    if entry.msgid_plural:
        for form, value in enumerate(draft):
            label = ctx.t("Form {n}", n=form + 1)
            if form < len(examples):
                label += " (n = {})".format(_examples(examples[form]))
            marker = "👉 " if form == s.plural_form else ""
            parts += ["", "{}<b>{}</b>".format(marker, esc(label)), pre(value, limit // 2)]
        used = _examples(examples[s.plural_form]) if s.plural_form < len(examples) else "?"
        parts += ["", "✍️ " + ctx.t("Send the translation for form {n} of {total} (n = {examples}).",
                                    n=s.plural_form + 1, total=nplurals, examples=used)]
    else:
        if entry.msgstr:
            parts += ["", "<b>{}</b>".format(ctx.t("Current translation")), pre(entry.msgstr, limit)]
        parts += ["", "✍️ " + ctx.t("Send your translation as a message.")]
    return "\n".join(parts)


def card(ctx: Ctx, doc: PoDocument, s: Session, nplurals: int, plural_rule: str) -> Tuple[str, dict]:
    text = _render_card(ctx, doc, s, nplurals, plural_rule, limit=700)
    if len(text) > MESSAGE_LIMIT:
        text = _render_card(ctx, doc, s, nplurals, plural_rule, limit=250)
    return text, card_keyboard(ctx, doc, s, nplurals)


def card_keyboard(ctx: Ctx, doc: PoDocument, s: Session, nplurals: int) -> dict:
    entry = doc.entry(s.current)
    pos = s.position
    source = entry.msgid_plural if (entry.msgid_plural and s.plural_form > 0) else entry.msgid
    current = current_translations(entry, nplurals)
    value = current[min(s.plural_form, len(current) - 1)] if current else ""
    approve = None
    if "fuzzy" in entry.flags and all(current):
        approve = button("✅ " + ctx.t("Approve"), "nav:ok:{}".format(pos))
    return keyboard(
        [
            [button("⬅️ " + ctx.t("Back"), "nav:back:{}".format(pos)),
             button("⏭ " + ctx.t("Skip"), "nav:skip:{}".format(pos)),
             approve],
            [copy_button("📋 " + ctx.t("Copy source"), source),
             copy_button("📋 " + ctx.t("Copy translation"), value)],
            [button("💾 " + ctx.t("Save file"), "save"),
             button("✖️ " + ctx.t("Finish"), "finish")],
        ]
    )


def finish_keyboard(ctx: Ctx, token: str) -> dict:
    return keyboard(
        [
            [button("💾 " + ctx.t("Save and close"), "fin:save:" + token)],
            [button("🗑 " + ctx.t("Close without saving"), "fin:drop:" + token)],
            [button("↩️ " + ctx.t("Continue translating"), "fin:back")],
        ]
    )


def issue_text(ctx: Ctx, issues: Sequence[Issue]) -> List[str]:
    messages = {
        "format": ctx.t("Placeholders such as %s, %d or {{name}} do not match the source"),
        "markup": ctx.t("Markup tags differ from the source"),
        "newline": ctx.t("Line breaks at the start or end differ from the source"),
        "empty": ctx.t("The translation is empty"),
    }
    lines = []
    for issue in issues:
        if issue.code == "accelerator":
            text = ctx.t("The source has one keyboard shortcut (_) but the translation has {n}", n=issue.detail)
        else:
            text = messages.get(issue.code, issue.code)
            if issue.detail:
                text += ": <code>{}</code>".format(esc(issue.detail))
        lines.append("• " + text)
    return lines
