#!/usr/bin/env python3
"""
Telegram-бот Xazhe Telegram Mod.
Только стандартная библиотека Python 3.8+, ничего устанавливать не нужно.

Запуск локально:
    export BOT_TOKEN="123456:ABC..."
    python3 xazhe_bot.py

На Render (Web Service) бот также поднимает мини-сервер на порту из PORT,
чтобы сервис не считался «упавшим» и его можно было пинговать.

Рядом со скриптом должен лежать файл banner.jpg (баннер).
"""

import html
import json
import mimetypes
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

# Логи сразу видны в Render (без буферизации)
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ============================ НАСТРОЙКИ ============================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")

CHANNEL_USERNAME = "@catcaslno"              # для проверки подписки
CHANNEL_URL = "https://t.me/catcaslno"       # кнопка «Подписаться»

SUPPORT_URL = "https://t.me/your_support"    # кнопка «Поддержка» — замените на свою

IOS_DOWNLOAD_URL = "https://wertigo.ru/shared-files/99448e95-5429-4efb-8b02-905b156461c6"
ANDROID_DOWNLOAD_URL = "https://wertigo.ru/shared-files/c3cdc42f-21b7-4b8c-bb74-a0462c24d3dc"

BANNER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banner.jpg")

# ===================================================================

API = f"https://api.telegram.org/bot{BOT_TOKEN}/"

SUBSCRIBED_STATUSES = {"creator", "administrator", "member", "restricted"}


# ----------------------------- Мини-сервер для Render -----------------------------

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass  # не засоряем логи пингами


def start_web_server():
    port = int(os.environ.get("PORT", "10000"))  # Render сам задаёт PORT
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"HTTP-сервер запущен на порту {port}")


# ----------------------------- Telegram API -----------------------------

def api(method, params=None, timeout=60):
    """Вызов метода Bot API (JSON)."""
    data = json.dumps(params or {}).encode("utf-8")
    req = urllib.request.Request(
        API + method, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"{method} failed: {result}")
    return result["result"]


def api_multipart(method, fields, file_field, file_path, timeout=60):
    """Вызов метода Bot API с загрузкой файла (multipart/form-data)."""
    boundary = uuid.uuid4().hex
    body = bytearray()

    for name, value in fields.items():
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        body += str(value).encode("utf-8") + b"\r\n"

    filename = os.path.basename(file_path)
    ctype = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    body += f"--{boundary}\r\n".encode()
    body += (
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode()
    body += file_bytes + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        API + method,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"{method} failed: {result}")
    return result["result"]


# ----------------------------- Вспомогательное -----------------------------

def btn(text, url=None, data=None):
    """Кнопка: либо со ссылкой (url), либо с callback_data."""
    if url:
        return {"text": text, "url": url}
    return {"text": text, "callback_data": data}


def kb(*rows):
    """Клавиатура из строк кнопок."""
    return {"inline_keyboard": [list(r) for r in rows]}


def is_subscribed(user_id):
    """Проверяет, подписан ли пользователь на канал."""
    try:
        member = api("getChatMember", {"chat_id": CHANNEL_USERNAME, "user_id": user_id})
        return member.get("status") in SUBSCRIBED_STATUSES
    except Exception as e:
        # Частая причина: бот не добавлен администратором в канал
        print(f"[warn] getChatMember error: {e}", file=sys.stderr)
        return False


def send_text(chat_id, text, markup=None):
    params = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if markup:
        params["reply_markup"] = markup
    api("sendMessage", params)


def send_subscribe_prompt(chat_id):
    send_text(
        chat_id,
        "🔒 Для использования бота подпишитесь на канал "
        f"{CHANNEL_USERNAME}, после чего нажмите /start",
        kb([btn("📢 Подписаться", url=CHANNEL_URL)]),
    )


# ----------------------------- Тексты и меню -----------------------------

def main_menu_markup():
    return kb(
        [btn("🍏 MOD (iOS)", data="mod_ios")],
        [btn("🤖 MOD (Android)", data="mod_android")],
        [btn("📖 Инструкция", data="instruction"), btn("💬 Поддержка", url=SUPPORT_URL)],
    )


def main_menu_text(user):
    if user.get("username"):
        name = f"@{html.escape(user['username'])}"
    else:
        name = html.escape(user.get("first_name", "друг"))

    return (
        "💎 <b>Xazhe Telegram</b>\n"
        "<i>Твоё оформление Telegram.</i>\n\n"
        f"Привет, {name}! Здесь можно узнать и установить "
        "<b>Xazhe Telegram Mod</b>\n\n"
        "🔎 <b>С чего начнём?</b>"
    )


BACK_BTN = btn("⬅️ В главное меню", data="menu")

TEXT_IOS = (
    "🍏 <b>Mod IOS - Телеграм мод на iPhone</b>\n\n"
    "Установите файл ниже.\n"
    "Для запуска мод панели нажмите три раза на кнопку «Чаты».\n\n"
    "💎 Пробная подписка 1 день (далее 5$ / месяц) — купить через поддержку!"
)

TEXT_ANDROID = (
    "🤖 <b>Mod Android</b>\n\n"
    "Установите файл ниже.\n"
    "Для запуска мод панели посмотрите во вкладке «Инструкция».\n\n"
    "🎁 Подписка бесплатная — навсегда!"
)

TEXT_INSTRUCTION = (
    "📖 <b>Инструкция по установке Mod Telegram</b>\n\n"
    "Выберите нужный раздел:"
)

TEXT_HOW_IOS = (
    "🍏 <b>Как скачать (Mod iOS)</b>\n\n"
    "После установки Xazhe Mod вы должны скачать через Scarlet или Esign или (ПК), "
    "после чего запускаете приложение и заходите в аккаунт.\n\n"
    "✅ Ура, вы успешно скачали и зашли в приложение!"
)

TEXT_HOW_ANDROID = (
    "🤖 <b>Как скачать (Mod Android)</b>\n\n"
    "После установки Xazhe Mod вы должны открыть приложение и войти в свой аккаунт, "
    "после чего установите готовый плагин для мода на визуал, NFT и т.д.\n\n"
    "✅ Готово!"
)

TEXT_HOW_MENU = (
    "⚙️ <b>Как включить (Мод меню)</b>\n\n"
    "🍏 <b>На iPhone:</b> нажмите три раза на кнопку «Чаты» снизу.\n\n"
    "🤖 <b>На Android:</b> откройте свой профиль в Telegram."
)


def send_main_menu(chat_id, user):
    text = main_menu_text(user)
    markup = main_menu_markup()

    if os.path.isfile(BANNER_PATH):
        try:
            api_multipart(
                "sendPhoto",
                {
                    "chat_id": chat_id,
                    "caption": text,
                    "parse_mode": "HTML",
                    "reply_markup": json.dumps(markup),
                },
                "photo",
                BANNER_PATH,
            )
            return
        except Exception as e:
            print(f"[warn] sendPhoto failed, fallback to text: {e}", file=sys.stderr)

    # Фолбэк, если баннера нет или загрузка не удалась
    send_text(chat_id, text, markup)


# ----------------------------- Обработчики -----------------------------

def handle_message(message):
    text = (message.get("text") or "").strip()
    if not text:
        return

    command = text.split()[0].split("@")[0].lower()
    if command != "/start":
        return

    chat_id = message["chat"]["id"]
    user = message.get("from", {})

    if is_subscribed(user.get("id")):
        send_main_menu(chat_id, user)
    else:
        send_subscribe_prompt(chat_id)


def handle_callback(cb):
    api("answerCallbackQuery", {"callback_query_id": cb["id"]})

    message = cb.get("message")
    if not message:
        return
    chat_id = message["chat"]["id"]
    user = cb.get("from", {})
    data = cb.get("data", "")

    if not is_subscribed(user.get("id")):
        send_subscribe_prompt(chat_id)
        return

    if data == "menu":
        send_main_menu(chat_id, user)

    elif data == "mod_ios":
        send_text(
            chat_id,
            TEXT_IOS,
            kb(
                [btn("⬇️ Скачать", url=IOS_DOWNLOAD_URL)],
                [btn("💬 Поддержка", url=SUPPORT_URL)],
                [BACK_BTN],
            ),
        )

    elif data == "mod_android":
        send_text(
            chat_id,
            TEXT_ANDROID,
            kb(
                [btn("⬇️ Скачать", url=ANDROID_DOWNLOAD_URL)],
                [btn("📖 Инструкция", data="instruction")],
                [BACK_BTN],
            ),
        )

    elif data == "instruction":
        send_text(
            chat_id,
            TEXT_INSTRUCTION,
            kb(
                [btn("🍏 Как скачать (Mod iOS)", data="how_ios")],
                [btn("🤖 Как скачать (Mod Android)", data="how_android")],
                [btn("⚙️ Как включить (Мод меню)", data="how_menu")],
                [BACK_BTN],
            ),
        )

    elif data == "how_ios":
        send_text(chat_id, TEXT_HOW_IOS, kb([btn("📖 Назад к инструкции", data="instruction")], [BACK_BTN]))

    elif data == "how_android":
        send_text(chat_id, TEXT_HOW_ANDROID, kb([btn("📖 Назад к инструкции", data="instruction")], [BACK_BTN]))

    elif data == "how_menu":
        send_text(chat_id, TEXT_HOW_MENU, kb([btn("📖 Назад к инструкции", data="instruction")], [BACK_BTN]))


def run():
    if BOT_TOKEN == "PUT_YOUR_TOKEN_HERE":
        sys.exit("Укажите токен: export BOT_TOKEN=... или впишите в BOT_TOKEN")

    # Открываем порт сразу, чтобы Render видел сервис
    start_web_server()

    me = api("getMe")
    print(f"Бот запущен: @{me.get('username')}")

    offset = None
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
            if offset is not None:
                params["offset"] = offset
            updates = api("getUpdates", params, timeout=40)

            for upd in updates:
                offset = upd["update_id"] + 1
                try:
                    if "message" in upd:
                        handle_message(upd["message"])
                    elif "callback_query" in upd:
                        handle_callback(upd["callback_query"])
                except Exception as e:
                    print(f"[error] handler: {e}", file=sys.stderr)
        except urllib.error.URLError as e:
            print(f"[warn] network: {e}", file=sys.stderr)
            time.sleep(5)
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    run()
