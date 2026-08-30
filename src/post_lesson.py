#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
پست جلسه‌ی آموزشی پیانو برای کانال Alipiano:

1) از data/progress.json می‌خواند جلسه‌ی بعدی کدام است
2) از Groq (هوش مصنوعی رایگان) می‌خواهد متن کامل آن جلسه را بنویسد
3) متن را با فرمت رسمی برند Alipiano (وب‌سایت + هشتگ‌ها + امضا) به کانال می‌فرستد
4) شمارنده‌ی پیشرفت را به‌روز می‌کند تا workflow آن را commit کند

مهم: فقط وقتی پست با موفقیت ارسال شد، پیشرفت به‌روز می‌شود.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
from ai import groq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

# ── هویت رسمی برند Alipiano ─────────────────────────────────
WEBSITE_LINE = "🔗 وب‌سایت رسمی: https://alipiano.ir"
CORE_HASHTAGS = "#Alipiano #AliBaghbani #OneHandOneDream #پیانو #پیانیست_تک‌دست"
SIGNATURE = "—\nAli Piano | One Hand, Infinite Emotions ✨"

FA_DIGITS = "".join(chr(0x06F0 + i) for i in range(10))


def brand_footer(extra_hashtags: str = "") -> str:
    """بخش پایانی ثابتِ همه‌ی پست‌ها: وب‌سایت + هشتگ‌ها + امضا."""
    tags = CORE_HASHTAGS + (f" {extra_hashtags}" if extra_hashtags else "")
    return f"{WEBSITE_LINE}\n\n{tags}\n\n{SIGNATURE}"


def fa_num(n: int) -> str:
    """عدد را به رقم فارسی تبدیل می‌کند: 3 -> ۳"""
    return str(n).translate(str.maketrans("0123456789", FA_DIGITS))


SYSTEM_PROMPT = """تو نویسنده‌ی رسمی کانال تلگرام «Alipiano» هستی؛ معلم پیانوی صبور، باتجربه و الهام‌بخش، که درس‌نامه‌ها را به فارسی گرم، ساده و امیدبخش می‌نویسی.

جلسه را دقیقاً با همین ساختار (به این ترتیب) بنویس:
۱) مقدمه‌ی ۲ خطی: چه‌چیزهایی را در جلسه‌ی قبل یاد گرفتیم و امروز چه می‌کنیم.
۲)  تئوری: توضیح ساده با مثال و تشبیه از زندگی روزمره.
۳)  تمرین عملی: تمرین‌های شماره‌دار؛ هر تمرین در یک تا دو خط کوتاه: کدام دست، کدام کلیدها، انگشت شماره‌ی چند، با چه سرعتی.
۴) 🕐 برنامه‌ی تمرین امروز: ۱۵ تا ۳۰ دقیقه، بخش‌بندی‌شده با زمان.
۵) 💡 نکات مهم و اشتباهات رایج: ۳ تا ۵ مورد، هر مورد یک خط.
۶) 🔜 جلسه‌ی بعد: یک خط پیش‌نمایش.

قوانین:
- خطوط کوتاه و خوانا بنویس؛ هرگز پاراگراف طولانی.
- متن خالص مناسب تلگرام؛ بدون تگ HTML یا مارک‌داون (بدون **, ##, [] و لینک).
- لحن: صمیمی، محترمانه و الهام‌بخش؛ محدودیت‌ها را به فرصت تبدیل کن.
- طول: ۵۰۰ تا ۸۰۰ کلمه.
- خط عنوان، شماره‌ی جلسه، وب‌سایت، هشتگ و امضا را خودت ننویس؛ سیستم اضافه می‌کند.
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
                "🎹 دوره‌ی آموزش پیانو به پایان رسید\n\n"
                f"شما {fa_num(total)} جلسه از صفر تا سطح متوسط را کامل کردید؛ "
                "حالا نوبت کتاب‌های درسی جدید و تمرین روزانه است.\n"
                "ممنون که همراه ما بودید 🙏\n\n"
                + brand_footer()
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

    header = f"🎹 دوره‌ی آموزش پیانو | جلسه‌ی {fa_num(n)} از {fa_num(total)}\n{lesson['title']}\n"
    post = header + "\n" + body + "\n\n" + brand_footer(extra_hashtags="#آموزش_پیانو")

    common.send_message(post, dry_run=dry_run)

    if dry_run:
        print("ℹ️ حالت DRY RUN: پیشرفت به‌روز نمی‌شود.")
        return

    progress["next_lesson"] = n + 1
    progress["last_posted_lesson"] = n
    save_progress(progress)
    nxt = f"جلسه‌ی {fa_num(n + 1)}" if n + 1 <= total else "پایان دوره"
    print(f"✔ جلسه‌ی {n} ارسال شد. بعدی: {nxt}")


if __name__ == "__main__":
    main()
