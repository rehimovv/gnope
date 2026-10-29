from datetime import datetime, timezone
from pathlib import Path

import polib
import pytest

from app.po import checks, header
from app.po.document import PoDocument, PoParseError, format_field
from app.po.edit import approve, current_translations, mirror_edges, set_translation
from app.po.plurals import form_examples, language_name, normalize_lang_code, parse_plural_forms, plural_forms_for

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
ME = header.Translator("Ramal Rahimov", "ramal@example.org")


def load(name: str) -> PoDocument:
    return PoDocument.from_bytes((FIXTURES / name).read_bytes())


def index_of(doc: PoDocument, msgid: str) -> int:
    return next(i for i in range(len(doc)) if doc.entry(i).msgid == msgid)


# -- document ---------------------------------------------------------------

def test_untouched_file_round_trips_byte_for_byte():
    data = (FIXTURES / "sample.az.po").read_bytes()
    assert PoDocument.from_bytes(data).to_bytes() == data


def test_stats_ignore_obsolete_entries():
    stats = load("sample.az.po").stats()
    assert (stats.total, stats.translated, stats.fuzzy, stats.untranslated) == (7, 2, 1, 4)


def test_crlf_and_bom_are_accepted():
    data = (FIXTURES / "sample.az.po").read_bytes().replace(b"\n", b"\r\n")
    doc = PoDocument.from_bytes(b"\xef\xbb\xbf" + data)
    assert doc.stats().total == 7


@pytest.mark.parametrize("data", [b"", b"hello world", b'msgid "unterminated\n'])
def test_invalid_files_raise(data):
    with pytest.raises(PoParseError):
        PoDocument.from_bytes(data)


def test_changed_entry_keeps_msgid_lines_and_only_rewrites_msgstr():
    doc = load("sample.az.po")
    i = index_of(doc, "_Undo %s")
    set_translation(doc, i, ["_Geri al %s"])
    text = doc.serialize()
    assert '#: src/window.ui:10\nmsgctxt "menu"\nmsgid "_Undo %s"\nmsgstr "_Geri al %s"\n' in text
    # every other block is unchanged
    original = (FIXTURES / "sample.az.po").read_text(encoding="utf-8")
    assert text.replace('msgstr "_Geri al %s"', 'msgstr ""', 1) == original


def test_translating_fuzzy_entry_drops_flag_and_previous_msgid():
    doc = load("sample.az.po")
    i = index_of(doc, "Could not open the file “%s”")
    set_translation(doc, i, ["“%s” faylı açıla bilmədi"])
    block = doc.serialize().split("#: src/window.vala:120\n")[1].split("\n\n")[0]
    assert block == '#, c-format\nmsgid "Could not open the file “%s”"\nmsgstr "“%s” faylı açıla bilmədi"'


def test_plural_translation_and_approve():
    doc = load("sample.az.po")
    i = index_of(doc, "Deleted %d file")
    set_translation(doc, i, ["%d fayl silindi", "%d fayl silindi"])
    assert 'msgstr[0] "%d fayl silindi"\nmsgstr[1] "%d fayl silindi"' in doc.serialize()
    assert current_translations(doc.entry(i), 2) == ["%d fayl silindi", "%d fayl silindi"]

    j = index_of(doc, "Could not open the file “%s”")
    approve(doc, j)
    assert "fuzzy" not in doc.entry(j).flags
    assert doc.stats().fuzzy == 0


def test_format_field_wraps_like_gettext():
    assert format_field("msgstr", "short") == ['msgstr "short"']
    assert format_field("msgstr", "line\n") == ['msgstr "line\\n"']
    assert format_field("msgstr", "one\ntwo") == ['msgstr ""', '"one\\n"', '"two"']
    long = " ".join(["word"] * 30)
    lines = format_field("msgstr", long)
    assert lines[0] == 'msgstr ""'
    assert all(len(line) <= 79 for line in lines)
    assert "".join(line.strip('"') for line in lines[1:]) == long


# -- header -----------------------------------------------------------------

def test_header_update_on_existing_po():
    doc = load("sample.az.po")
    notes = header.apply(doc, ME, "az", NOW)
    text = doc.serialize()
    assert notes == []
    assert '"PO-Revision-Date: 2026-10-30 12:00+0000\\n"' in text
    assert '"Last-Translator: Ramal Rahimov <ramal@example.org>\\n"' in text
    assert '"Language-Team: Azerbaijani <https://l10n.gnome.org/teams/az/>\\n"' in text
    assert '"X-Generator: GNOME PO Telegram Bot 1.0\\n"' in text
    assert "# Ramal Rahimov <ramal@example.org>, 2026.\n#\n" in text
    assert "# Test Translator <test@example.org>, 2024.\n" in text
    keys = list(doc.metadata)
    assert keys.index("Last-Translator") < keys.index("Language") < keys.index("Plural-Forms")


def test_header_adds_year_to_existing_translator_line():
    doc = load("sample.az.po")
    header.apply(doc, header.Translator("Test Translator", "test@example.org"), "az", NOW)
    assert "# Test Translator <test@example.org>, 2024, 2026.\n" in doc.serialize()


def test_pot_header_is_initialised():
    doc = load("sample.pot")
    header.apply(doc, ME, "tr", NOW)
    text = doc.serialize()
    assert text.startswith("# Turkish translation for gnome-sample.\n# Copyright (C) 2026 THE PACKAGE'S")
    assert "# Ramal Rahimov <ramal@example.org>, 2026." in text
    assert "#, fuzzy" not in text.split("msgid")[0]
    assert '"Language: tr\\n"' in text
    assert '"Plural-Forms: nplurals=1; plural=0;\\n"' in text
    assert '"Content-Type: text/plain; charset=UTF-8\\n"' in text
    assert "LANGUAGE <LL@li.org>" not in text
    reparsed = PoDocument.parse(text)
    assert reparsed.metadata["Language"] == "tr"


def test_unknown_language_gets_default_plural_rule_and_a_note():
    doc = load("sample.pot")
    assert header.apply(doc, ME, "xx", NOW) == ["plural_guess"]


# -- checks -----------------------------------------------------------------

def _entry(doc: PoDocument, msgid: str) -> polib.POEntry:
    return doc.entry(index_of(doc, msgid))


def test_format_mismatch_is_an_error():
    doc = load("sample.az.po")
    issues = checks.check(_entry(doc, "Could not open the file “%s”"), ["fayl açıla bilmədi %d"])
    assert checks.has_errors(issues)
    assert issues[0].code == "format"


def test_positional_format_reorder_is_fine():
    entry = polib.POEntry(msgid="%s of %d", flags=["c-format"])
    assert checks.check(entry, ["%2$d / %1$s"]) == []


def test_python_and_brace_formats():
    py = polib.POEntry(msgid="%(name)s left", flags=["python-format"])
    assert checks.check(py, ["%(name)s getdi"]) == []
    assert checks.has_errors(checks.check(py, ["%(ad)s getdi"]))
    brace = polib.POEntry(msgid="{count} files", flags=["python-brace-format"])
    assert checks.check(brace, ["{count} fayl"]) == []
    assert checks.check(brace, ["{say} fayl"])[0].code == "format"


def test_accelerator_markup_and_newline_checks():
    doc = load("sample.az.po")
    undo = _entry(doc, "_Undo %s")
    assert [i.code for i in checks.check(undo, ["Geri al %s"])] == ["accelerator"]
    assert checks.check(undo, ["Geri _al %s"]) == []
    markup = _entry(doc, "Open <b>bold</b> link")
    assert [i.code for i in checks.check(markup, ["Qalın keçidi aç"])] == ["markup"]
    long = doc.entry(4)
    assert long.msgid.endswith("\n")
    assert checks.check(long, ["Yeni sətirsiz"])[0].code == "newline"
    assert checks.check(undo, [""])[0].code == "empty"


def test_plural_format_differences_are_only_warnings():
    doc = load("sample.az.po")
    issues = checks.check(_entry(doc, "Deleted %d file"), ["Bir fayl silindi", "%d fayl silindi"])
    assert issues and not checks.has_errors(issues)


# -- helpers ----------------------------------------------------------------

def test_mirror_edges():
    assert mirror_edges("Hello\n", "Salam") == "Salam\n"
    assert mirror_edges("\n  Hi ", "  Salam  ") == "\n  Salam "
    assert mirror_edges("Hello", "   ") == ""


def test_plural_helpers():
    assert normalize_lang_code("pt-br") == "pt_BR"
    assert normalize_lang_code("AZ") == "az"
    assert normalize_lang_code("sr@latin") == "sr@latin"
    assert normalize_lang_code("not a code") is None
    assert language_name("pt_BR") == "Brazilian Portuguese"
    assert language_name("az_IR") == "Azerbaijani"
    assert plural_forms_for("tr") == ("nplurals=1; plural=0;", True)
    assert plural_forms_for("zz")[1] is False
    assert form_examples("nplurals=2; plural=(n != 1);") == [[1], [0, 2, 3, 4]]
    ru = form_examples(plural_forms_for("ru")[0])
    assert ru[0][:2] == [1, 21] and ru[1][:3] == [2, 3, 4]
    assert parse_plural_forms("nplurals=2; plural=import os") is None
    assert parse_plural_forms("garbage") is None
