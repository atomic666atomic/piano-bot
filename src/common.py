#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
فункشن‌های مشترک: ارسال پیام به تلگرام (با تقسیم خودکار متن طولانی).

لیمیت یک پیام تلگرام 4096 کاراکتر است؛ اینجا متن‌های بلندتر را
در مرز پاراگراف‌ها به چند پیامِ پشت‌سرهم تقسیم می‌کنیم.
"""

import os
import time
import requests

MESSAGE_LIMIT = 4000  # لیمیت تلگرام 4096 است؛ کمی حاشیه‌ی امن نگه می‌داریم


def _tg_call(method: str, **params) -> dict:
    """یک روش Bot API تلگرام را صدا می‌زند و پاسخ را برمی‌گرداند."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/{method}"
    resp = requests.post(url, json=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"خطای API تلگرام: {data}")
    return data


def chunk_text(text: str, limit: int = MESSAGE_LIMIT) -> list:
    """متن بلند را در مرز خط‌ها/پاراگراف‌ها به تکه‌های زیر لیمیت تقسیم می‌کند."""
    chunks = []
    current = ""
    for para in text.split("\n"):
        # یک خطِ تکی که خودش از لیمیت بلندتر است: برش سخت
        while len(para) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(para[:limit])
            para = para[limit:]
        if len(current) + len(para) + 1 > limit:
            if current:
                chunks.append(current)
            current = para
        else:
            current = f"{current}\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks or [""]


def send_message(text: str, chat_id: str | None = None, dry_run: bool = False) -> None:
    """متن را به کانال می‌فرستد. اگر بلند باشد، به چند قسمتِ متوالی تقسیم می‌شود.

    در حالت dry_run (متغیر محیطی DRY_RUN=1) چیزی ارسال نمی‌شود و متن
    فقط روی خروجی چاپ می‌شود — برای تست بدون ریسک.
    """
    parts = chunk_text(text)
    if dry_run:
        print("=" * 60)
        print(text)
        print("=" * 60)
        print(f"[DRY RUN] متن ارسال نشد ({len(parts)} قسمت).")
        return
    chat_id = chat_id or os.environ["TELEGRAM_CHAT_ID"]
    for i, part in enumerate(parts):
        _tg_call(
            "sendMessage",
            chat_id=chat_id,
            text=part,
            disable_web_page_preview=False,
        )
        if i < len(parts) - 1:
            time.sleep(1)  # وقفه‌ی یک ثانیه‌ای بین قسمت‌ها
    plural = " قسمت" if len(parts) == 1 else " قسمت"
    print(f"✔ متن ارسال شد ({len(parts)}{plural}).")
