import os
import re
import subprocess
import urllib.parse
import requests
import instaloader
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============== تنظیمات از Environment Variables ==============
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
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

# ============== توابع دانلود برای سایت‌های مختلف ==============

async def download_with_ytdlp(url, video_path, audio_path):
    """روش ۱: دانلود با yt-dlp (برای اکثر سایت‌ها)"""
    audio_extracted = False
    
    # دانلود ویدیو
    cmd_video = [
        "yt-dlp",
        "-f", "best[ext=mp4]/best",
        "--no-playlist",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--socket-timeout", "60",
        "--retries", "10",
        "--fragment-retries", "10",
        "-o", video_path,
        url
    ]
    
    process = subprocess.run(cmd_video, capture_output=True, text=True, timeout=300)
    
    if process.returncode != 0:
        return False, None, process.stderr[:200]
    
    if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
        return False, None, "فایل خالی است"
    
    # دریافت عنوان
    title_cmd = ["yt-dlp", "--get-title", url]
    title_process = subprocess.run(title_cmd, capture_output=True, text=True, timeout=30)
    video_title = title_process.stdout.strip() or "ویدیو"
    
    # استخراج آهنگ
    try:
        cmd_audio = [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--no-playlist",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "--socket-timeout", "60",
            "-o", audio_path,
            url
        ]
        
        audio_process = subprocess.run(cmd_audio, capture_output=True, text=True, timeout=300)
        
        if audio_process.returncode == 0 and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            audio_extracted = True
    except:
        pass
    
    return True, video_title, audio_extracted

async def download_with_instaloader(url, video_path):
    """روش ۲: دانلود اینستاگرام با instaloader"""
    try:
        loader = instaloader.Instaloader()
        
        # استخراج کد پست
        shortcode_match = re.search(r'/p/([^/?]+)', url)
        if not shortcode_match:
            shortcode_match = re.search(r'/reel/([^/?]+)', url)
        if not shortcode_match:
            shortcode_match = re.search(r'/tv/([^/?]+)', url)
        
        if not shortcode_match:
            return False, "کد پست پیدا نشد"
        
        shortcode = shortcode_match.group(1)
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        
        # دانلود ویدیو
        temp_dir = os.path.join(DOWNLOAD_FOLDER, f"temp_{shortcode}")
        loader.download_post(post, target=temp_dir)
        
        # پیدا کردن فایل ویدیو
        for file in os.listdir(temp_dir):
            if file.endswith(('.mp4', '.mov')):
                src_path = os.path.join(temp_dir, file)
                os.rename(src_path, video_path)
                # پاک کردن فایل‌های اضافی
                import shutil
                shutil.rmtree(temp_dir)
                return True, "اینستاگرام"
        
        return False, "ویدیو پیدا نشد"
    except Exception as e:
        return False, str(e)

async def download_with_instagram_api(url, video_path):
    """روش ۳: دانلود اینستاگرام با API جایگزین"""
    try:
        # استفاده از API رایگان (مثال)
        api_url = "https://api.instagram.com/oembed"
        params = {"url": url}
        
        response = requests.get(api_url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            # این API فقط اطلاعات می‌ده، برای دانلود باید از روش دیگه استفاده کرد
            return False, "API اطلاعات دارد اما دانلود مستقیم ممکن نیست"
        return False, "API پاسخ نداد"
    except Exception as e:
        return False, str(e)

def detect_site(url):
    """تشخیص خودکار سایت از روی لینک"""
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube", "yt-dlp"
    elif "instagram.com" in url:
        return "instagram", "instaloader"
    elif "tiktok.com" in url:
        return "tiktok", "yt-dlp"
    elif "twitter.com" in url or "x.com" in url:
        return "twitter", "yt-dlp"
    elif "facebook.com" in url or "fb.com" in url:
        return "facebook", "yt-dlp"
    elif "twitch.tv" in url:
        return "twitch", "yt-dlp"
    elif "vimeo.com" in url:
        return "vimeo", "yt-dlp"
    elif "soundcloud.com" in url:
        return "soundcloud", "yt-dlp"
    elif "reddit.com" in url:
        return "reddit", "yt-dlp"
    elif "dailymotion.com" in url:
        return "dailymotion", "yt-dlp"
    else:
        return "unknown", "yt-dlp"

# ============== توابع اصلی ربات ==============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🎬 ربات دانلودر پیشرفته!\n\n"
        f"هر لینکی بفرستی تشخیص می‌دم و با بهترین روش دانلود می‌کنم.\n\n"
        f"✅ سایت‌های پشتیبانی‌شده:\n{SUPPORTED_SITES}\n\n"
        f"🔹 برای اینستاگرام از روش اختصاصی استفاده می‌شه\n"
        f"🔹 برای بقیه سایت‌ها از روش پیشرفته استفاده می‌شه\n\n"
        f"فقط کافیه لینک رو بفرستی، بقیه اش با من 😊"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎯 راهنما:\n\n"
        "1️⃣ لینک ویدیو از هر سایتی رو بفرست\n"
        "2️⃣ ربات خودکار تشخیص میده چه سایتی هست\n"
        "3️⃣ فیلم رو با بهترین روش دانلود می‌کنه\n"
        "4️⃣ اگه فیلم آهنگ داشته باشه، آهنگ رو هم جداگانه می‌فرسته\n"
        "5️⃣ اگه نتونه آهنگ رو استخراج کنه، لینک جستجوی گوگل رو میده\n\n"
        "✅ پشتیبانی از بیش از ۱۸۰۰ سایت مختلف\n"
        "✅ روش اختصاصی برای اینستاگرام"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    
    # بررسی لینک بودن
    if not re.match(r'https?://', url):
        await update.message.reply_text("❌ لطفاً یه لینک معتبر بفرست (با http یا https شروع بشه).")
        return
    
    # تشخیص سایت
    site_name, method = detect_site(url)
    
    site_names = {
        "youtube": "YouTube",
        "instagram": "Instagram",
        "tiktok": "TikTok",
        "twitter": "Twitter/X",
        "facebook": "Facebook",
        "twitch": "Twitch",
        "vimeo": "Vimeo",
        "soundcloud": "SoundCloud",
        "reddit": "Reddit",
        "dailymotion": "Dailymotion",
        "unknown": "سایت ناشناخته"
    }
    
    display_name = site_names.get(site_name, site_name)
    
    await update.message.reply_text(
        f"✅ لینک تشخیص داده شد: {display_name}\n"
        f"📡 روش دانلود: {method}\n"
        f"⏳ در حال پردازش... ممکنه چند دقیقه طول بکشه."
    )
    
    video_path = os.path.join(DOWNLOAD_FOLDER, f"{user_id}_video.mp4")
    audio_path = os.path.join(DOWNLOAD_FOLDER, f"{user_id}_audio.mp3")
    
    try:
        success = False
        video_title = "ویدیو"
        audio_extracted = False
        
        # انتخاب روش دانلود
        if method == "instaloader":
            success, result = await download_with_instaloader(url, video_path)
            if success:
                video_title = "اینستاگرام"
        else:
            success, video_title, audio_extracted = await download_with_ytdlp(url, video_path, audio_path)
        
        if not success:
            # اگر روش اول شکست خورد، روش جایگزین رو امتحان کن
            if site_name == "instagram":
                await update.message.reply_text("🔄 روش اول شکست خورد، روش جایگزین رو امتحان می‌کنم...")
                success, result = await download_with_instagram_api(url, video_path)
                if not success:
                    await update.message.reply_text(
                        f"❌ دانلود اینستاگرام ناموفق.\n"
                        f"دلیل: {result}\n\n"
                        f"💡 می‌تونی از سایت‌های زیر استفاده کنی:\n"
                        f"https://savefrom.net\n"
                        f"https://snapinsta.app"
                    )
                    return
            else:
                await update.message.reply_text(f"❌ دانلود فیلم ناموفق: {result if 'result' in locals() else 'خطای ناشناخته'}")
                return
        
        if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
            await update.message.reply_text("❌ فایل دانلود نشد یا خالی هست.")
            return
        
        # ساخت لینک جستجوی گوگل
        search_query = f"{video_title} official song audio"
        google_search_url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"
        
        # ارسال فیلم به کاربر
        with open(video_path, 'rb') as video_file:
            caption = f"🎬 فیلم از {display_name} دانلود شد!\n\n"
            caption += f"📌 عنوان: {video_title[:100]}\n"
            caption += f"📡 روش: {method}\n\n"
            
            if method != "instaloader" and audio_extracted:
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
    print(f"✅ روش اختصاصی برای اینستاگرام")
    app.run_polling()

if __name__ == "__main__":
    main()
