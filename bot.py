import os
import re
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from src.downloader import download_media, detect_platform, save_cookies, get_cookies_path, get_formats, DOWNLOAD_DIR
from src.separator import separate_audio, separate_video

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

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle audio/video file uploads from user"""
    user_id = update.effective_user.id
    msg = update.message
    file_id = None
    file_name = "media"
    is_video = False

    if msg.video:
        file_id = msg.video.file_id
        file_name = msg.video.file_name or f"video_{msg.video.file_id[:8]}.mp4"
        is_video = True
    elif msg.audio:
        file_id = msg.audio.file_id
        file_name = msg.audio.file_name or f"audio_{msg.audio.file_id[:8]}.mp3"
        is_video = False
    elif msg.voice:
        file_id = msg.voice.file_id
        file_name = f"voice_{msg.voice.file_id[:8]}.ogg"
        is_video = False
    elif msg.document:
        ext = Path(msg.document.file_name or "").suffix.lower()
        if ext in {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv'}:
            file_id = msg.document.file_id
            file_name = msg.document.file_name
            is_video = True
        elif ext in {'.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac', '.opus', '.wma'}:
            file_id = msg.document.file_id
            file_name = msg.document.file_name
            is_video = False
        else:
            return

    if not file_id:
        return

    reply = await msg.reply_text("📥 جاري تحميل الملف...")
    if msg.video:
        tg_file = await msg.video.get_file()
    elif msg.audio:
        tg_file = await msg.audio.get_file()
    elif msg.voice:
        tg_file = await msg.voice.get_file()
    elif msg.document:
        tg_file = await msg.document.get_file()
    else:
        return

    safe_name = Path(file_name).name
    file_path = DOWNLOAD_DIR / safe_name
    await tg_file.download_to_drive(file_path)

    size_mb = file_path.stat().st_size / (1024*1024)
    info = {
        "file_path": str(file_path),
        "title": Path(file_name).stem,
        "duration": "?",
        "size": size_mb,
    }

    url_key = f"file_{file_id[:16]}"
    if 'downloads' not in context.user_data:
        context.user_data['downloads'] = {}
    context.user_data['downloads'][url_key] = info

    icon = "🎬" if is_video else "🎵"
    keyboard = []
    if is_video:
        keyboard = [
            [InlineKeyboardButton("🎬 الفيديو الأصلي", callback_data=f"file|{url_key}"),
             InlineKeyboardButton("🎤 فيديو + صوت فقط", callback_data=f"video_vocals|{url_key}")],
            [InlineKeyboardButton("🎵 الصوت الأصلي", callback_data=f"audio|{url_key}"),
             InlineKeyboardButton("🎤 صوت بدون موسيقى", callback_data=f"audio_vocals|{url_key}")],
            [InlineKeyboardButton("🎵 موسيقى فقط", callback_data=f"audio_music|{url_key}")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🎤 صوت بدون موسيقى", callback_data=f"audio_vocals|{url_key}"),
             InlineKeyboardButton("🎵 موسيقى فقط", callback_data=f"audio_music|{url_key}")],
            [InlineKeyboardButton("🎵 الصوت الأصلي", callback_data=f"file|{url_key}")],
        ]
    keyboard.append([InlineKeyboardButton("ℹ️ معلومات", callback_data=f"info|{url_key}")])

    await reply.edit_text(
        f"{icon} تم استلام الملف\n"
        f"📁 {file_name}\n💾 {size_mb:.1f}MB\n\nاختر ما تريد:",
        reply_markup=InlineKeyboardMarkup(keyboard)
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
        icon = PLATFORM_ICONS.get(platform.lower(), "🔗")
        is_video_platform = any(p in platform.lower() for p in ['youtube', 'facebook', 'instagram', 'tiktok', 'snapchat', 'twitter', 'vimeo', 'dailymotion', 'twitch', 'linkedin'])

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

            title = info["title"]
            duration = info.get("duration", "?")
            size = info.get("size", 0)

            ext = Path(info["file_path"]).suffix.lower()
            VIDEO_EXTS = {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv'}
            AUDIO_EXTS = {'.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac', '.opus'}
            is_video = ext in VIDEO_EXTS

            keyboard = []
            if is_video_platform:
                # Always show ALL options for video platforms
                keyboard = [
                    [InlineKeyboardButton("🎬 الفيديو الأصلي", callback_data=f"file|{url}"),
                     InlineKeyboardButton("🎤 فيديو + صوت فقط", callback_data=f"video_vocals|{url}")],
                    [InlineKeyboardButton("🎵 الصوت الأصلي", callback_data=f"audio|{url}"),
                     InlineKeyboardButton("🎤 صوت بدون موسيقى", callback_data=f"audio_vocals|{url}")],
                    [InlineKeyboardButton("🎵 موسيقى فقط", callback_data=f"audio_music|{url}"),
                     InlineKeyboardButton("🎬 اختيار الجودة", callback_data=f"video|{url}")],
                ]
            elif is_video:
                keyboard = [
                    [InlineKeyboardButton("🎬 الفيديو الأصلي", callback_data=f"file|{url}"),
                     InlineKeyboardButton("🎤 فيديو + صوت فقط", callback_data=f"video_vocals|{url}")],
                    [InlineKeyboardButton("🎵 الصوت الأصلي", callback_data=f"audio|{url}"),
                     InlineKeyboardButton("🎤 صوت بدون موسيقى", callback_data=f"audio_vocals|{url}")],
                    [InlineKeyboardButton("🎵 موسيقى فقط", callback_data=f"audio_music|{url}")],
                ]
            else:
                keyboard = [
                    [InlineKeyboardButton("🎤 صوت بدون موسيقى", callback_data=f"audio_vocals|{url}"),
                     InlineKeyboardButton("🎵 موسيقى فقط", callback_data=f"audio_music|{url}")],
                    [InlineKeyboardButton("🎵 الصوت الأصلي", callback_data=f"file|{url}")],
                ]

            keyboard.append([InlineKeyboardButton("ℹ️ معلومات", callback_data=f"info|{url}")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await msg.edit_text(
                f"{icon} **{platform}**\n"
                f"🎵 {title}\n"
                f"⏱ {duration} | 💾 {size:.1f}MB\n\n"
                f"اختر ما تريد:",
                reply_markup=reply_markup
            )

            if 'downloads' not in context.user_data:
                context.user_data['downloads'] = {}
            context.user_data['downloads'][url] = info

        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            await msg.edit_text(f"❌ حدث خطأ: {str(e)[:100]}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
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

        if action == "info":
            fp = info["file_path"]
            await query.edit_message_text(
                f"ℹ️ **معلومات**\n\n"
                f"العنوان: {info['title']}\n"
                f"⏱ المدة: {info.get('duration', '?')}\n"
                f"💾 الحجم: {info.get('size', 0):.1f}MB\n"
                f"📁 النوع: {Path(fp).suffix}\n\n"
                f"تقدر تختار حاجة من القائمة 👇",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="back_start")
                ]])
            )

        elif action == "file":
            await query.edit_message_text("📥 جاري التحميل...")
            ext = Path(info["file_path"]).suffix.lower()
            VIDEO_EXTS = {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv'}
            AUDIO_EXTS = {'.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac', '.opus'}
            is_video_platform = any(p in url.lower() for p in ['youtube', 'facebook', 'instagram', 'tiktok', 'snapchat', 'twitter', 'vimeo'])
            if ext in AUDIO_EXTS and is_video_platform:
                new_info = await download_media(url, query.from_user.id, "bestvideo[height<=1080]+bestaudio/best[height<=1080]")
                if new_info:
                    await _send_file(query, new_info)
                    return
            await _send_file(query, info)

        elif action == "video":
            user_id = query.from_user.id
            await query.edit_message_text("🎬 جاري جلب الجودات...")
            formats = await get_formats(url, user_id)
            if formats:
                keyboard = []
                row = []
                for f in formats:
                    label = f"{f['resolution'] or f['id']} ({f['ext']})" if not f['is_audio'] else f"🎵 {f['ext']}"
                    cb = f"dload|{url}|{f['id']}"
                    if f['size']:
                        label += f" {f['size']}"
                    row.append(InlineKeyboardButton(label, callback_data=cb))
                    if len(row) >= 2:
                        keyboard.append(row)
                        row = []
                if row:
                    keyboard.append(row)
                keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"back|{url}")])
                await query.edit_message_text("🎬 اختر الجودة:", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.edit_message_text("📥 جاري تحميل الفيديو...")
                new_info = await download_media(url, user_id)
                await _send_file(query, new_info or info)

        elif action.startswith("dload"):
            _, url, fmt_id = query.data.split("|", 2)
            user_id = query.from_user.id
            await query.edit_message_text(f"📥 جاري التحميل بالجودة {fmt_id}...")
            new_info = await download_media(url, user_id, fmt_id)
            await _send_file(query, new_info or info)

        elif action == "back":
            url = query.data.split("|", 1)[1]
            await _show_file_options(query, url, context)

        elif action == "audio":
            user_id = query.from_user.id
            await query.edit_message_text("🎵 جاري تحميل الصوت الأصلي...")
            new_info = await download_media(url, user_id, "bestaudio/best")
            await _send_file(query, new_info or info)

        elif action == "audio_vocals":
            user_id = query.from_user.id
            await query.edit_message_text("🎤 جاري تحميل وفصل الصوت...")
            audio_info = await download_media(url, user_id, "bestaudio/best")
            if not audio_info:
                audio_info = info
            await query.edit_message_text("🎤 جاري فصل الصوت عن الموسيقى... ⏳")
            result = await separate_audio(audio_info["file_path"])
            if result:
                await query.edit_message_text("✅ تم! جاري الإرسال...")
                with open(result["vocals"], 'rb') as f:
                    await query.message.reply_audio(f, caption="🎤 صوت بدون موسيقى")
                await query.delete_message()
                for p in [audio_info["file_path"], result["vocals"], result["music"]]:
                    try: Path(p).unlink(missing_ok=True)
                    except: pass
            else:
                await query.edit_message_text("❌ تعذر فصل الصوت")

        elif action == "audio_music":
            user_id = query.from_user.id
            await query.edit_message_text("🎵 جاري تحميل وفصل الموسيقى...")
            audio_info = await download_media(url, user_id, "bestaudio/best")
            if not audio_info:
                audio_info = info
            await query.edit_message_text("🎵 جاري فصل الموسيقى عن الصوت... ⏳")
            result = await separate_audio(audio_info["file_path"])
            if result:
                await query.edit_message_text("✅ تم! جاري الإرسال...")
                with open(result["music"], 'rb') as f:
                    await query.message.reply_audio(f, caption="🎵 موسيقى فقط")
                await query.delete_message()
                for p in [audio_info["file_path"], result["vocals"], result["music"]]:
                    try: Path(p).unlink(missing_ok=True)
                    except: pass
            else:
                await query.edit_message_text("❌ تعذر فصل الموسيقى")

        elif action == "video_vocals":
            user_id = query.from_user.id
            await query.edit_message_text("🎤 جاري تحميل الفيديو وفصل الصوت...")
            video_info = await download_media(url, user_id)
            if not video_info:
                video_info = info
            await query.edit_message_text("🎤 جاري فصل الصوت واستبداله في الفيديو... ⏳")
            result_path = await separate_video(video_info["file_path"])
            if result_path:
                await query.edit_message_text("✅ تم! جاري الإرسال...")
                with open(result_path, 'rb') as f:
                    await query.message.reply_video(f, caption="🎤 فيديو + صوت فقط (بدون موسيقى)")
                await query.delete_message()
                for p in [video_info["file_path"], result_path]:
                    try: Path(p).unlink(missing_ok=True)
                    except: pass
            else:
                await query.edit_message_text("❌ تعذر فصل الصوت من الفيديو")

    except Exception as e:
        logger.error(f"Button callback error: {e}")
        try:
            await query.edit_message_text(f"❌ حدث خطأ: {str(e)[:100]}")
        except:
            pass

async def _send_file(query, info, action="file"):
    file_path = info["file_path"]
    ext = Path(file_path).suffix.lower()
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    VIDEO_EXTS = {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv'}
    AUDIO_EXTS = {'.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac', '.opus'}
    with open(file_path, 'rb') as f:
        if ext in AUDIO_EXTS:
            await query.message.reply_audio(f, caption=f"🎵 {info['title']}")
        elif ext in IMAGE_EXTS:
            await query.message.reply_photo(f, caption=f"🖼️ {info['title']}")
        elif ext in VIDEO_EXTS:
            await query.message.reply_video(f, caption=f"🎬 {info['title']}")
        else:
            await query.message.reply_document(f, caption=f"📁 {info['title']}")
    await query.delete_message()
    Path(file_path).unlink(missing_ok=True)

async def _show_file_options(query, url, context):
    downloads = context.user_data.get('downloads', {})
    info = downloads.get(url)
    if not info:
        await query.edit_message_text("❌ انتهت صلاحية الجلسة")
        return
    file_path = info["file_path"]
    ext = Path(file_path).suffix.lower()
    VIDEO_EXTS = {'.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv'}
    is_video = ext in VIDEO_EXTS
    keyboard = []
    if is_video:
        keyboard = [
            [InlineKeyboardButton("🎬 الفيديو الأصلي", callback_data=f"file|{url}"),
             InlineKeyboardButton("🎤 فيديو + صوت فقط", callback_data=f"video_vocals|{url}")],
            [InlineKeyboardButton("🎵 الصوت الأصلي", callback_data=f"audio|{url}"),
             InlineKeyboardButton("🎤 صوت بدون موسيقى", callback_data=f"audio_vocals|{url}")],
            [InlineKeyboardButton("🎵 موسيقى فقط", callback_data=f"audio_music|{url}"),
             InlineKeyboardButton("🎬 اختيار الجودة", callback_data=f"video|{url}")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🎤 صوت بدون موسيقى", callback_data=f"audio_vocals|{url}"),
             InlineKeyboardButton("🎵 موسيقى فقط", callback_data=f"audio_music|{url}")],
            [InlineKeyboardButton("🎵 الصوت الأصلي", callback_data=f"file|{url}")],
        ]
    keyboard.append([InlineKeyboardButton("ℹ️ معلومات", callback_data=f"info|{url}")])
    await query.edit_message_text(
        f"اختر ما تريد:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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
    app.add_handler(MessageHandler(filters.VIDEO | filters.AUDIO | filters.VOICE, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
