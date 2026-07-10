
import os
import re
import subprocess
import urllib.parse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============== تنظیمات از Environment Variables ==============
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # توکن از Railway میاد
if not TOKEN:
    raise ValueError("❌ توکن ربات پیدا نشد! متغیر TELEGRAM_BOT_TOKEN رو تنظیم کن.")

DOWNLOAD_FOLDER = os.getenv("DOWNLOAD_FOLDER", "downloads")
# ==============================================================

# ایجاد پوشه دانلود
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# لیست سایت‌های پشتیبانی‌شده
SUPPORTED_SITES = """
📺 ویدئو: YouTube, Vimeo, Dailymotion, Twitch, Facebook, TikTok, Instagram, Twitter, Reddit
🎵 موسیقی: SoundCloud, Bandcamp, Mixcloud, Audiomack
📱 شبکه‌های اجتماعی: VK, Tumblr, Flickr, LinkedIn
🎮 گیمینگ: Trovo, AfreecaTV, DLive
🌐 خبری: CNN, BBC, TED, Khan Academy
و بیش از ۱۸۰۰ سایت دیگه...
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🎬 ربات دانلودر!\n\n"
        f"هر لینکی بفرستی تشخیص می‌دم و فیلمش رو دانلود می‌کنم.\n\n"
        f"✅ سایت‌های پشتیبانی‌شده:\n{SUPPORTED_SITES}\n\n"
        f"فقط کافیه لینک رو بفرستی، بقیه اش با من 😊"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎯 راهنما:\n\n"
        "1️⃣ لینک ویدیو از هر سایتی رو بفرست\n"
        "2️⃣ ربات خودکار تشخیص میده چه سایتی هست\n"
        "3️⃣ فیلم رو دانلود و برات می‌فرسته\n"
        "4️⃣ اگه فیلم آهنگ داشته باشه، آهنگ رو هم جداگانه می‌فرسته\n"
        "5️⃣ اگه نتونه آهنگ رو استخراج کنه، لینک جستجوی گوگل رو میده\n\n"
        "✅ پشتیبانی از بیش از ۱۸۰۰ سایت مختلف"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    
    # بررسی لینک بودن
    if not re.match(r'https?://', url):
        await update.message.reply_text("❌ لطفاً یه لینک معتبر بفرست (با http یا https شروع بشه).")
        return
    
    # تشخیص خودکار سایت از روی لینک
    site_name = "سایت ناشناخته"
    if "youtube.com" in url or "youtu.be" in url:
        site_name = "YouTube"
    elif "instagram.com" in url:
        site_name = "Instagram"
    elif "tiktok.com" in url:
        site_name = "TikTok"
    elif "twitter.com" in url or "x.com" in url:
        site_name = "Twitter/X"
    elif "facebook.com" in url or "fb.com" in url:
        site_name = "Facebook"
    elif "twitch.tv" in url:
        site_name = "Twitch"
    elif "vimeo.com" in url:
        site_name = "Vimeo"
    elif "soundcloud.com" in url:
        site_name = "SoundCloud"
    elif "reddit.com" in url:
        site_name = "Reddit"
    elif "dailymotion.com" in url:
        site_name = "Dailymotion"
    
    await update.message.reply_text(
        f"✅ لینک تشخیص داده شد: {site_name}\n"
        f"⏳ در حال دانلود... ممکنه چند دقیقه طول بکشه."
    )
    
    video_path = os.path.join(DOWNLOAD_FOLDER, f"{user_id}_video.mp4")
    audio_path = os.path.join(DOWNLOAD_FOLDER, f"{user_id}_audio.mp3")
    
    try:
        # مرحله 1: دانلود ویدیو
        cmd_video = [
            "yt-dlp",
            "-f", "best[ext=mp4]/best",
            "--no-playlist",
            "-o", video_path,
            "--socket-timeout", "30",
            url
        ]
        
        process = subprocess.run(cmd_video, capture_output=True, text=True, timeout=300)
        
        if process.returncode != 0:
            error_msg = process.stderr[:200] if process.stderr else "خطای ناشناخته"
            await update.message.reply_text(f"❌ دانلود فیلم ناموفق: {error_msg}")
            return
        
        if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
            await update.message.reply_text("❌ فایل دانلود نشد یا خالی هست.")
            return
        
        # مرحله 2: دریافت عنوان برای جستجوی آهنگ
        title_cmd = ["yt-dlp", "--get-title", url]
        title_process = subprocess.run(title_cmd, capture_output=True, text=True, timeout=30)
        video_title = title_process.stdout.strip() or "ویدیو"
        
        # مرحله 3: استخراج آهنگ از ویدیو
        audio_extracted = False
        try:
            cmd_audio = [
                "yt-dlp",
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--no-playlist",
                "-o", audio_path,
                "--socket-timeout", "30",
                url
            ]
            
            audio_process = subprocess.run(cmd_audio, capture_output=True, text=True, timeout=300)
            
            if audio_process.returncode == 0 and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                audio_extracted = True
        except:
            pass
        
        # مرحله 4: ساخت لینک جستجوی گوگل
        search_query = f"{video_title} official song audio"
        google_search_url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"
        
        # مرحله 5: ارسال فیلم به کاربر
        with open(video_path, 'rb') as video_file:
            caption = f"🎬 فیلم از {site_name} دانلود شد!\n\n"
            caption += f"📌 عنوان: {video_title[:100]}\n\n"
            
            if audio_extracted:
                caption += f"🎵 آهنگ استخراج شده از فیلم آماده‌ست!\n"
                with open(audio_path, 'rb') as audio_file:
                    await update.message.reply_audio(
                        audio=audio_file,
                        title=f"{video_title[:50]}",
                        performer="استخراج شده از فیلم"
                    )
            else:
                caption += f"🎵 برای پیدا کردن آهنگ این فیلم:\n{google_search_url}"
            
            await update.message.reply_video(
                video=video_file,
                caption=caption,
                supports_streaming=True
            )
        
        # پاک کردن فایل‌های موقت
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏰ دانلود زیاد طول کشید (بیش از ۵ دقیقه). دوباره تلاش کن.")
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {str(e)[:150]}")
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ لطفاً فقط لینک بفرست.\n"
        "من خودم تشخیص می‌دم که لینک از کدوم سایته و فیلم رو دانلود می‌کنم."
    )

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    
    print("🚀 ربات روشن شد...")
    print(f"✅ پشتیبانی از بیش از ۱۸۰۰ سایت")
    app.run_polling()

if __name__ == "__main__":
    main()
