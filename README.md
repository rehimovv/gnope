# Gnope — translate gettext .po files from Telegram

Gnope is a free and open source Telegram bot for translating gettext `.po`
files. Send a file, translate it one string at a time and get the finished file
back, from any phone, with nothing to install. Made for GNOME translators, works
with any gettext project.

🇹🇷 [Türkçe](#türkçe) · 🇦🇿 [Azərbaycanca](#azərbaycanca)

## Get started

Open [@gnope_bot](https://t.me/gnope_bot) in Telegram and tap **Start**.
More about the bot: <https://azelinux.com/tools/poeditor>

## How to use it

1. Choose the interface language: English, Türkçe or Azərbaycanca.
2. Enter your name and email once. They go into the header of the files you
   save (`Last-Translator`, the translator line).
3. Send a `.po` or `.pot` file. If you translate for GNOME, reserve the file on
   [Damned Lies](https://l10n.gnome.org) first so that two people do not work on
   the same file.
4. Choose what to work on: untranslated, fuzzy, both, or all strings.
5. The bot shows one string at a time with its context, notes and source
   references. Reply with the translation, or use the buttons to skip, go back
   or keep a fuzzy translation.
6. Tap **Save file** (or send `/save`) to get the translated file. Upload it to
   Damned Lies or send it to your team.
7. Send `/cancel` to close the file and delete it from the server.

Other commands: `/continue`, `/status`, `/profile`, `/language`, `/help`,
`/about`.

## Features

- **Plural forms:** each form is asked separately, with example numbers. The
  plural rules of about 70 languages are built in.
- **Checks before saving:** placeholders (`%s`, `%d`, `%1$s`, `%(name)s`,
  `{name}`), `_` keyboard shortcuts, markup tags and line breaks. Mistakes that
  `msgfmt -c` would reject are blocked; likely mistakes are shown as warnings.
- **Header update:** `PO-Revision-Date`, `Last-Translator`, `Language-Team`,
  `Language`, `Plural-Forms` and the translator line are updated on save. A
  `.pot` file comes back as `name.<lang>.po`.
- **Small diffs:** strings you did not touch are written back exactly as they
  were.
- **Interface in three languages:** English, Turkish and Azerbaijani.

## Privacy

What the bot stores, on the server that runs it:

- your Telegram user ID, interface language, the name and email you entered
  for file headers, and the language you last translated into;
- the file you are working on and your progress in it;
- a daily upload counter, and the IDs of recent Telegram updates (kept for 3
  days, so an update is not processed twice).

How long:

- Your file is deleted as soon as you close it (`/cancel` → close), or after 14
  days without activity.
- Your name and email are kept so you do not have to enter them again. Change
  them with `/profile`; to have them removed, write to the developer.

What it does not do:

- File contents and translations are not written to logs. The log only records
  errors.
- Your files are not shared with anyone. Messages between Telegram and the bot
  pass through a small relay server that forwards them without storing
  anything.

Your chat with the bot stays in Telegram like any other chat.

## Translate the interface into your language

Would you like to see Gnope in your language? Translate the `.po` file in
[`app/locale/`](app/locale/) and send it:

1. Copy `app/locale/messages.pot` to `app/locale/<code>.po`, for example
   `de.po`.
2. Translate it with any PO editor, or with Gnope itself.
3. Add the language to `UI_LANGUAGES` in [`app/i18n.py`](app/i18n.py).
4. Open a pull request, or send the file to the developer.

When interface texts change, `python scripts/extract_messages.py` refreshes
`messages.pot`.

## Run your own copy

The bot is a small WSGI app (Python 3.8+, only dependency: `polib`). It uses a
Telegram webhook, so it runs on ordinary shared hosting such as cPanel's
**Setup Python App** (Passenger).

1. Create a bot with [@BotFather](https://t.me/BotFather).
2. Create a Python app whose root is outside `public_html`, and put this
   repository in it. Startup file: `passenger_wsgi.py`, entry point:
   `application`. Install `requirements.txt`.
3. Copy `.env.example` to `.env` and set `BOT_TOKEN` and `BASE_URL`.
4. Open `BASE_URL` in a browser once. This registers the webhook, the commands
   and the descriptions.

Notes:

- cPanel replaces an existing `passenger_wsgi.py` when the app is created. Run
  `git checkout -- passenger_wsgi.py` and `touch tmp/restart.txt` afterwards.
- If your host reaches Telegram badly, put `relay/telegram-relay.php` on another
  PHP host and set `TELEGRAM_RELAY_URL`. The file header explains the setup.
- Tests:
  ```bash
  pip install polib pytest && pytest
  ```

## License

GPL-3.0-or-later. Developer: Ramal Rahimov — <https://azelinux.com> —
Telegram [@rahimovramal](https://t.me/rahimovramal).

Gnope is an independent project. It is not affiliated with, authorized by,
sponsored by, or otherwise approved by the GNOME Foundation. GNOME is a
trademark of the GNOME Foundation.

---

## Türkçe

Gnope, gettext `.po` dosyalarını hiçbir program kurmadan, telefondan Telegram
üzerinden çevirmenizi sağlayan ücretsiz ve açık kaynak bir bottur. GNOME
çevirmenleri için yapıldı, her gettext projesiyle çalışır. Başlamak için
[@gnope_bot](https://t.me/gnope_bot)'u açın.

## Azərbaycanca

Gnope gettext `.po` fayllarını heç bir proqram qurmadan, telefondan Telegram
vasitəsilə tərcümə etməyə imkan verən pulsuz və açıq mənbəli botdur. GNOME
tərcüməçiləri üçün hazırlanıb, istənilən gettext layihəsi ilə işləyir.
Başlamaq üçün [@gnope_bot](https://t.me/gnope_bot)-u açın.
