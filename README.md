# GNOME PO Translator — Telegram bot

Translate gettext `.po` files for GNOME and other open source projects right in
Telegram, from any phone, with nothing to install.

**Send the file → translate string by string → download the finished file.**

- Live bot and landing page: <https://azelinux.com/tools/poeditor>
- Made by a volunteer to support the GNOME translation community.
  Not an official GNOME product; GNOME is a trademark of the GNOME Foundation.

🇹🇷 [Türkçe](#türkçe) · 🇦🇿 [Azərbaycanca](#azərbaycanca)

## What it does

- Works like Gtranslator / Poedit, one string at a time: context, developer
  notes, source references, previous source of fuzzy strings.
- Choose what to work on: untranslated, fuzzy, both, or all strings.
- Plural forms are asked one by one, with example numbers for each form.
- Checks before saving: `%s`/`%d`/`%1$s`, `%(name)s`, `{name}` placeholders,
  `_` keyboard shortcuts, markup tags, line breaks. Errors that `msgfmt -c` would
  reject are blocked; likely mistakes are shown as warnings.
- Telegram trims messages, so leading/trailing line breaks and spaces are copied
  from the source automatically.
- On save the header is updated (`PO-Revision-Date`, `Last-Translator`,
  `Language-Team`, `Language`, `Plural-Forms`, `X-Generator`, translator line in
  the header comment). A `.pot` gets a proper header and is returned as
  `name.<lang>.po`.
- Entries you did not touch are written back byte for byte, and changed entries
  keep their `msgid` lines, so the diff only shows your translations.
- Interface in English, Turkish and Azerbaijani (the interface itself is
  translated with `.po` files in `app/locale/`).
- Files are deleted after 14 days without activity. No content is logged.

## How it runs

The bot is a small WSGI app (Python 3.8+, only dependency: `polib`). It uses a
Telegram **webhook**, so it runs on ordinary shared hosting (cPanel "Setup
Python App" / Passenger): no process has to stay alive, every update is a short
HTTPS request.

```
Telegram ──POST + secret header──▶ https://example.org/tools/poeditor/webhook
                                   (Passenger → app.web.App)
```

| Path | Purpose |
|---|---|
| `GET /` | Landing page; registers the webhook, commands and descriptions on first visit |
| `POST /webhook` | Telegram updates, verified with `X-Telegram-Bot-Api-Secret-Token` |
| `GET /health` | Returns `ok` |

State lives in `data/` next to the app (outside the web root): `bot.db`
(SQLite), `files/<user>/` working copies, `webhook_secret`, `logs/`.

## Deploy on cPanel

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. cPanel → **Setup Python App** → *Create application*
   - Python version: 3.8 or newer
   - Application root: `gnome-po-bot` (outside `public_html`)
   - Application URL: e.g. `yourdomain.com/tools/poeditor`
   - Startup file: `passenger_wsgi.py`, entry point: `application`
3. Put the code in the application root (cPanel **Git Version Control** can
   clone this repository there), then click *Run Pip Install* for
   `requirements.txt`.
4. Create `gnome-po-bot/.env` from `.env.example` with `BOT_TOKEN` and
   `BASE_URL` (the application URL with `https://`). Restart the app.
5. Open `BASE_URL` in a browser once. The page registers the webhook. Done.

> **Note:** when the app is created, cPanel replaces an existing
> `passenger_wsgi.py` with a template that loads itself (`RecursionError`, HTTP
> 500). Run `git checkout -- passenger_wsgi.py` in the application root and
> `touch tmp/restart.txt` afterwards.

To update: `git pull && touch tmp/restart.txt` in the application root.

Optional cron job (cPanel → Cron Jobs, every 10 minutes) that registers the
webhook if Telegram was unavailable at setup time and does nothing otherwise:

```
cd ~/gnome-po-bot && ~/virtualenv/gnome-po-bot/3.11/bin/python -m app.bootstrap --if-needed >/dev/null 2>&1
```

If `setWebhook` fails with "Failed to resolve host" (slow nameservers), set
`WEBHOOK_IP` in `.env` to the server's IP address.

If your site rewrites unknown paths to PHP (for example a front controller
that serves `/tools`), make sure the real directory created by Passenger is not
rewritten, and keep an explicit rule for any page that has the same name as the
new directory, e.g. `RewriteRule ^tools/?$ tools.php [L,QSA]`.

Optional settings: see `.env.example` (file size limit, retention, daily
upload limit, developer and source links shown in `/about`).

## Development

```bash
python -m venv .venv && .venv/bin/pip install polib pytest pytest-cov
.venv/bin/pytest --cov=app
python scripts/extract_messages.py   # refresh app/locale/messages.pot
```

To translate the interface into another language, copy `messages.pot` to
`app/locale/<code>.po`, translate it and add the code to `UI_LANGUAGES` in
`app/i18n.py`.

## License

GPL-3.0-or-later. Developer: Ramal Rahimov — <https://azelinux.com> —
Telegram [@rahimovramal](https://t.me/rahimovramal).

---

## Türkçe

GNOME ve diğer açık kaynak projelerin `.po` dosyalarını hiçbir program kurmadan,
telefondan Telegram üzerinden çevirmenizi sağlayan ücretsiz ve açık kaynak bir bot.
Dosyayı gönderin, metinleri Gtranslator mantığıyla tek tek çevirin, başlığı
güncellenmiş dosyayı indirin. Kurulum adımları yukarıdaki *Deploy on cPanel*
bölümündedir. Bot GNOME çeviri topluluğunu desteklemek için gönüllü olarak
yapılmıştır.

## Azərbaycanca

GNOME və digər açıq mənbəli layihələrin `.po` fayllarını heç bir proqram
qurmadan, telefondan Telegram vasitəsilə tərcümə etməyə imkan verən pulsuz və
açıq mənbəli bot. Faylı göndərin, sətirləri Gtranslator məntiqi ilə bir-bir
tərcümə edin, başlığı yenilənmiş faylı endirin. Quraşdırma addımları yuxarıdakı
*Deploy on cPanel* bölməsindədir. Bot GNOME tərcümə icmasını dəstəkləmək üçün
könüllü olaraq hazırlanıb.
