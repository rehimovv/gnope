"""Checks run on a translation before it is written, in the spirit of msgfmt -c.

Errors are problems msgfmt --check would reject (the file would fail on
Damned Lies); warnings are likely mistakes the translator may still keep.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import polib

ERROR = "error"
WARNING = "warning"

_PRINTF = re.compile(
    r"%(?:(\d+)\$)?[-+ #0']*(?:\d+|\*(?:\d+\$)?)?(?:\.(?:\d+|\*(?:\d+\$)?))?"
    r"(hh|h|ll|l|L|q|j|z|Z|t|I64|I32|I)?([diouxXeEfFgGaAcspnCS%])"
)
_PYTHON = re.compile(r"%(?:\(([^)]+)\))?[-+ #0]*(?:\d+|\*)?(?:\.\d+)?([diouxXeEfFgGcrsa%])")
_BRACE = re.compile(r"(?<!\{)\{([^{}]*)\}(?!\})")
_ACCEL_SOURCE = re.compile(r"(?:^|(?<=[^\w]))_(?=\w)")
_ACCEL_ANY = re.compile(r"_(?=\w)")
_TAG = re.compile(r"<(/?)([a-zA-Z][\w:-]*)[^<>]*?(/?)>")

_PRINTF_FLAGS = ("c-format", "objc-format", "javascript-format", "gcc-internal-format")
_TYPE_GROUPS = {
    "d": "int", "i": "int",
    "o": "uint", "u": "uint", "x": "uint", "X": "uint",
    "e": "double", "E": "double", "f": "double", "F": "double",
    "g": "double", "G": "double", "a": "double", "A": "double",
    "c": "char", "C": "char", "s": "string", "S": "string",
    "p": "pointer", "n": "count",
}


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    detail: str = ""


def _printf_signature(text: str) -> Optional[Dict[int, str]]:
    """Map argument position to type; None when positions are inconsistent."""
    result: Dict[int, str] = {}
    sequential = 0
    for match in _PRINTF.finditer(text):
        position, length, conv = match.group(1), match.group(2) or "", match.group(3)
        if conv == "%":
            continue
        if position:
            pos = int(position)
        else:
            sequential += 1
            pos = sequential
        kind = length + _TYPE_GROUPS.get(conv, conv)
        if result.get(pos, kind) != kind:
            return None
        result[pos] = kind
    return result


def _python_signature(text: str) -> Counter:
    return Counter(
        (name or "", conv) for name, conv in _PYTHON.findall(text) if conv != "%"
    )


def _brace_signature(text: str) -> Counter:
    return Counter(name.split(":")[0].split("!")[0] for name in _BRACE.findall(text))


def _describe(sig: Dict[int, str]) -> str:
    return ", ".join("{}:{}".format(k, v) for k, v in sorted(sig.items())) or "—"


def _format_issues(flags: Sequence[str], source: str, translation: str, strict: bool) -> List[Issue]:
    severity = ERROR if strict else WARNING
    issues: List[Issue] = []
    if any(f in flags for f in _PRINTF_FLAGS):
        src, dst = _printf_signature(source), _printf_signature(translation)
        if src is not None and src != dst:
            issues.append(Issue("format", severity, "{} → {}".format(_describe(src), _describe(dst or {}))))
    if "python-format" in flags and _python_signature(source) != _python_signature(translation):
        issues.append(Issue("format", severity, "python-format"))
    if "python-brace-format" in flags and _brace_signature(source) != _brace_signature(translation):
        issues.append(Issue("format", severity, "python-brace-format"))
    return issues


def _accelerator_issue(source: str, translation: str) -> Optional[Issue]:
    if len(_ACCEL_SOURCE.findall(source)) != 1:
        return None
    count = len(_ACCEL_ANY.findall(translation))
    if count == 1:
        return None
    return Issue("accelerator", WARNING, str(count))


def _tags(text: str) -> Counter:
    return Counter((close, name.lower()) for close, name, _ in _TAG.findall(text))


def _markup_issue(source: str, translation: str) -> Optional[Issue]:
    src = _tags(source)
    if not src or src == _tags(translation):
        return None
    missing = src - _tags(translation)
    shown = ", ".join("<{}{}>".format(c, n) for (c, n) in missing) or "?"
    return Issue("markup", WARNING, shown)


def _newline_issue(source: str, translation: str) -> Optional[Issue]:
    if source.startswith("\n") != translation.startswith("\n"):
        return Issue("newline", ERROR, "start")
    if source.endswith("\n") != translation.endswith("\n"):
        return Issue("newline", ERROR, "end")
    return None


def check(entry: polib.POEntry, translations: Sequence[str]) -> List[Issue]:
    """Check translation(s) for an entry. Plural entries pass one string per form."""
    flags = list(entry.flags)
    is_plural = bool(entry.msgid_plural)
    issues: List[Issue] = []
    if any(not t for t in translations):
        issues.append(Issue("empty", ERROR))
        return issues
    for form, text in enumerate(translations):
        source = entry.msgid if (not is_plural or form == 0) else entry.msgid_plural
        for found in (
            _newline_issue(source, text),
            _accelerator_issue(source, text),
            _markup_issue(source, text),
        ):
            if found:
                issues.append(found)
        # A plural form may legitimately drop the number ("one file").
        issues.extend(_format_issues(flags, entry.msgid_plural if is_plural else source, text, strict=not is_plural))
    return _unique(issues)


def _unique(issues: List[Issue]) -> List[Issue]:
    seen: List[Tuple[str, str, str]] = []
    result = []
    for issue in issues:
        key = (issue.code, issue.severity, issue.detail)
        if key not in seen:
            seen.append(key)
            result.append(issue)
    return result


def has_errors(issues: Sequence[Issue]) -> bool:
    return any(i.severity == ERROR for i in issues)
