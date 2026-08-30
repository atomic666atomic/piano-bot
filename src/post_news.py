#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
پست اخبار روز:

1) از چند فید RSS معتبر و رایگان، خبرهای تازه (۳۶ ساعت اخیر) را جمع می‌کند
2) با کلیدواژه‌های پیانو/کلاسیک/AI به آن‌ها امتیاز می‌دهد و بهترین‌ها را انتخاب می‌کند
3) اگر GROQ_API_KEY داشته باشد، خلاصه‌ی فارسی هر خبر را با Groq می‌نویسد
   (اگر Groq در دسترس نباشد، توضیح کوتاه خود خبر استفاده می‌شود)
4) یک پست مرتب با عنوان، تاریخ شمسی، منبع و لینک هر خبر می‌فرستد
"""

import os
import re
import sys
import time
from datetime import datetime, timezone

import feedparser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
from ai import groq

# ── منابع خبری (RSS رایگان) ───────────────────────────────────
# می‌توانید آیتم‌ها را کم/زیاد کنید؛ کافی است هر کدام نام و آدرس RSS داشته باشد.
FEEDS = [
    {"name": "The Guardian (فرهنگ و هنر)", "url": "https://www.theguardian.com/culture/rss"},
    {"name": "BBC (سرگرمی و هنر)", "url": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"},
    {"name": "Ars Technica (هوش مصنوعی)", "url": "https://arstechnica.com/ai/feed/"},
    {"name": "MIT Technology Review (هوش مصنوعی)", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed"},
]

MAX_ITEMS = 4        # تعداد خبر در هر پست
MAX_AGE_HOURS = 36   # فقط خبرهای ۳۶ ساعت اخیر

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

# ارقام فارسی (U+06F0 تا U+06F9)
FA_DIGITS = "".join(chr(0x06F0 + i) for i in range(10))


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


def fallback_summary(item: dict) -> str:
    """وقتی AI در دسترس نیست: توضیح کوتاه خود خبر."""
    desc = strip_html(item["description"])
    if not desc:
        return item["title"]
    return desc[:160] + ("…" if len(desc) > 160 else "")


def summarize(items: list) -> list:
    """خلاصه‌ی فارسی هر خبر را با Groq می‌گیرد؛ اگر نشد، توضیح خود خبر را برمی‌گرداند."""
    listing = []
    for i, it in enumerate(items, 1):
        desc = strip_html(it["description"])[:400]
        listing.append(f"{i}. منبع: {it['source']}\n   عنوان: {it['title']}\n   توضیح: {desc}")

    user_prompt = (
        "خبرهای زیر را می‌بینی. برای هر خبر یک خلاصه‌ی یک تا دو خطی به فارسی ساده و روان بنویس.\n"
        "قوانین سخت:\n"
        f"- خروجی دقیقاً {len(items)} خط باشد، نه بیشتر، نه کمتر.\n"
        "- هر خط با شماره‌ی همان خبر و پرانتز بسته شروع شود، مثلاً: ۱)\n"
        "- هر خلاصه زیر ۱۸۰ کاراکتر باشد.\n"
        "- لینک، عنوان، یا کلمه‌ی اضافه ننویس؛ فقط خط‌های خلاصه.\n\n"
        + "\n\n".join(listing)
    )

    try:
        raw = groq(
            [
                {"role": "system", "content": "ویراستار خبری یک کانال تلگرام فارسی‌زبان درباره‌ی پیانو، موسیقی کلاسیک و هوش مصنوعی در موسیقی هستی."},
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
        summaries = [lines.get(i) or fallback_summary(it) for i, it in enumerate(items, 1)]
        print("✔ خلاصه‌سازی با Groq انجام شد.")
        return summaries
    except Exception as exc:  # noqa: BLE001
        print(f"⚠ خلاصه‌سازی با AI نشد ({exc}); از توضیح خود خبر استفاده می‌شود.")
        return [fallback_summary(it) for it in items]


def persian_date() -> str:
    """تاریخ امروز به شمسی و با نام‌های فارسی، مثلاً: شنبه، ۷ شهریور ۱۴۰"""
    try:
        import jdatetime
        jdatetime.set_locale(jdatetime.FA_LOCALE)  # نام روز و ماه به فارسی
        from jdatetime import datetime as jd
        date_line = jd.now().strftime("%A، %d %B %Y")
        return date_line.translate(str.maketrans("0123456789", FA_DIGITS))
    except Exception:  # noqa: BLE001
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def build_post(items: list, summaries: list) -> str:
    lines = [
        "📰 اخبار امروز در دنیای پیانو، موسیقی و AI",
        f"🗓 {persian_date()}",
        "",
    ]
    for i, (it, summary) in enumerate(zip(items, summaries), 1):
        lines.append(f"{i}) {summary}")
        lines.append(f"📎 منبع: {it['source']}")
        lines.append(f"🔗 {it['link']}")
        lines.append("")
    lines.append("🤖 این پست به‌صورت خودکار از فیدهای RSS معتبر جمع‌آوری و خلاصه شد.")
    return "\n".join(lines)


def main() -> None:
    dry_run = os.environ.get("DRY_RUN") == "1"
    items = collect_items()
    print(f"🔎 {len(items)} خبر انتخاب شد:")
    for i, it in enumerate(items, 1):
        print(f"  {i}) [{it['source']}] {it['title']}")

    summaries = summarize(items)
    post = build_post(items, summaries)
    common.send_message(post, dry_run=dry_run)
    if dry_run:
        print("ℹ️ حالت DRY RUN: پست ارسال نشد.")


if __name__ == "__main__":
    main()
