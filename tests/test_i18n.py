import re

import polib
import pytest

from app.i18n import LOCALE_DIR, pick, tr
from scripts.extract_messages import extract

_FIELD = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")


@pytest.mark.parametrize("lang", ["tr", "az"])
def test_every_interface_string_is_translated(lang):
    po = polib.pofile(str(LOCALE_DIR / "{}.po".format(lang)))
    translated = {e.msgid: e.msgstr for e in po if e.msgstr and "fuzzy" not in e.flags}
    missing = [m for m in extract() if m not in translated]
    assert missing == []


@pytest.mark.parametrize("lang", ["tr", "az"])
def test_translations_keep_placeholders(lang):
    for entry in polib.pofile(str(LOCALE_DIR / "{}.po".format(lang))):
        assert sorted(_FIELD.findall(entry.msgid)) == sorted(_FIELD.findall(entry.msgstr)), entry.msgid
        assert entry.msgid.count("{{") == entry.msgstr.count("{{"), entry.msgid


def test_tr_formats_and_falls_back():
    assert tr("az", "Total: {n}", n=3) == "Cəmi: 3"
    assert tr("en", "Total: {n}", n=3) == "Total: 3"
    assert tr("xx", "Total: {n}", n=3) == "Total: 3"
    assert tr("en", "Placeholders such as %s, %d or {{name}} do not match the source").endswith("{name} do not match the source")
    assert pick("az-AZ") == "az" and pick("de") == "en" and pick("") == "en"
