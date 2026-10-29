"""Operations that change entries, shared by the bot handlers."""

from __future__ import annotations

import re
from typing import List, Sequence

import polib

from app.po.document import PoDocument

_LEAD = re.compile(r"^\s*")
_TRAIL = re.compile(r"\s*$")


def mirror_edges(source: str, text: str) -> str:
    """Give the translation the source's leading and trailing whitespace.

    Telegram trims every message, so a translator cannot type a trailing
    newline or space. Copying the source's edges keeps msgfmt happy.
    """
    body = text.strip()
    if not body:
        return ""
    return _LEAD.match(source).group(0) + body + _TRAIL.search(source).group(0)


def source_for_form(entry: polib.POEntry, form: int) -> str:
    return entry.msgid if form == 0 or not entry.msgid_plural else entry.msgid_plural


def current_translations(entry: polib.POEntry, nplurals: int) -> List[str]:
    if not entry.msgid_plural:
        return [entry.msgstr]
    return [entry.msgstr_plural.get(i, "") for i in range(nplurals)]


def _clear_fuzzy(entry: polib.POEntry) -> None:
    if "fuzzy" in entry.flags:
        entry.flags.remove("fuzzy")
    entry.previous_msgctxt = None
    entry.previous_msgid = None
    entry.previous_msgid_plural = None


def set_translation(doc: PoDocument, index: int, translations: Sequence[str]) -> None:
    entry = doc.entry(index)
    if entry.msgid_plural:
        entry.msgstr_plural = {i: text for i, text in enumerate(translations)}
    else:
        entry.msgstr = translations[0]
    _clear_fuzzy(entry)
    doc.mark_changed(index)


def approve(doc: PoDocument, index: int) -> None:
    _clear_fuzzy(doc.entry(index))
    doc.mark_changed(index)
