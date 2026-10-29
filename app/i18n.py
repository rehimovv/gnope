"""The bot's own interface translations, stored as ordinary PO files.

The English text is the msgid; app/locale/<code>.po holds each translation,
so the bot's interface can be translated with the bot itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import polib

LOCALE_DIR = Path(__file__).resolve().parent / "locale"
DEFAULT = "en"
UI_LANGUAGES: Dict[str, str] = {
    "en": "🇬🇧 English",
    "tr": "🇹🇷 Türkçe",
    "az": "🇦🇿 Azərbaycanca",
}

_catalogs: Dict[str, Dict[str, str]] = {}


def _catalog(lang: str) -> Dict[str, str]:
    if lang not in _catalogs:
        path = LOCALE_DIR / "{}.po".format(lang)
        entries: Dict[str, str] = {}
        if path.is_file():
            for entry in polib.pofile(str(path)):
                if entry.msgstr and not entry.obsolete and "fuzzy" not in entry.flags:
                    entries[entry.msgid] = entry.msgstr
        _catalogs[lang] = entries
    return _catalogs[lang]


def tr(lang: str, msgid: str, **values: object) -> str:
    """Translate and format. Literal braces in messages are written as {{ }}."""
    text = msgid if lang == DEFAULT else _catalog(lang).get(msgid, msgid)
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return msgid.format(**values)


def N_(msgid: str) -> str:  # noqa: N802 (gettext convention)
    """Mark a string for extraction without translating it yet."""
    return msgid


def pick(code: str) -> str:
    """Map a Telegram language_code to one of the interface languages."""
    base = (code or "").split("-")[0].lower()
    return base if base in UI_LANGUAGES else DEFAULT
