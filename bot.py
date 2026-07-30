import os
import re
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from src.downloader import download_media, detect_platform, save_cookies, get_cookies_path
from src.separator import separate_audio

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

PLATFORM_ICONS = {
    "youtube": "▶️", "youtube music": "🎵", "youtube shorts": "▶️",
    "facebook": "📘", "facebook reels": "📘", "facebook stories": "📘",
    "instagram": "📸", "instagram reels": "📸", "instagram stories": "📸", "instagram post": "📸",
    "tiktok": "🎵", "tiktok video": "🎵", "tiktok photo": "📸",
    "snapchat": "👻", "snapchat spotlight": "👻", "snapchat story": "👻",
    "snapchat profile": "👻", "snapchat add": "👻", "snapchat lens": "👻",
    "snapchat discover": "👻", "snapchat link": "👻",
    "twitter": "🐦", "spotify": "🎧",
    "soundcloud": "🎶", "vimeo": "🎬", "dailymotion": "📺", "twitch": "🎮",
    "reddit": "🤖", "pinterest": "📌", "telegram": "✈️", "whatsapp": "💬",
    "linkedin": "💼", "linkedin post": "💼", "linkedin feed": "💼",
    "linkedin learning": "📚", "linkedin event": "📅",
}

COOKIES_DIR = Path("cookies")
COOKIES_DIR.mkdir(exist_ok=True)

def extract_urls(text):
    return re.findall(r'https?://[^\s]+', text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    has_cookies = get_cookies_path(user.id) is not None
    keyboard = [
        [InlineKeyboardButton("📋 طريقة الاستخدام", callback_data="howto")],
    ]
    if not has_cookies:
        keyboard.append([InlineKeyboardButton("🍪 رفع Cookies", callback_data="cookie_help")])
    await update.message.reply_text(
        f"مرحبا {user.first_name} 🤗\n\n"
        f"أرسل لي رابط أي فيديو أو أغنية وهختارلك أنسب حاجة:\n\n"
        f"🎵 **أغنية** → افصل الموسيقى عن الصوت\n"
        f"🎬 **فيديو** → حمل الصوت أو الفيديو\n"
        f"📁 **رابط مباشر** → حمل الملف\n"
        f"🍪 **cookies** → عشان الاستوريهات\n\n"
        f"المنصات المدعومة:\n"
        f"▶️ YouTube • 📘 Facebook • 📸 Instagram\n"
        f"🎵 TikTok • 👻 Snapchat • 🐦 Twitter\n"
        f"🎧 Spotify • 🎶 SoundCloud • 💼 LinkedIn\n"
        f"وغيرها ١٠٠٠+\n\n"
        f"أرسل الرابط الآن 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def howto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📋 **طريقة الاستخدام**\n\n"
        "1. أرسل رابط فيديو أو أغنية\n"
        "2. البوت يكتشف المنصة تلقائيًا\n"
        "3. يظهرلك خيارات: تحميل - فصل صوت - معلومات\n"
        "4. استلم النتيجة\n\n"
        "تقدر ترسل أكثر من رابط في نفس الرسالة!\n\n"
        "🍪 **للاستوريهات:**\n"
        "ارسلي /cookies وارفع ملف cookies.txt\n"
        "هتشتغل استوريهات فيسبوك، انستا، سناب\n\n"
        "مثال:\n"
        "https://youtu.be/xxx\n"
        "https://tiktok.com/xxx\n\n"
        "✅ يدعم YouTube Music • Spotify • SoundCloud\n"
        "✅ يدعم Facebook • Instagram • TikTok • Twitter\n"
        "✅ يدعم Snapchat • Reddit • Vimeo • Twitch\n"
        "✅ يدعم LinkedIn • أي رابط تحميل مباشر",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data="back_start")
        ]])
    )

async def cookie_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🍪 **طريقة رفع Cookies**\n\n"
        "عشان تحمل استوريهات وبوستات خاصة، محتاج ترفع ملف cookies:\n\n"
        "1. ثبت إضافة متصفح:\n"
        "   • Chrome: 'Get cookies.txt' (من المتجر)\n"
        "   • Firefox: 'cookies.txt' (من الإضافات)\n\n"
        "2. افتح فيسبوك/انستا/سناب وسجل دخول\n\n"
        "3. استخدم الإضافة → Export cookies → هينزل ملف cookies.txt\n\n"
        "4. أرسل الملف للبوت بعد /cookies\n\n"
        "⚠️ ملف cookies ده سري جدًا!\n"
        "خلي بالك متشاركوش مع حد",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data="back_start")
        ]])
    )

async def back_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    has_cookies = get_cookies_path(user.id) is not None
    keyboard = [
        [InlineKeyboardButton("📋 طريقة الاستخدام", callback_data="howto")],
    ]
    if not has_cookies:
        keyboard.append([InlineKeyboardButton("🍪 رفع Cookies", callback_data="cookie_help")])
    await query.edit_message_text(
        f"مرحبا {user.first_name} 🤗\n\n"
        f"أرسل لي رابط أي فيديو أو أغنية وهختارلك أنسب حاجة:\n\n"
        f"🎵 **أغنية** → افصل الموسيقى عن الصوت\n"
        f"🎬 **فيديو** → حمل الصوت أو الفيديو\n"
        f"📁 **رابط مباشر** → حمل الملف\n"
        f"🍪 **cookies** → عشان الاستوريهات\n\n"
        f"أرسل الرابط الآن 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cookies_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🍪 أرسل ملف **cookies.txt** دلوقتي\n\n"
        "افتح فيسبوك/انستا/سناب في المتصفح وسجل دخول\n"
        "استخدم إضافة 'Get cookies.txt'\n"
        "→ Export → ارفع الملف هنا"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name or not doc.file_name.endswith('.txt'):
        return
    user_id = update.effective_user.id
    content = await doc.get_file()
    cookies_path = COOKIES_DIR / f"{user_id}.txt"
    await content.download_to_drive(cookies_path)
    if save_cookies(user_id, str(cookies_path)):
        await update.message.reply_text(
            "✅ تم حفظ الـ cookies بنجاح!\n\n"
            "دلوقتي تقدر تحمل:\n"
            "📘 استوريهات فيسبوك\n"
            "📸 استوريهات انستا\n"
            "👻 استوريهات سناب شات\n"
            "💼 بوستات LinkedIn\n\n"
            "أرسل الرابط وجرب!"
        )
    else:
        await update.message.reply_text("❌ فشل في حفظ الـ cookies، تأكد من صحة الملف")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    urls = extract_urls(text)

    if not urls:
        await update.message.reply_text("❌ ما لقيت رابط في رسالتك!\nأرسل رابط يوتيوب، فيسبوك، تيك توك، الخ...")
        return

    for url in urls:
        platform = detect_platform(url)
        icon = PLATFORM_ICONS.get(platform, "🔗")

        msg = await update.message.reply_text(
            f"{icon} تم اكتشاف: **{platform}**\n"
            f"🔗 {url[:50]}...\n\n"
            f"⏳ جاري التحميل..."
        )

        try:
            info = await download_media(url, update.effective_user.id)
            if not info:
                await msg.edit_text(f"❌ فشل تحميل الرابط: {url[:50]}")
                continue

            file_path = info["file_path"]
            title = info["title"]
            duration = info.get("duration", "?")
            size = info.get("size", 0)

            ext = Path(file_path).suffix.lower()
            IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
            VIDEO_EXTS = {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv'}
            AUDIO_EXTS = {'.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac', '.opus'}

            keyboard = []
            if ext in AUDIO_EXTS or ext in {'.m4a', '.wma'}:
                keyboard = [
                    [InlineKeyboardButton("🎤 فصل الصوت", callback_data=f"separate|{url}")],
                    [InlineKeyboardButton("📥 تحميل الملف", callback_data=f"file|{url}")],
                ]
            elif ext in VIDEO_EXTS:
                keyboard = [
                    [InlineKeyboardButton("🎵 تحميل الصوت", callback_data=f"audio|{url}")],
                    [InlineKeyboardButton("🎬 تحميل الفيديو", callback_data=f"video|{url}")],
                ]
            else:
                action = "file"
                keyboard = [[InlineKeyboardButton("📥 تحميل الملف", callback_data=f"file|{url}")]]

            keyboard.append([InlineKeyboardButton("ℹ️ معلومات", callback_data=f"info|{url}")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await msg.edit_text(
                f"{icon} **{platform}**\n"
                f"🎵 {title}\n"
                f"⏱ {duration} | 💾 {size:.1f}MB\n\n"
                f"اختر ما تريد:",
                reply_markup=reply_markup
            )

            # Store info for callback
            if 'downloads' not in context.user_data:
                context.user_data['downloads'] = {}
            context.user_data['downloads'][url] = info

        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            await msg.edit_text(f"❌ حدث خطأ: {str(e)[:100]}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "howto":
        await howto(update, context)
        return
    if query.data == "back_start":
        await back_start(update, context)
        return
    if query.data == "cookie_help":
        await cookie_help(update, context)
        return

    action, url = query.data.split("|", 1)
    downloads = context.user_data.get('downloads', {})
    info = downloads.get(url)

    if not info:
        await query.edit_message_text("❌ انتهت صلاحية الجلسة، أرسل الرابط تاني")
        return

    file_path = info["file_path"]

    if action == "separate":
        await query.edit_message_text("🎤 جاري فصل الصوت... ⏳")
        result = await separate_audio(file_path)
        if result:
            await query.edit_message_text("✅ تم! جاري الإرسال...")
            with open(result["vocals"], 'rb') as f:
                await query.message.reply_audio(f, caption="🎤 صوت بدون موسيقى")
            with open(result["music"], 'rb') as f:
                await query.message.reply_audio(f, caption="🎵 الموسيقى فقط")
            await query.delete_message()
            for p in [file_path, result["vocals"], result["music"]]:
                try: Path(p).unlink(missing_ok=True)
                except: pass
        else:
            await query.edit_message_text("❌ تعذر فصل الصوت، جرب ملف تاني")

    elif action == "info":
        await query.edit_message_text(
            f"ℹ️ **معلومات**\n\n"
            f"العنوان: {info['title']}\n"
            f"⏱ المدة: {info.get('duration', '?')}\n"
            f"💾 الحجم: {info.get('size', 0):.1f}MB\n"
            f"📁 النوع: {Path(file_path).suffix}\n\n"
            f"تقدر تختار حاجة من القائمة 👇",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="back_start")
            ]])
        )

    elif action in ("audio", "video", "file"):
        await query.edit_message_text("📥 جاري التحميل...")
        ext = Path(file_path).suffix.lower()
        IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        VIDEO_EXTS = {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv'}
        AUDIO_EXTS = {'.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac', '.opus'}
        with open(file_path, 'rb') as f:
            if action == "audio" or ext in AUDIO_EXTS:
                await query.message.reply_audio(f, caption=f"🎵 {info['title']}")
            elif ext in IMAGE_EXTS:
                await query.message.reply_photo(f, caption=f"🖼️ {info['title']}")
            elif ext in VIDEO_EXTS or action == "video":
                await query.message.reply_video(f, caption=f"🎬 {info['title']}")
            else:
                await query.message.reply_document(f, caption=f"📁 {info['title']}")
        await query.delete_message()
        Path(file_path).unlink(missing_ok=True)

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("غير مصرح لك ❌")
        return
    await update.message.reply_text(
        "🔐 **لوحة التحكم**\n\n"
        "البوت شغال ✅\n"
        "/start للعودة"
    )

def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN غير موجود!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("cookies", cookies_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
