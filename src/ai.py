#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گفت‌وگو با Groq (API سازگار با OpenAI) — با ری‌تِری خودکار.

Groq یک API رایگان است (بدون کارت بانکی) و بسیار سریع.
مدل پیش‌فرض: llama-3.3-70b-versatile
برای تعویض مدل، متغیر محیطی GROQ_MODEL را set کنید.
"""

import os
import time
import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_RETRIES = 4


def groq(messages, temperature: float = 0.7, max_tokens: int = 3000, model: str | None = None) -> str:
    """یک درخواست chat به Groq می‌فرستد و متن مدل را برمی‌گرداند.

    در صورت خطای شبکه یا rate-limit، چند بار با وقفه‌ی فزاینده تکرار می‌شود.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY تنظیم نشده! آن را در Secrets رپوی گیت‌هاب ثبت کنید.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=180)
            if resp.status_code == 429:  # rate limit خورده
                wait = 30 * attempt
                print(f"⏳ rate limit Groq؛ {wait} ثانیه صبر می‌کنم (تلاش {attempt}/{MAX_RETRIES})...")
                time.sleep(wait)
                last_error = "rate limit (429)"
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(f"⚠ خطا در Groq (تلاش {attempt}/{MAX_RETRIES}): {exc}")
            time.sleep(10 * attempt)

    raise RuntimeError(f"API Groq بعد از {MAX_RETRIES} تلاش هم ناموفق بود: {last_error}")
