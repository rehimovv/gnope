"""Header update applied when a translated file is handed back to the translator."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from app.po.document import PoDocument
from app.po.plurals import language_name, parse_plural_forms, plural_forms_for

GENERATOR = "GNOME PO Telegram Bot 1.0"

_KEY_ORDER = [
    "Project-Id-Version",
    "Report-Msgid-Bugs-To",
    "POT-Creation-Date",
    "PO-Revision-Date",
    "Last-Translator",
    "Language-Team",
    "Language",
    "MIME-Version",
    "Content-Type",
    "Content-Transfer-Encoding",
    "Plural-Forms",
    "X-Generator",
]


@dataclass(frozen=True)
class Translator:
    name: str
    email: str

    @property
    def signature(self) -> str:
        return "{} <{}>".format(self.name, self.email)


def _is_placeholder(value: str) -> bool:
    return not value.strip() or any(
        marker in value for marker in ("LANGUAGE", "LL@li.org", "FULL NAME", "EMAIL@ADDRESS", "INTEGER", "EXPRESSION")
    )


def _ordered(original_keys: List[str], metadata: Dict[str, str]) -> Dict[str, str]:
    """Keep the file's own key order; put keys we add where gettext would."""
    keys = [k for k in original_keys if k in metadata]
    for key in metadata:
        if key in keys:
            continue
        position = len(keys)
        if key in _KEY_ORDER:
            earlier = [keys.index(k) for k in _KEY_ORDER[: _KEY_ORDER.index(key)] if k in keys]
            position = max(earlier) + 1 if earlier else 0
        keys.insert(position, key)
    return {k: metadata[k] for k in keys}


def _update_comments(comments: List[str], translator: Translator, lang: str, package: str, year: int) -> List[str]:
    updated = []
    for line in comments:
        if line.startswith("# SOME DESCRIPTIVE TITLE"):
            line = "# {} translation for {}.".format(language_name(lang), package)
        elif "FIRST AUTHOR <EMAIL@ADDRESS>" in line:
            line = "# {}, {}.".format(translator.signature, year)
        elif line.startswith("# Copyright (C) YEAR"):
            line = line.replace("YEAR", str(year), 1)
        updated.append(line)

    if not updated:
        updated = [
            "# {} translation for {}.".format(language_name(lang), package),
            "# This file is distributed under the same license as the {} package.".format(package),
        ]

    mine = [i for i, line in enumerate(updated) if translator.signature in line]
    if mine:
        i = mine[-1]
        if str(year) not in updated[i]:
            updated[i] = re.sub(r"\.?\s*$", ", {}.".format(year), updated[i], count=1)
        return updated

    line = "# {}, {}.".format(translator.signature, year)
    # Translator lines go before a trailing bare "#" separator, as gettext tools do.
    if updated and updated[-1].strip() == "#":
        return updated[:-1] + [line, updated[-1]]
    return updated + [line]


def apply(doc: PoDocument, translator: Translator, lang: str, now: datetime) -> List[str]:
    """Update the header in place. Returns notes worth telling the translator."""
    notes: List[str] = []
    metadata = dict(doc.metadata)
    package = (metadata.get("Project-Id-Version") or "PACKAGE").split(" ")[0]
    if package.upper() == "PACKAGE":
        package = "this package"

    metadata["PO-Revision-Date"] = now.strftime("%Y-%m-%d %H:%M%z")
    metadata["Last-Translator"] = translator.signature
    if _is_placeholder(metadata.get("Language-Team", "")):
        metadata["Language-Team"] = "{} <https://l10n.gnome.org/teams/{}/>".format(language_name(lang), lang)
    if not metadata.get("Language", "").strip():
        metadata["Language"] = lang
    metadata.setdefault("MIME-Version", "1.0")
    metadata["Content-Type"] = "text/plain; charset=UTF-8"
    metadata.setdefault("Content-Transfer-Encoding", "8bit")

    current = metadata.get("Plural-Forms", "")
    if _is_placeholder(current) or parse_plural_forms(current) is None:
        rule, known = plural_forms_for(lang)
        metadata["Plural-Forms"] = rule
        if not known:
            notes.append("plural_guess")
    metadata["X-Generator"] = GENERATOR

    comments = _update_comments(doc.header_comments, translator, lang, package, now.year)
    flags = [f for f in doc.header_flags if f != "fuzzy"]
    doc.set_header(comments, flags, _ordered(list(doc.metadata), metadata))
    return notes
