"""Collect the bot's interface strings into app/locale/messages.pot.

Finds ctx.t("..."), tr(lang, "...") and N_("...") calls. Run it after
changing interface texts, then update the .po files with msgmerge (or by hand):

    python scripts/extract_messages.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Dict, List

import polib

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
POT = APP / "locale" / "messages.pot"


def _literal(node: ast.AST) -> str:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else ""


def extract(root: Path = APP) -> Dict[str, List[str]]:
    """Return {msgid: ["file:line", ...]} for every marked string."""
    found: Dict[str, List[str]] = {}
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            msgid = ""
            if isinstance(func, ast.Attribute) and func.attr == "t":
                msgid = _literal(node.args[0])
            elif isinstance(func, ast.Name) and func.id == "N_":
                msgid = _literal(node.args[0])
            elif isinstance(func, ast.Name) and func.id == "tr" and len(node.args) > 1:
                msgid = _literal(node.args[1])
            if msgid:
                where = "{}:{}".format(path.relative_to(ROOT).as_posix(), node.lineno)
                found.setdefault(msgid, []).append(where)
    return found


def write_pot(messages: Dict[str, List[str]], path: Path = POT) -> None:
    pot = polib.POFile(wrapwidth=79)
    pot.metadata = {
        "Project-Id-Version": "gnope",
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
    }
    for msgid, places in messages.items():
        pot.append(polib.POEntry(msgid=msgid, msgstr="", occurrences=[tuple(p.rsplit(":", 1)) for p in places]))
    path.parent.mkdir(parents=True, exist_ok=True)
    pot.save(str(path))


if __name__ == "__main__":
    msgs = extract()
    write_pot(msgs)
    sys.stdout.write("{} strings -> {}\n".format(len(msgs), POT.relative_to(ROOT)))
