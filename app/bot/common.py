"""Welcome, interface language, profile, help and about."""

from __future__ import annotations

import re
from typing import Tuple

from app.bot import ui
from app.bot.context import Ctx
from app.i18n import UI_LANGUAGES

# Shown before a language is chosen, so it is always English.
FIRST_WELCOME = (
    "👋 Welcome to <b>Gnope</b>!\n\n"
    "Translate gettext <b>.po</b> files from Telegram: send a file, translate it "
    "string by string, and get the finished file back — right from your phone. "
    "Made for GNOME translators, works with any gettext project. Free and open source.\n\n"
    "Please choose your language:"
)

_EMAIL = re.compile(r"^[^@\s<>\"]+@[^@\s<>\"]+\.[^@\s<>\"]+$")
NAME_MIN, NAME_MAX = 2, 80


def ask_ui_language(ctx: Ctx) -> None:
    ctx.send(FIRST_WELCOME, ui.language_keyboard())


def welcome(ctx: Ctx) -> None:
    ctx.send(
        "👋 "
        + ctx.t("I help you translate gettext .po files right in Telegram.")
        + "\n\n1️⃣ "
        + ctx.t("Send me a .po or .pot file")
        + "\n2️⃣ "
        + ctx.t("Translate the strings one by one")
        + "\n3️⃣ "
        + ctx.t("Tap “Save file” to get the translated file back")
        + "\n\n🌍 "
        + ctx.t("Made for GNOME translators, works with any gettext project.")
        + "\n\n"
        + ctx.t("Commands: /help")
    )


def start(ctx: Ctx) -> None:
    if not ctx.user.ui_lang:
        ask_ui_language(ctx)
        return
    welcome(ctx)


def choose_ui_language(ctx: Ctx, code: str) -> None:
    if code not in UI_LANGUAGES:
        return
    first_time = not ctx.user.ui_lang
    ctx = ctx.update_user(ui_lang=code)
    ctx.send("✅ " + ctx.t("Interface language: {name}", name=UI_LANGUAGES[code]))
    if first_time:
        welcome(ctx)
        if not ctx.user.has_profile:
            ask_name(ctx, resume_upload=False)


def help_text(ctx: Ctx) -> None:
    lines = [
        "<b>{}</b>".format(ctx.t("How it works")),
        ctx.t("Send a .po or .pot file. I show the strings one at a time; reply with the translation. "
              "Line breaks and spaces at the start or end are copied from the source automatically."),
        "",
        "/continue — " + ctx.t("show the current string again"),
        "/status — " + ctx.t("progress of the current file"),
        "/save — " + ctx.t("get the translated file now"),
        "/cancel — " + ctx.t("close the current file"),
        "/profile — " + ctx.t("your name and email for the file header"),
        "/language — " + ctx.t("change the interface language"),
        "/about — " + ctx.t("about this bot"),
        "",
        "🔒 " + ctx.t("Files are deleted automatically after {days} days without activity.",
                      days=ctx.deps.config.retention_days),
    ]
    ctx.send("\n".join(lines))


def about(ctx: Ctx) -> None:
    cfg = ctx.deps.config
    lines = [
        "🤖 <b>Gnope</b> — " + ctx.t("translate gettext .po files from Telegram"),
        "",
        ctx.t("A free and open source tool made for GNOME translators. It works with any gettext project."),
        "",
        "👤 {}: <b>{}</b>".format(ctx.t("Developer"), ui.esc(cfg.developer_name)),
        "🌐 {}".format(ui.esc(cfg.developer_url)),
        "✈️ @{}".format(ui.esc(cfg.developer_telegram)),
        "💻 {}: {}".format(ctx.t("Source code (GPL-3.0)"), ui.esc(cfg.source_url)),
        "",
        "🔒 <b>{}</b>".format(ctx.t("Privacy")),
        "• " + ctx.t("Stored: your Telegram user ID, interface language, the name and email you entered for file "
                     "headers, the language you last translated into, and the file you are working on."),
        "• " + ctx.t("Your file is deleted when you close it (/cancel) or after {days} days without activity.",
                     days=cfg.retention_days),
        "• " + ctx.t("File contents and translations are not written to logs and are not shared with anyone."),
        "• " + ctx.t("Your name and email are kept so you do not have to enter them again; change them with /profile. "
                     "To have them removed, write to the developer."),
        "",
        "🌍 " + ctx.t("Would you like to see Gnope in your language? Translate the .po file in app/locale/ and send it."),
        "",
        "ℹ️ " + ctx.t("Gnope is an independent project. It is not affiliated with or approved by the GNOME Foundation. "
                      "GNOME is a trademark of the GNOME Foundation."),
    ]
    ctx.send("\n".join(lines))


def reserve_note(ctx: Ctx) -> None:
    """Reminder shown with each new file; it never blocks the upload."""
    if ctx.user.hide_reserve_note:
        return
    ctx.send(
        "💡 " + ctx.t("Translating for GNOME? Reserve the file on Damned Lies (l10n.gnome.org) first, "
                      "so that two people do not translate the same file."),
        ui.keyboard([[ui.button("🔕 " + ctx.t("Don't show this again"), "note:hide")]]),
    )


def hide_reserve_note(ctx: Ctx) -> None:
    ctx.update_user(hide_reserve_note=True)
    ctx.send("🔕 " + ctx.t("OK, I will not show this reminder again."))


def profile(ctx: Ctx) -> None:
    if not ctx.user.has_profile:
        ask_name(ctx, resume_upload=False)
        return
    text = "{}\n<code>Last-Translator: {} &lt;{}&gt;</code>".format(
        ctx.t("This is written to the header of every file you save:"),
        ui.esc(ctx.user.name),
        ui.esc(ctx.user.email),
    )
    ctx.send(text, ui.keyboard([[ui.button("✏️ " + ctx.t("Change"), "profile:edit")]]))


def ask_name(ctx: Ctx, resume_upload: bool) -> None:
    ctx = ctx.set_state("ask_name", resume=resume_upload)
    ctx.send("👤 " + ctx.t("What name should appear as the translator in the file header? Send your full name."))


def handle_name(ctx: Ctx, text: str) -> None:
    name = " ".join(text.split())
    if not NAME_MIN <= len(name) <= NAME_MAX or any(c in name for c in "<>\"@"):
        ctx.send(ctx.t("Please send just your name, for example: Ramal Rahimov"))
        return
    resume = bool(ctx.user.state_data.get("resume"))
    ctx = ctx.set_state("ask_email", name=name, resume=resume)
    ctx.send("✉️ " + ui.esc(ctx.t("Thanks! Now send your email address. GNOME files list each translator as Name <email>.")))


def handle_email(ctx: Ctx, text: str) -> Tuple[Ctx, bool]:
    """Save the profile. Returns the new context and whether an upload is waiting."""
    email = text.strip()
    if not _EMAIL.match(email) or len(email) > 120:
        ctx.send(ctx.t("That does not look like an email address. Please try again."))
        return ctx, False
    data = ctx.user.state_data
    resume = bool(data.get("resume"))
    ctx = ctx.update_user(name=data.get("name", ctx.user.name), email=email, state="", state_data={})
    ctx.send("✅ " + ctx.t("Saved: {signature}", signature=ui.esc("{} <{}>".format(ctx.user.name, email))))
    if not resume:
        ctx.send("📎 " + ctx.t("Now send me a .po or .pot file to start translating."))
    return ctx, resume
