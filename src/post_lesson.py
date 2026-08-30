#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
پست جلسه‌ی آموزشی پیانو برای کانال Alipiano:

1) از data/progress.json می‌خواند جلسه‌ی بعدی کدام است
2) از Groq (هوش مصنوعی رایگان) می‌خواهد متن کامل آن جلسه را بنویسد
3) پست را دقیقاً با «ساختار شماره ۲» راهنمای برند می‌سازد و به کانال می‌فرستد
4) بعد از ارسال، «📌 جلسه کامل: لینک همین پست» را به‌صورت خودکار اضافه می‌کند
5) شمارنده‌ی پیشرفت را به‌روز می‌کند تا workflow آن را commit کند

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
SEPARATOR = "─" * 20
WEBSITE_LINE = "🌐 وب‌سایت: https://alipiano.ir"
SPOTIFY_LINE = "🎧 اسپاتیفای: https://open.spotify.com/artist/3DYod604QbWaMTlV7MN6hN"
APPLE_LINE = "🍎 اپل موزیک: https://music.apple.com/us/artist/ali-baghbani/1828748850"
LESSON_HASHTAGS = "#Alipiano #آموزش_پیانو #علی_باغبانی #OneHandOneDream #پیانو"
SIGNATURE = "—\nAli Piano | One Hand, Infinite Emotions ✨"

FA_DIGITS = "".join(chr(0x06F0 + i) for i in range(10))


def fa_num(n: int) -> str:
    """عدد را به رقم فارسی تبدیل می‌کند: 3 -> ۳"""
    return str(n).translate(str.maketrans("0123456789", FA_DIGITS))


def brand_footer() -> str:
    """بخش پایانی ثابت پست‌های آموزشی: جداکننده + لینک‌ها + هشتگ‌ها + امضا."""
    return (
        f"{SEPARATOR}\n📎 لینک‌ها:\n{WEBSITE_LINE}\n{SPOTIFY_LINE}\n{APPLE_LINE}\n\n"
        f"{LESSON_HASHTAGS}\n\n{SIGNATURE}"
    )


SYSTEM_PROMPT = """تو نویسنده‌ی رسمی کانال تلگرام «Alipiano» هستی؛ معلم پیانوی صبور و باتجربه که درس‌نامه‌ها را به فارسی روان، گرم و صمیمی می‌نویسی.

جلسه را دقیقاً با همین ساختار بنویس:
۱) خوش‌آمدگویی گرمِ ۲ خطی که با «سلام دوست عزیزم 🌿» شروع شود و هدف امروز را کوتاه بگوید.
۲) یک خط جداکننده از ۲۰ کاراکتر ─
۳) «📚 تئوری امروز:» و بعد توضیح کوتاه و ساده با فاصله‌گذاری خوب، با مثال و تشبیه از زندگی روزمره.
۴) یک خط جداکننده از ۲۰ کاراکتر ─
۵) «🎯 تمرین عملی:» و بعد تمرین‌های شماره‌دار (۱. . ۳. ...)؛ هر تمرین در یک خط کوتاه، با مشخص کردن کدام دست، کدام کلیدها، انگشت شماره‌ی چند و سرعت.
۶) یک خط جداکننده از ۲۰ کاراکتر ─
۷) «⏱ برنامه پیشنهادی امروز:» و بعد یک برنامه‌ی ۱۵ تا ۳۰ دقیقه‌ای که به بخش‌های ۵ تا ۱۰ دقیقه‌ای تقسیم شده و هر بخش با • شروع شود.

قوانین:
- فارسی روان، گرم و صمیمی؛ خطوط کوتاه و خوانا.
- یک تا دو نکته‌ی مهم یا اشتباه رایج را طبیعی داخل تئوری یا تمرین‌ها بگنج.
- متن خالص؛ بدون تگ HTML یا مارک‌داون.
- طول: ۳۵۰ تا ۰۰ کلمه.
- عنوان و شماره‌ی جلسه را خودت ننویس؛ بخش «📎 لینک‌ها»، هشتگ‌ها و امضا را هم ننویس — سیستم اضافه می‌کند.
- هیچ لینکی در متن ننویس.
- به اینکه هوش مصنوعی هستی اشاره نکن.
- فرض کن شاگرد همه‌ی جلسات قبل را کامل کرده است."""


def load_json(name: str):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def save_progress(progress: dict) -> None:
    with open(os.path.join(DATA_DIR, "progress.json"), "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def add_self_link(post: str, message_id: int) -> str | None:
    """لینکِ خودِ پست (📌 جلسه کامل) را به بخش لینک‌ها اضافه می‌کند.
    فقط وقتی می‌توان متن را در همان اندازه در یک پیام جا داد، برمی‌گردد."""
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    username = chat_id[1:] if chat_id.startswith("@") else None
    if not username:
        return None
    link = f"https://t.me/{username}/{message_id}"
    new_post = post.replace(APPLE_LINE, f"{APPLE_LINE}\n📌 جلسه کامل: {link}")
    return new_post if len(new_post) <= 4000 else None


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
        "متن کامل این جلسه را دقیقاً طبق ساختار و قوانین بنویس."
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

    header = f"🎹 دوره آموزش پیانو | جلسه {fa_num(n)} از {fa_num(total)}\n\n{lesson['title']}\n\n"
    post = header + body + "\n\n" + brand_footer()

    ids = common.send_message(post, dry_run=dry_run)

    # ── اضافه‌کردن خودکار «📌 جلسه کامل» بعد از ارسال ──────────────
    if not dry_run and len(ids) == 1:
        full = add_self_link(post, ids[0])
        if full:
            try:
                common.edit_message(ids[0], full)
                print("✔ لینک «📌 جلسه کامل» به پست اضافه شد.")
            except Exception as exc:  # noqa: BLE001
                print(f"⚠ لینک «📌 جلسه کامل» اضافه نشد ({exc}) — پست کامل است، فقط بدون این لینک.")

    if dry_run:
        print("ℹ️ حالت DRY RUN: پیشرفت به‌روز نمی‌شود.")
        return

    progress["next_lesson"] = n + 1
    progress["last_posted_lesson"] = n
    save_progress(progress)
    nxt = f"جلسه {fa_num(n + 1)}" if n + 1 <= total else "پایان دوره"
    print(f"✔ جلسه {fa_num(n)} ارسال شد. بعدی: {nxt}")


if __name__ == "__main__":
    main()
