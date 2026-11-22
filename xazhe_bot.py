#!/usr/bin/env python3
"""
Telegram-бот Xazhe Telegram Mod.
Только стандартная библиотека Python 3.8+, ничего устанавливать не нужно.

Запуск:
    export BOT_TOKEN="123456:ABC..."
    python3 xazhe_bot.py

Рядом со скриптом должен лежать файл banner.jpg (баннер).
"""

import html
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

# ============================ НАСТРОЙКИ ============================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")

CHANNEL_USERNAME = "@catcaslno"              # для проверки подписки
CHANNEL_URL = "https://t.me/catcaslno"       # кнопка «Подписаться»

# Ссылки для кнопок — замените на свои
MOD_IOS_URL = "https://example.com/xazhe-ios"
MOD_ANDROID_URL = "https://example.com/xazhe-android"
INSTRUCTION_URL = "https://example.com/xazhe-instruction"
SUPPORT_URL = "https://t.me/your_support"

BANNER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banner.jpg")

# ===================================================================

API = f"https://api.telegram.org/bot{BOT_TOKEN}/"

SUBSCRIBED_STATUSES = {"creator", "administrator", "member", "restricted"}


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


# ----------------------------- Логика бота -----------------------------

def is_subscribed(user_id):
    """Проверяет, подписан ли пользователь на канал."""
    try:
        member = api("getChatMember", {"chat_id": CHANNEL_USERNAME, "user_id": user_id})
        return member.get("status") in SUBSCRIBED_STATUSES
    except Exception as e:
        # Частая причина: бот не добавлен администратором в канал
        print(f"[warn] getChatMember error: {e}", file=sys.stderr)
        return False


def subscribe_markup():
    return {
        "inline_keyboard": [
            [{"text": "📢 Подписаться", "url": CHANNEL_URL}],
        ]
    }


def main_markup():
    return {
        "inline_keyboard": [
            [{"text": "🍏 MOD (iOS)", "url": MOD_IOS_URL}],
            [{"text": "🤖 MOD (Android)", "url": MOD_ANDROID_URL}],
            [
                {"text": "📖 Инструкция", "url": INSTRUCTION_URL},
                {"text": "💬 Поддержка", "url": SUPPORT_URL},
            ],
        ]
    }


def main_text(user):
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


def send_subscribe_prompt(chat_id):
    api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                "🔒 Для использования бота подпишитесь на канал "
                f"{CHANNEL_USERNAME}, после чего нажмите /start"
            ),
            "reply_markup": subscribe_markup(),
        },
    )


def send_main_menu(chat_id, user):
    text = main_text(user)
    markup = main_markup()

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
    api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": markup,
        },
    )


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


def run():
    if BOT_TOKEN == "PUT_YOUR_TOKEN_HERE":
        sys.exit("Укажите токен: export BOT_TOKEN=... или впишите в BOT_TOKEN")

    me = api("getMe")
    print(f"Бот запущен: @{me.get('username')}")

    offset = None
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message"]}
            if offset is not None:
                params["offset"] = offset
            updates = api("getUpdates", params, timeout=40)

            for upd in updates:
                offset = upd["update_id"] + 1
                if "message" in upd:
                    try:
                        handle_message(upd["message"])
                    except Exception as e:
                        print(f"[error] handle_message: {e}", file=sys.stderr)
        except urllib.error.URLError as e:
            print(f"[warn] network: {e}", file=sys.stderr)
            time.sleep(5)
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    run()
