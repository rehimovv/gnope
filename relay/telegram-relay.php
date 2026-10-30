<?php
/*
 * Telegram relay for gnome-po-telegram-bot.
 *
 * Put this single file on any PHP host that talks to Telegram reliably when
 * the bot's own host does not (slow DNS, flaky routes to api.telegram.org):
 *
 *   Telegram  --webhook-->  this file  -->  BOT_WEBHOOK (the bot)
 *   the bot   --API call-->  this file  -->  api.telegram.org
 *
 * The relay stores nothing. It only forwards API calls for BOT_ID (which still
 * need the bot token to do anything), so it cannot be used as an open proxy.
 * Webhook calls are passed on with Telegram's secret header, which the bot
 * itself verifies. Set TELEGRAM_RELAY_URL in the bot's .env; RELAY_KEY is an
 * optional extra check (then also set TELEGRAM_RELAY_KEY).
 *
 * License: GPL-3.0-or-later
 */

// ---- configuration -------------------------------------------------------
const BOT_ID = 'CHANGE_ME';  // the number before ':' in the bot token (public)
const BOT_WEBHOOK = 'https://azelinux.com/tools/poeditor/webhook';
const RELAY_KEY = '';        // optional
// ---------------------------------------------------------------------------

const API_HOST = 'https://api.telegram.org';
const MAX_BODY = 8388608; // 8 MB

function reply($status, $body, $type = 'text/plain; charset=utf-8')
{
    http_response_code($status);
    header('Content-Type: ' . $type);
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    echo $body;
    exit;
}

function header_value($name)
{
    $key = 'HTTP_' . strtoupper(str_replace('-', '_', $name));
    return isset($_SERVER[$key]) ? (string) $_SERVER[$key] : '';
}

function forward($url, $method, $body, $headers, $timeout)
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST => $method,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HEADER => false,
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_CONNECTTIMEOUT => 10,
        CURLOPT_TIMEOUT => $timeout,
        CURLOPT_FOLLOWLOCATION => false,
        CURLOPT_PROTOCOLS => CURLPROTO_HTTPS,
        // Hosting firewalls (e.g. Imunify360) reject requests without a user agent.
        CURLOPT_USERAGENT => 'gnome-po-telegram-relay/1.0 (+https://github.com/rehimovv/gnome-po-telegram-bot)',
    ]);
    if ($method === 'POST') {
        curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
    }
    $out = curl_exec($ch);
    $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    $type = (string) curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
    $error = curl_error($ch);
    curl_close($ch);
    if ($out === false || $status === 0) {
        return [502, json_encode(['ok' => false, 'error_code' => 502, 'description' => 'relay: ' . $error]), 'application/json'];
    }
    return [$status, $out, $type ?: 'application/octet-stream'];
}

function key_ok($given)
{
    return RELAY_KEY === '' || ($given !== '' && hash_equals(RELAY_KEY, $given));
}

if (!ctype_digit(BOT_ID)) {
    reply(503, 'relay not configured');
}

$method = isset($_SERVER['REQUEST_METHOD']) ? $_SERVER['REQUEST_METHOD'] : 'GET';
$length = isset($_SERVER['CONTENT_LENGTH']) ? (int) $_SERVER['CONTENT_LENGTH'] : 0;
if ($length > MAX_BODY) {
    reply(413, 'too large');
}

// 1) Bot -> Telegram API
$path = header_value('X-Relay-Path');
if ($path !== '') {
    if (!key_ok(header_value('X-Relay-Key'))) {
        reply(403, 'forbidden');
    }
    $allowed = '#^/(?:file/)?bot' . BOT_ID . ':[A-Za-z0-9_-]+/[A-Za-z0-9_./-]+$#';
    if (!preg_match($allowed, $path) || strpos($path, '..') !== false) {
        reply(400, 'bad path');
    }
    $headers = ['Expect:'];
    $type = isset($_SERVER['CONTENT_TYPE']) ? $_SERVER['CONTENT_TYPE'] : '';
    if (stripos($type, 'multipart/form-data') === 0) {
        // PHP has already parsed multipart bodies into $_POST/$_FILES and
        // php://input is empty, so rebuild the form; curl sets the boundary.
        $body = $_POST;
        foreach ($_FILES as $field => $file) {
            if (is_array($file['tmp_name']) || $file['error'] !== UPLOAD_ERR_OK) {
                reply(400, 'bad upload');
            }
            $body[$field] = new CURLFile($file['tmp_name'], $file['type'], $file['name']);
        }
    } else {
        if ($type !== '') {
            $headers[] = 'Content-Type: ' . $type;
        }
        $body = $method === 'POST' ? file_get_contents('php://input') : '';
    }
    list($status, $out, $outType) = forward(API_HOST . $path, $method === 'POST' ? 'POST' : 'GET', $body, $headers, 60);
    reply($status, $out, $outType);
}

// 2) Telegram -> bot webhook
$secret = header_value('X-Telegram-Bot-Api-Secret-Token');
if ($method === 'POST' && $secret !== '') {
    $body = file_get_contents('php://input');
    $headers = [
        'Expect:',
        'Content-Type: application/json',
        'X-Telegram-Bot-Api-Secret-Token: ' . $secret,
    ];
    list($status, $out) = forward(BOT_WEBHOOK, 'POST', $body, $headers, 55);
    reply($status, $out);
}

// 3) Health check: ?check (=<RELAY_KEY> when one is set); returns status codes only
if (isset($_GET['check']) && key_ok((string) $_GET['check'])) {
    list($api) = forward(API_HOST . '/bot0:x/getMe', 'GET', '', [], 15);
    list($bot) = forward(BOT_WEBHOOK, 'POST', '{}', ['Content-Type: application/json'], 15);
    reply(200, json_encode(['telegram_api' => $api, 'bot_webhook' => $bot]), 'application/json');
}

reply(404, 'not found');
