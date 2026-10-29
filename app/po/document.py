"""A PO file that writes untouched entries back byte for byte.

Gettext separates entries with a blank line, so the file is split into
blocks on blank lines and each block is parsed on its own. Only blocks whose
entries changed, and the header when it was updated, are serialized again;
every other block is written back exactly as it was read. This keeps the
diff that reaches GNOME GitLab limited to the strings the translator touched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import polib

WRAP_WIDTH = 79

_BLOCK_SPLIT = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)*")
_CHARSET = re.compile(r"charset=([\w.-]+)", re.IGNORECASE)


class PoParseError(ValueError):
    """The uploaded file is not a readable PO file."""


@dataclass
class _Block:
    raw: str
    entries: List[polib.POEntry] = field(default_factory=list)
    is_header: bool = False
    dirty: bool = False


@dataclass(frozen=True)
class Stats:
    total: int
    translated: int
    fuzzy: int
    untranslated: int


def decode(data: bytes) -> str:
    """Decode PO bytes using the charset declared in the header (UTF-8 by default)."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    head = data[:4096].decode("ascii", errors="ignore")
    match = _CHARSET.search(head)
    charset = match.group(1) if match else "utf-8"
    if charset.upper() == "CHARSET":
        charset = "utf-8"
    try:
        return data.decode(charset)
    except (LookupError, UnicodeDecodeError) as exc:
        raise PoParseError("encoding: {}".format(exc)) from exc


_QUOTED = r'"(?:[^"\\]|\\.)*"\s*$'
_VALID_LINE = re.compile(r"^(?:(?:msgctxt|msgid|msgid_plural|msgstr(?:\[\d+\])?)\s+)?" + _QUOTED)


def _check_syntax(text: str) -> None:
    """polib silently truncates unterminated strings; reject them instead."""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not _VALID_LINE.match(stripped):
            raise PoParseError("syntax error near: {}".format(stripped[:60]))


def _parse_block(text: str) -> polib.POFile:
    _check_syntax(text)
    try:
        return polib.pofile(text + "\n", wrapwidth=WRAP_WIDTH)
    except (IOError, OSError, ValueError) as exc:
        raise PoParseError(str(exc)) from exc


def _is_header_block(text: str, parsed: polib.POFile) -> bool:
    return len(parsed) == 0 and bool(re.search(r'^msgid ""\s*$', text, re.MULTILINE))


def _header_parts(raw: str) -> Tuple[List[str], List[str]]:
    """Split a header block into its raw comment lines and its flags."""
    comments: List[str] = []
    flags: List[str] = []
    for line in raw.split("\n"):
        if line.startswith("#,"):
            flags.extend(f.strip() for f in line[2:].split(",") if f.strip())
        elif line.startswith("#"):
            comments.append(line)
        else:
            break
    return comments, flags


class PoDocument:
    """Parsed PO file with stable entry indices and minimal-diff serialization."""

    def __init__(self, blocks: List[_Block]) -> None:
        self._blocks = blocks
        self._index: List[Tuple[int, int]] = [
            (b, i) for b, block in enumerate(blocks) for i in range(len(block.entries))
        ]
        header = self._header_block()
        if header is None:
            self.metadata: Dict[str, str] = {}
            self.header_comments: List[str] = []
            self.header_flags: List[str] = []
        else:
            parsed = _parse_block(header.raw)
            self.metadata = dict(parsed.metadata)
            self.header_comments, self.header_flags = _header_parts(header.raw)
        self._header_dirty = False

    # -- loading -----------------------------------------------------------

    @classmethod
    def parse(cls, text: str) -> "PoDocument":
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
        if not text:
            raise PoParseError("empty file")
        blocks: List[_Block] = []
        for raw in _BLOCK_SPLIT.split(text):
            raw = raw.rstrip()
            if not raw:
                continue
            parsed = _parse_block(raw)
            if _is_header_block(raw, parsed) and not any(b.is_header for b in blocks):
                blocks.append(_Block(raw=raw, is_header=True))
            else:
                blocks.append(_Block(raw=raw, entries=list(parsed)))
        doc = cls(blocks)
        if not doc._index and doc._header_block() is None:
            raise PoParseError("no msgid entries found")
        return doc

    @classmethod
    def from_bytes(cls, data: bytes) -> "PoDocument":
        return cls.parse(decode(data))

    # -- entries -----------------------------------------------------------

    def __len__(self) -> int:
        return len(self._index)

    def entry(self, index: int) -> polib.POEntry:
        b, i = self._index[index]
        return self._blocks[b].entries[i]

    def mark_changed(self, index: int) -> None:
        b, _ = self._index[index]
        self._blocks[b].dirty = True

    def active_indices(self) -> List[int]:
        return [i for i in range(len(self)) if not self.entry(i).obsolete]

    def untranslated_indices(self) -> List[int]:
        return [i for i in self.active_indices() if _is_untranslated(self.entry(i))]

    def fuzzy_indices(self) -> List[int]:
        return [i for i in self.active_indices() if "fuzzy" in self.entry(i).flags]

    def stats(self) -> Stats:
        active = self.active_indices()
        fuzzy = len(self.fuzzy_indices())
        untranslated = len(self.untranslated_indices())
        return Stats(
            total=len(active),
            translated=len(active) - fuzzy - untranslated,
            fuzzy=fuzzy,
            untranslated=untranslated,
        )

    # -- header ------------------------------------------------------------

    def _header_block(self) -> Optional[_Block]:
        return next((b for b in self._blocks if b.is_header), None)

    def set_header(self, comments: List[str], flags: List[str], metadata: Dict[str, str]) -> None:
        self.header_comments = list(comments)
        self.header_flags = list(flags)
        self.metadata = dict(metadata)
        self._header_dirty = True
        if self._header_block() is None:
            self._blocks.insert(0, _Block(raw="", is_header=True))

    def _render_header(self) -> str:
        lines = list(self.header_comments)
        if self.header_flags:
            lines.append("#, " + ", ".join(self.header_flags))
        lines.append('msgid ""')
        lines.append('msgstr ""')
        for key, value in self.metadata.items():
            lines.append('"{}: {}\\n"'.format(key, polib.escape(value)))
        return "\n".join(lines)

    # -- output ------------------------------------------------------------

    def serialize(self) -> str:
        parts = []
        for block in self._blocks:
            if block.is_header:
                parts.append(self._render_header() if self._header_dirty else block.raw)
            elif block.dirty:
                parts.append(_render_changed(block))
            else:
                parts.append(block.raw)
        return "\n\n".join(parts) + "\n"

    def to_bytes(self) -> bytes:
        return self.serialize().encode("utf-8")


def format_field(keyword: str, value: str, width: int = WRAP_WIDTH) -> List[str]:
    """Quote a field the way gettext's msgcat does: break after '\\n' and spaces."""
    escaped = polib.escape(value)
    single = '{} "{}"'.format(keyword, escaped)
    inner_newline = "\\n" in escaped[:-2]
    if not inner_newline and len(single) <= width:
        return [single]
    lines = ['{} ""'.format(keyword)]
    for piece in re.split(r"(?<=\\n)", escaped):
        if not piece:
            continue
        current = ""
        for token in re.findall(r"[^ ]+ *| +", piece):
            if current and len(current) + len(token) + 2 > width:
                lines.append('"{}"'.format(current))
                current = ""
            current += token
        if current:
            lines.append('"{}"'.format(current))
    return lines


def _render_changed(block: _Block) -> str:
    """Re-render only what a translator can change; keep msgid lines as written."""
    if len(block.entries) != 1 or block.entries[0].obsolete:
        return "\n".join(e.__unicode__(wrapwidth=WRAP_WIDTH).rstrip("\n") for e in block.entries)
    entry = block.entries[0]
    keep_previous = entry.previous_msgid is not None
    comments: List[str] = []
    body: List[str] = []
    for line in block.raw.split("\n"):
        if line.startswith("msgstr"):
            break
        if line.startswith("#,") or (line.startswith("#|") and not keep_previous):
            continue
        (comments if line.startswith("#") and not body else body).append(line)
    previous = [line for line in comments if line.startswith("#|")]
    comments = [line for line in comments if not line.startswith("#|")]
    if entry.flags:
        comments.append("#, " + ", ".join(entry.flags))
    lines = comments + previous + body
    if entry.msgid_plural:
        for i in sorted(entry.msgstr_plural):
            lines += format_field("msgstr[{}]".format(i), entry.msgstr_plural[i])
    else:
        lines += format_field("msgstr", entry.msgstr)
    return "\n".join(lines)


def _is_untranslated(entry: polib.POEntry) -> bool:
    if "fuzzy" in entry.flags:
        return False
    if entry.msgid_plural:
        values = list(entry.msgstr_plural.values())
        return not values or not all(values)
    return not entry.msgstr
