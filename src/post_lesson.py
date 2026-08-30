#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
پست جلسه‌ی آموزشی پیانو:

1) از data/progress.json می‌خواند جلسه‌ی بعدی کدام است
2) از Groq (هوش مصنوعی رایگان) می‌خواهد متن کامل آن جلسه را بنویسد
3) متن را به کانال تلگرام می‌فرستد (با تقسیم خودکار متن‌های بلند)
4) شمارنده‌ی پیشرفت را به‌روز می‌کند تا workflow آن را commit کند

مهم: فقط وقتی پست با موفقیت ارسال شد، پیشرفت به‌روز می‌شود.
اگر هر اتفاقی بیفتد، جلسه‌ی بعدی دوباره همین جلسه را می‌آزماید.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
from ai import groq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

SYSTEM_PROMPT = """تو یک معلم پیانوی باتجربه و صبور با بیش از ۲۰ سال سابقه‌ی تدریس هستی و درس‌نامه‌هایت را به زبان فارسی ساده، صمیمی و انگیزشی می‌نویسی — برای همه، از مبتلا مطلق تا سطح متوسط.

جلسه را دقیقاً با همین ساختار (به این ترتیب) بنویس:
۱) یک مقدمه‌ی ۲ تا ۳ خطی: چه‌چیزهایی را در جلسه‌ی قبل یاد گرفتیم و امروز چه می‌کنیم (به جلسه‌ی قبل اشاره کن).
۲) 📖 تئوری: مفهوم جلسه را خیلی ساده توضیح بده، با مثال و تشبیه از زندگی روزمره.
۳) 🤲 تمرین عملی: تمرین‌های شماره‌دار، گام‌به‌گام؛ برای هر تمرین مشخص کن کدام دست، کدام کلیدها، انگشت شماره‌ی چند، و با چه سرعتی.
۴) 🕐 برنامه‌ی تمرین امروز: یک برنامه‌ی تمرینی ۱۵ تا ۰ دقیقه‌ای که به بخش‌های زمانی تقسیم شده باشد.
۵) 💡 نکات مهم و اشتباهات رایج: ۳ تا ۵ مورد.
۶) 🔜 جلسه‌ی بعد: یک خط کوتاه، پیش‌نمایش جلسه‌ی بعد.

قوانین نگارش:
- متن خالص مناسب تلگرام؛ بدون تگ HTML یا مارک‌داون (بدون **, ##, [] و لینک).
- از ایموجی‌های ساده و رایج استفاده کن.
- طول کل جلسه: ۵۰۰ تا ۰۰ کلمه.
- خط عنوان و شماره‌ی جلسه را خودت بنویس؛ سیستم خودکار اضافه می‌کند.
- به اینکه هوش مصنوعی هستی اشاره نکن.
- فرض کن شاگرد همه‌ی جلسات قبل را کامل کرده است."""


def load_json(name: str):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def save_progress(progress: dict) -> None:
    with open(os.path.join(DATA_DIR, "progress.json"), "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def main() -> None:
    dry_run = os.environ.get("DRY_RUN") == "1"
    curriculum = load_json("curriculum.json")
    total = len(curriculum)
    progress = load_json("progress.json")
    n = progress.get("next_lesson", 1)

    # ── حالت: دوره به پایان رسیده ──────────────────────────────
    if n > total:
        if not progress.get("course_completed"):
            msg = (
                "🎓 دوره‌ی ۳۰ جلسه‌ای آموزش پیانو تمام شد!\n\n"
                "شما از صفر تا سطح متوسط پیش رفتید؛ حالا نوبت کتاب‌های درسی "
                "جدید و تمرین روزانه است.\n"
                "ممنون که همراه ما بودید 🙏"
            )
            common.send_message(msg, dry_run=dry_run)
            if not dry_run:
                progress["course_completed"] = True
                save_progress(progress)
                print("✔ پیام پایان دوره ارسال و ثبت شد.")
        else:
            print("همه‌ی جلسات ارسال شده و پیام پایان دوره هم فرستاده شده. کاری ندارم.")
        return

    lesson = curriculum[n - 1]
    prev_title = curriculum[n - 2]["title"] if n > 1 else "هیچ (این اولین جلسه است)"
    next_title = curriculum[n]["title"] if n < total else "دوره در همین جلسه تمام می‌شود"

    user_prompt = (
        f"شماره‌ی جلسه: {n} از مجموع {total} جلسه\n"
        f"موضوع این جلسه: {lesson['title']}\n"
        f"هدف این جلسه: {lesson.get('goal', '')}\n"
        f"جلسه‌ی قبل (تدریس‌شده، فرض کن شاگرد کامل یاد گرفته): {prev_title}\n"
        f"جلسه‌ی بعد (هنوز تدریس نشده): {next_title}\n\n"
        "متن کامل این جلسه را دقیقاً طبق قوانین بنویس."
    )

    print(f"✍️ در حال تولید جلسه {n}/{total}: {lesson['title']}")
    body = groq(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=3000,
    )

    header = f"🎹 دوره‌ی آموزش پیانو | جلسه‌ی {n} از {total}\n{lesson['title']}\n" + "─" * 34 + "\n\n"
    post = header + body

    common.send_message(post, dry_run=dry_run)

    if dry_run:
        print("ℹ️ حالت DRY RUN: پیشرفت به‌روز نمی‌شود.")
        return

    progress["next_lesson"] = n + 1
    progress["last_posted_lesson"] = n
    save_progress(progress)
    nxt = f"جلسه‌ی {n + 1}" if n + 1 <= total else "پایان دوره"
    print(f"✔ جلسه‌ی {n} ارسال شد. بعدی: {nxt}")


if __name__ == "__main__":
    main()
