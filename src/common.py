"""
فункشن‌های مشترک: ارسال و ویرایش پیام در تلگرام (با تقسیم خودکار متن طولانی).

لیمیت یک پیام تلگرام 4096 کاراکتر است؛ متن‌های بلندتر در مرز خط‌ها
به چند پیامِ پشت‌سرهم تقسیم می‌شوند.

از نسخه‌ی ۳: پشتیبانی از parse_mode (برای لینک‌های قابل‌کلیک) +
تابع html_escape برای امن‌کردن متن‌های تولیدشده با هوش مصنوعی.
"""

import os
import time
import requests

MESSAGE_LIMIT = 4000  # لیمیت تلگرام 4096 است؛ کمی حاشیه‌ی امن نگه می‌داریم


def _tg_call(method: str, **params) -> dict:
    """یک روش Bot API تلگرام را صدا می‌زند و پاسخ را برمی‌گرداند."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده! Secret را در گیت‌هاب بررسی کنید.")
    url = f"https://api.telegram.org/bot{token}/{method}"
    resp = requests.post(url, json=params, timeout=60)
    if not resp.ok:
        # نمایش دقیق دلیل خطا (مثلاً chat not found یا bot not member)
        try:
            detail = resp.json().get("description", resp.text)
        except Exception:  # noqa: BLE001
            detail = resp.text
        raise RuntimeError(f"خطای تلگرام ({resp.status_code}) در {method}: {detail}")
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"خطای API تلگرام: {data}")
    return data


def html_escape(text: str) -> str:
    """کاراکترهای HTML را در متن خنثی می‌کند تا parse_mode=HTML به‌هم نریزد."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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


def send_message(text: str, chat_id: str | None = None, dry_run: bool = False,
                 parse_mode: str | None = None) -> list:
    """متن را به کانال می‌فرستد. اگر بلند باشد، به چند قسمتِ متوالی تقسیم می‌شود.

    برمی‌گرداند: لیستِ message_id پیام‌های ارسالی (در حالت DRY RUN خالی است).
    """
    parts = chunk_text(text)
    if dry_run:
        print("=" * 60)
        print(text)
        print("=" * 60)
        print(f"[DRY RUN] متن ارسال نشد ({len(parts)} قسمت).")
        return []
    chat_id = chat_id or os.environ["TELEGRAM_CHAT_ID"]
    ids = []
    for i, part in enumerate(parts):
        params = dict(
            chat_id=chat_id,
            text=part,
            disable_web_page_preview=False,
        )
        if parse_mode:
            params["parse_mode"] = parse_mode
        data = _tg_call("sendMessage", **params)
        ids.append(data["result"]["message_id"])
        if i < len(parts) - 1:
            time.sleep(1)  # وقفه‌ی یک ثانیه‌ای بین قسمت‌ها
    plural = " قسمت"
    print(f"✔ متن ارسال شد ({len(parts)}{plural}).")
    return ids


def edit_message(message_id: int, text: str, chat_id: str | None = None,
                 parse_mode: str | None = None) -> dict:
    """متنِ پیامی که قبلاً ارسال شده را ویرایش می‌کند."""
    chat_id = chat_id or os.environ["TELEGRAM_CHAT_ID"]
    params = dict(chat_id=chat_id, message_id=message_id, text=text)
    if parse_mode:
        params["parse_mode"] = parse_mode
    return _tg_call("editMessageText", **params)
