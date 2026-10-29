"""Plural-Forms rules and language names for languages GNOME translates into."""

from __future__ import annotations

import gettext
import re
from typing import Callable, Dict, List, Optional, Tuple

_TWO = "nplurals=2; plural=(n != 1);"
_TWO_GT1 = "nplurals=2; plural=(n > 1);"
_ONE = "nplurals=1; plural=0;"
_SLAVIC = (
    "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && "
    "(n%100<10 || n%100>=20) ? 1 : 2);"
)

# code: (English name, Plural-Forms)
LANGUAGES: Dict[str, Tuple[str, str]] = {
    "af": ("Afrikaans", _TWO),
    "an": ("Aragonese", _TWO),
    "ar": ("Arabic", "nplurals=6; plural=n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3 && n%100<=10 ? 3 : n%100>=11 ? 4 : 5;"),
    "ast": ("Asturian", _TWO),
    "az": ("Azerbaijani", _TWO),
    "be": ("Belarusian", _SLAVIC),
    "bg": ("Bulgarian", _TWO),
    "bn": ("Bengali", _TWO),
    "bs": ("Bosnian", _SLAVIC),
    "ca": ("Catalan", _TWO),
    "cs": ("Czech", "nplurals=3; plural=(n==1) ? 0 : (n>=2 && n<=4) ? 1 : 2;"),
    "da": ("Danish", _TWO),
    "de": ("German", _TWO),
    "el": ("Greek", _TWO),
    "en_GB": ("English (United Kingdom)", _TWO),
    "eo": ("Esperanto", _TWO),
    "es": ("Spanish", _TWO),
    "et": ("Estonian", _TWO),
    "eu": ("Basque", _TWO),
    "fi": ("Finnish", _TWO),
    "fr": ("French", _TWO_GT1),
    "fur": ("Friulian", _TWO),
    "ga": ("Irish", "nplurals=5; plural=n==1 ? 0 : n==2 ? 1 : n<7 ? 2 : n<11 ? 3 : 4;"),
    "gl": ("Galician", _TWO),
    "gu": ("Gujarati", _TWO),
    "hi": ("Hindi", _TWO),
    "hr": ("Croatian", _SLAVIC),
    "hu": ("Hungarian", _TWO),
    "ia": ("Interlingua", _TWO),
    "id": ("Indonesian", _ONE),
    "is": ("Icelandic", "nplurals=2; plural=(n%10!=1 || n%100==11);"),
    "it": ("Italian", _TWO),
    "ja": ("Japanese", _ONE),
    "kk": ("Kazakh", _TWO),
    "kn": ("Kannada", _TWO),
    "ko": ("Korean", _ONE),
    "lt": ("Lithuanian", "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && (n%100<10 || n%100>=20) ? 1 : 2);"),
    "lv": ("Latvian", "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n != 0 ? 1 : 2);"),
    "ml": ("Malayalam", _TWO),
    "mr": ("Marathi", _TWO),
    "ms": ("Malay", _ONE),
    "nb": ("Norwegian Bokmål", _TWO),
    "ne": ("Nepali", _TWO),
    "nl": ("Dutch", _TWO),
    "nn": ("Norwegian Nynorsk", _TWO),
    "oc": ("Occitan", _TWO_GT1),
    "pa": ("Punjabi", _TWO),
    "pl": ("Polish", "nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);"),
    "pt": ("Portuguese", _TWO),
    "pt_BR": ("Brazilian Portuguese", _TWO_GT1),
    "ro": ("Romanian", "nplurals=3; plural=(n==1 ? 0 : (n==0 || (n%100 > 0 && n%100 < 20)) ? 1 : 2);"),
    "ru": ("Russian", _SLAVIC),
    "sk": ("Slovak", "nplurals=3; plural=(n==1) ? 0 : (n>=2 && n<=4) ? 1 : 2;"),
    "sq": ("Albanian", _TWO),
    "sr": ("Serbian", _SLAVIC),
    "sv": ("Swedish", _TWO),
    "ta": ("Tamil", _TWO),
    "te": ("Telugu", _TWO),
    "th": ("Thai", _ONE),
    "tr": ("Turkish", _ONE),
    "ug": ("Uyghur", _ONE),
    "uk": ("Ukrainian", _SLAVIC),
    "ur": ("Urdu", _TWO),
    "uz": ("Uzbek", _TWO),
    "vi": ("Vietnamese", _ONE),
    "zh_CN": ("Chinese (China)", _ONE),
    "zh_HK": ("Chinese (Hong Kong)", _ONE),
    "zh_TW": ("Chinese (Taiwan)", _ONE),
}

DEFAULT_PLURAL_FORMS = _TWO

_LANG_CODE = re.compile(r"^[a-z]{2,3}(?:_[A-Z]{2})?(?:@[a-z]+)?$")
_PLURAL_FORMS = re.compile(r"nplurals\s*=\s*(\d+)\s*;\s*plural\s*=\s*(.+?);?\s*$")


def normalize_lang_code(text: str) -> Optional[str]:
    """Turn user input such as 'pt-br' or 'AZ' into a gettext code, or None."""
    text = text.strip().replace("-", "_")
    if "_" in text:
        lang, _, region = text.partition("_")
        text = "{}_{}".format(lang.lower(), region.upper())
    else:
        text = text.lower()
    return text if _LANG_CODE.match(text) else None


def language_name(code: str) -> str:
    if code in LANGUAGES:
        return LANGUAGES[code][0]
    base = code.split("_")[0].split("@")[0]
    return LANGUAGES[base][0] if base in LANGUAGES else code


def plural_forms_for(code: str) -> Tuple[str, bool]:
    """Return (Plural-Forms, known) for a language code."""
    for candidate in (code, code.split("@")[0], code.split("_")[0]):
        if candidate in LANGUAGES:
            return LANGUAGES[candidate][1], True
    return DEFAULT_PLURAL_FORMS, False


def parse_plural_forms(value: str) -> Optional[Tuple[int, Callable[[int], int]]]:
    """Parse a Plural-Forms header into (nplurals, function), or None if invalid."""
    match = _PLURAL_FORMS.search(value or "")
    if not match:
        return None
    try:
        count = int(match.group(1))
        func = gettext.c2py(match.group(2).strip().rstrip(";"))
    except (ValueError, SyntaxError, RecursionError):
        return None
    if count < 1 or count > 6:
        return None
    return count, func


def form_examples(value: str, per_form: int = 4) -> List[List[int]]:
    """Example numbers that select each plural form, e.g. [[1], [0, 2, 3, 4]]."""
    parsed = parse_plural_forms(value)
    if parsed is None:
        return []
    count, func = parsed
    examples: List[List[int]] = [[] for _ in range(count)]
    for n in range(0, 1001):
        try:
            form = int(func(n))
        except (ZeroDivisionError, ValueError):
            continue
        if 0 <= form < count and len(examples[form]) < per_form:
            examples[form].append(n)
        if all(len(e) >= per_form for e in examples):
            break
    return examples
