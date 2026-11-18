"""Telegram Auto-Connector and Listener for GeoSketch.

Listens for the user's /start command on Telegram, captures the chat ID,
updates geosketch.db automatically, and sends a welcome confirmation back.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "backend", "geosketch.db")
ENV_PATH = os.path.join(ROOT_DIR, "backend", ".env")


def _load_token() -> str:
    token = os.environ.get("GEOSKETCH_TELEGRAM_BOT_TOKEN", "").strip()
    if token:
        return token
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEOSKETCH_TELEGRAM_BOT_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(
        "GEOSKETCH_TELEGRAM_BOT_TOKEN is not set in environment or backend/.env"
    )


TOKEN = _load_token()


def send_message(chat_id: int | str, text: str) -> bool:
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            res = json.loads(resp.read().decode())
            return bool(res.get("ok"))
    except Exception as e:
        print(f"[!] Send error: {e}")
        return False


def save_chat_id_to_db(chat_id: int | str) -> None:
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "UPDATE parents SET telegram_chat_id = ? WHERE email = 'parent@geosketch.local'",
            (str(chat_id),),
        )
        conn.commit()
        conn.close()
        print(f"[OK] Saved chat ID {chat_id} to geosketch.db for parent@geosketch.local")
    except Exception as e:
        print(f"[!] DB Error: {e}")


def main() -> None:
    print("=" * 60)
    print(" GeoSketch Telegram Bot Listener")
    print(f" Bot Username: @my_geosketch_bot")
    print(f" Direct Link:  https://t.me/my_geosketch_bot")
    print(" Waiting for you to click START in Telegram...")
    print("=" * 60)

    offset = None
    # Check if there are already pending updates
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/getUpdates")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            updates = data.get("result", [])
    except Exception as e:
        print(f"[!] Could not fetch updates: {e}")
        updates = []

    for item in updates:
        offset = item["update_id"] + 1
        msg = item.get("message", {})
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        text = msg.get("text", "")
        sender = chat.get("first_name", "User")
        if chat_id:
            print(f"[+] Found existing message from {sender} (Chat ID: {chat_id}): '{text}'")
            save_chat_id_to_db(chat_id)
            send_message(
                chat_id,
                f"🎉 Welcome {sender}!\n\nYour Telegram is now officially connected to GeoSketch Family Safe-Trip.\nYou will receive instant alerts for safe zone arrivals, departures, and emergency SOS.",
            )
            return

    # Polling loop (wait up to 15 minutes)
    start_time = time.time()
    while time.time() - start_time < 900:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?timeout=5"
        if offset:
            url += f"&offset={offset}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                for item in data.get("result", []):
                    offset = item["update_id"] + 1
                    msg = item.get("message", {})
                    chat = msg.get("chat", {})
                    chat_id = chat.get("id")
                    sender = chat.get("first_name", "User")
                    text = msg.get("text", "")
                    if chat_id:
                        print(f"\n[SUCCESS] Message received from {sender} (Chat ID: {chat_id})!")
                        save_chat_id_to_db(chat_id)
                        send_message(
                            chat_id,
                            f"🎉 Welcome {sender}!\n\nYour Telegram is now officially connected to GeoSketch Family Safe-Trip.\nYou will receive instant alerts for safe zone arrivals, departures, and emergency SOS.",
                        )
                        print(f"[OK] Confirmation sent to {sender} on Telegram!")
                        return
        except Exception as e:
            pass
        time.sleep(1)


if __name__ == "__main__":
    main()
