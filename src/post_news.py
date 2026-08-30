#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
پست اخبار روز کانال Alipiano (نسخه‌ی ۴ — طبق راهنمای رسمی برند):

1) خبرهای تازه‌ی ۷۲ ساعت اخیر از فیدهای RSS معتبر
2) انتخاب بهترین خبرها با امتیازدهی (پیانو > کلاسیک > AI > موسیقی)
3) خلاصه‌ی فارسی: اول با Groq (کیفیت بالا)؛ اگر در دسترس نبود، ترجمه‌ی رایگان
4) پست نهایی با «ساختار ۱» برند:
   - سه لینک قابل‌کلیک (وب‌سایت رسمی، اسپاتیفای، اپل موزیک) — هرگز URL خام نمایش داده نمی‌شود
   - هشتگ‌ها و امضای ثابت در انتها
"""

import os
import re
import sys
import time
from datetime import datetime, timezone

import feedparser
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
from ai import groq

# ── هویت رسمی برند Alipiano ─────────────────────────────────
SEPARATOR = "─" * 20
WEBSITE_LINE = '🌐 <a href="https://alipiano.ir">وب‌سایت رسمی</a>'
SPOTIFY_LINE = '🎧 <a href="https://open.spotify.com/artist/3DYod604QbWaMTlV7MN6hN">اسپاتیفای</a>'
APPLE_LINE = '🍎 <a href="https://music.apple.com/us/artist/ali-baghbani/1828748850">اپل موزیک</a>'
CORE_HASHTAGS = "#Alipiano #علی_باغبانی #OneHandOneDream #پیانو"
SIGNATURE = "—\nAli Piano | One Hand, Infinite Emotions ✨"
CLOSING_LINE = "✨ یک‌ذره‌ی موسیقی در روز، دلت را تازه می‌کند"


def brand_links_block() -> str:
    """سه لینک رسمی برند به‌صورت متن قابل‌کلیک."""
    return f"{WEBSITE_LINE}\n{SPOTIFY_LINE}\n{APPLE_LINE}"


def brand_footer() -> str:
    """بخش پایانی ثابتِ همه‌ی پست‌ها: جداکننده + سه لینک + هشتگ‌ها + امضا."""
    return f"{SEPARATOR}\n{brand_links_block()}\n\n{CORE_HASHTAGS}\n\n{SIGNATURE}"


# ── منابع خبری (RSS رایگان) ─────────────────────────────────
# می‌توانید آیتم‌ها را کم/زیاد کنید؛ کافی است هر کدام نام کوتاه و آدرس RSS داشته باشد.
FEEDS = [
    {"name": "Guardian", "url": "https://www.theguardian.com/culture/rss"},
    {"name": "BBC", "url": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"},
    {"name": "Ars Technica", "url": "https://arstechnica.com/ai/feed/"},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed"},
]

MAX_ITEMS = 3          # تعداد خبر در هر پست (کوتاه و خوانا)
MAX_AGE_HOURS = 72     # فقط خبرهای ۷۲ ساعت اخیر

# امتیازدهی خبر: پیانو مهم‌تر، بعد موسیقی کلاسیک و AI، بعد موسیقی به‌طور کلی
# (هر گروه فقط یک‌بار اعمال می‌شود)
KEYWORD_SCORES = [
    (3, ["piano", "pianist", "پیانو", "کلاویه"]),
    (2, [
        "classical", "orchestra", "symphony", "sonata", "concerto", "composer",
        "beethoven", "bach", "chopin", "mozart", "liszt", "rahmaninoff",
        "shostakovich", "schubert", "opera", "conservatory",
    ]),
    (2, [
        "artificial intelligence", "machine learning", "generative",
        "ai music", "music ai", "suno", "udio", "neural", "llm",
    ]),
    (1, ["music", "album", "song", "festival", "record", "concert", "موسیقی"]),
]

# کلمات منفی: اگر خبر درباره‌ی این‌ها باشد، امتیاز کم می‌شود (مثل اخبار بازی ویدئویی)
NEGATIVE_KEYWORDS = [
    "video game", "videogame", "witcher", "xbox", "playstation", "nintendo",
    "anime", "k-pop", "esport", "e-sport",
]

FA_DIGITS = "".join(chr(0x06F0 + i) for i in range(10))


def fa_num(n: int) -> str:
    """عدد را به رقم فارسی تبدیل می‌کند: 3 -> ۳"""
    return str(n).translate(str.maketrans("0123456789", FA_DIGITS))


def strip_html(text: str) -> str:
    """تگ‌های HTML و فاصله‌های اضافی را از متن برمی‌دارد."""
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def score_item(title: str, description: str) -> int:
    text = f"{title} {description}".lower()
    score = 0
    for points, words in KEYWORD_SCORES:
        if any(w in text for w in words):
            score += points
    if any(w in text for w in NEGATIVE_KEYWORDS):
        score -= 3
    return score


def collect_items() -> list:
    """از همه‌ی فیدها خبرهای تازه و مرتبط را جمع می‌کند."""
    now = datetime.now(timezone.utc)
    candidates = []
    seen = set()
    failed_feeds = 0

    for feed in FEEDS:
        try:
            parsed = feedparser.parse(feed["url"], agent="Mozilla/5.0 (PianoBot/1.0)")
            entries = parsed.entries[:30]
        except Exception as exc:  # noqa: BLE001
            failed_feeds += 1
            print(f"⚠ فید {feed['name']} قابل خواندن نبود: {exc}")
            continue
        if not entries:
            failed_feeds += 1
            print(f"⚠ فید {feed['name']} خالی بود.")
            continue

        for e in entries:
            link = e.get("link", "").strip()
            if not link or link in seen:
                continue
            seen.add(link)

            ts = e.get("published_parsed") or e.get("updated_parsed")
            age_hours = 0.0
            if ts:
                pub = datetime.fromtimestamp(time.mktime(ts), tz=timezone.utc)
                age_hours = (now - pub).total_seconds() / 3600
            if age_hours > MAX_AGE_HOURS:
                continue

            title = re.sub(r"\s+", " ", (e.get("title") or "")).strip()
            description = e.get("summary") or e.get("description") or ""
            if not title:
                continue

            candidates.append({
                "title": title,
                "description": description,
                "link": link,
                "source": feed["name"],
                "age_hours": age_hours,
                "score": score_item(title, description),
            })

    if not candidates and failed_feeds == len(FEEDS):
        raise RuntimeError("هیچ فیدی خوانده نشد! شبکه‌ی سرور را بررسی کنید.")
    if not candidates:
        raise RuntimeError("هیچ خبر تازه‌ای در فیدها پیدا نشد.")

    # مرتب‌سازی: اولویت با امتیاز بالاتر، در امتیاز برابر با تازه‌تر
    candidates.sort(key=lambda x: (x["score"], -x["age_hours"]), reverse=True)

    top = [c for c in candidates if c["score"] > 0][:MAX_ITEMS]
    if len(top) < 2:  # اگر خبر مرتبط کم بود، با تازه‌ترین‌ها کامل کن
        top = candidates[:MAX_ITEMS]
    return top[:MAX_ITEMS]


def translate_to_persian(texts: list) -> list:
    """ترجمه‌ی رایگان به فارسی (بدون کلید API) — وقتی Groq در دسترس نیست.
    اولویت: MyMemory (معتبر و پایدار روی سرور)، بعد Google gtx، در نهایت متن اصلی."""
    results = []
    for t in texts:
        translated = None
        # گزینه‌ی ۱: MyMemory
        try:
            r = requests.get(
                "https://api.mymemory.translated.net/get",
                params={"q": t, "langpair": "en|fa"},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            if str(data.get("responseStatus")) == "200":
                translated = (data.get("responseData") or {}).get("translatedText")
        except Exception:  # noqa: BLE001
            pass
        # گزینه‌ی ۲: Google (gtx)
        if not translated:
            try:
                r = requests.get(
                    "https://translate.googleapis.com/translate_a/single",
                    params={"client": "gtx", "sl": "en", "tl": "fa", "dt": "t", "q": t},
                    timeout=20,
                )
                r.raise_for_status()
                data = r.json()
                translated = "".join(part[0] for part in data[0] if part and part[0]).strip()
            except Exception:  # noqa: BLE001
                pass
        results.append(translated or t)
    return results


def summarize(items: list) -> list:
    """خلاصه‌ی فارسی هر خبر: اول Groq (کیفیت بالا)، بعد ترجمه‌ی رایگان عنوان."""
    if os.environ.get("GROQ_API_KEY"):
        try:
            listing = []
            for i, it in enumerate(items, 1):
                desc = strip_html(it["description"])[:400]
                listing.append(f"{i}. منبع: {it['source']}\n   عنوان: {it['title']}\n   توضیح: {desc}")

            user_prompt = (
                "خبرهای زیر را می‌بینی. برای هر خبر یک خلاصه‌ی یک خطی (حداکثر ۱۴۰ کاراکتر) به فارسی ساده و گرم بنویس.\n"
                "قوانین سخت:\n"
                f"- خروجی دقیقاً {len(items)} خط باشد، نه بیشتر، نه کمتر.\n"
                "- هر خط با شماره‌ی همان خبر و پرانتز بسته شروع شود، مثلاً: ۱)\n"
                "- لحن: صمیمی و الهام‌بخش، مثل یک پیانیست حرفه‌ای.\n"
                "- لینک، عنوان انگلیسی، یا کلمه‌ی اضافه ننویس؛ فقط خط‌های خلاصه.\n\n"
                + "\n\n".join(listing)
            )
            raw = groq(
                [
                    {"role": "system", "content": "شما نویسنده‌ی رسمی کانال تلگرام Alipiano (علی باغبانی، پیانیست تک‌دست) هستید و متن‌ها را فارسی، گرم و کوتاه می‌نویسید."},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=900,
            )
            lines = {}
            for line in raw.splitlines():
                m = re.match(r"^\s*(\d+)\s*[)）:：]?\s*(.+)$", line.strip())
                if m:
                    lines[int(m.group(1))] = m.group(2).strip()
            summaries = [lines.get(i) or strip_html(it["title"])[:140] for i, it in enumerate(items, 1)]
            print("✔ خلاصه‌سازی با Groq انجام شد.")
            return summaries
        except Exception as exc:  # noqa: BLE001
            print(f"⚠ Groq در دسترس نبود ({exc}); از ترجمه‌ی رایگان استفاده می‌شود.")
    else:
        print("ℹ️ GROQ_API_KEY تنظیم نشده؛ از ترجمه‌ی رایگان عنوان‌ها استفاده می‌شود.")

    return translate_to_persian([it["title"][:140] for it in items])


def persian_date() -> str:
    """تاریخ امروز به شمسی و با نام‌های فارسی."""
    try:
        import jdatetime
        jdatetime.set_locale(jdatetime.FA_LOCALE)
        from jdatetime import datetime as jd
        date_line = jd.now().strftime("%A، %d %B %Y")
        return date_line.translate(str.maketrans("0123456789", FA_DIGITS))
    except Exception:  # noqa: BLE001
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def build_post(items: list, summaries: list) -> str:
    """پست نهایی دقیقاً با «ساختار ۱» برند Alipiano.
    طبق قوانین سخت برند: هیچ URL خامی نمایش داده نمی‌شود؛
    سه لینک (وب‌سایت، اسپاتیفای، اپل موزیک) به‌صورت متن قابل‌کلیک در انتها."""
    lines = [
        "🎹 اخبار امروز در دنیای موسیقی",
        "",
        f"({persian_date()})",
    ]
    for i, (it, summary) in enumerate(zip(items, summaries), 1):
        lines.append(f"{fa_num(i)}) {summary} ({it['source']})")
    body = "\n".join(lines)
    return (
        f"{common.html_escape(body)}\n\n"
        f"{CLOSING_LINE}\n\n"
        f"{brand_footer()}"
    )


def main() -> None:
    dry_run = os.environ.get("DRY_RUN") == "1"
    items = collect_items()
    print(f"🔎 {len(items)} خبر انتخاب شد:")
    for i, it in enumerate(items, 1):
        print(f"  {i}) [{it['source']}] {it['title']}")

    summaries = summarize(items)
    post = build_post(items, summaries)
    common.send_message(post, dry_run=dry_run, parse_mode="HTML")
    if dry_run:
        print("ℹ️ حالت DRY RUN: پست ارسال نشد.")


if __name__ == "__main__":
    main()
