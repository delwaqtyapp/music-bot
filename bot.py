import os
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from src.downloader import download_media
from src.separator import separate_audio

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"مرحبا {user.first_name} 🤗\n\n"
        f"أرسل لي رابط أي فيديو أو أغنية:\n\n"
        f"🎵 **رابط أغنية** → أفصل الموسيقى عن الصوت\n"
        f"🎬 **رابط فيديو** → أحمللك الصوت\n"
        f"📁 **رابط ملف** → أحمللك الملف\n\n"
        f"المنصات المدعومة:\n"
        f"YouTube • Facebook • Instagram • TikTok\n"
        f"Snapchat • Twitter • Spotify • SoundCloud\n"
        f"وغيرها كثير!\n\n"
        f"أرسل الرابط دلوقتي 👇"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    msg = await update.message.reply_text("⏳ جاري التحميل...")

    try:
        info = await download_media(text)
        if not info:
            await msg.edit_text("❌ الرابط غير مدعوم أو فشل التحميل")
            return

        file_path = info["file_path"]
        title = info["title"]
        duration = info.get("duration", "?")
        size = info.get("size", 0)

        await msg.edit_text(
            f"✅ تم التحميل!\n"
            f"🎵 {title}\n"
            f"⏱ {duration} | 💾 {size:.1f}MB\n\n"
            f"🔄 جاري فصل الصوت..."
        )

        result = await separate_audio(file_path)
        if result:
            await msg.edit_text("✅ تم فصل الصوت! جاري الإرسال...")

            with open(result["vocals"], 'rb') as f:
                await update.message.reply_audio(f, caption="🎤 الصوت بدون موسيقى")
            with open(result["music"], 'rb') as f:
                await update.message.reply_audio(f, caption="🎵 الموسيقى فقط")

            await msg.edit_text("✅ تم!")

            # Cleanup
            for p in [file_path, result["vocals"], result["music"]]:
                try: Path(p).unlink(missing_ok=True)
                except: pass
        else:
            await msg.edit_text("❌ تعذر فصل الصوت، جاري إرسال الملف الأصلي")
            with open(file_path, 'rb') as f:
                await update.message.reply_audio(f, caption=f"🎵 {title}")
            Path(file_path).unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text(f"❌ حدث خطأ: {str(e)[:100]}")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("غير مصرح لك ❌")
        return
    await update.message.reply_text(
        "🔐 لوحة التحكم\n\n"
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
