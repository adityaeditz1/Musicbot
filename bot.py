from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import yt_dlp
import os
import re

# TOKEN from environment variable
TOKEN = os.getenv("BOT_TOKEN")


def is_youtube_link(text: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)", text))


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Unknown"
    minutes = seconds // 60
    sec = seconds % 60
    return f"{minutes}:{sec:02d}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Music Downloader Bot\n\n"
        "This bot lets you download high-quality audio from YouTube.\n\n"
        "You can:\n"
        "• Send a song name\n"
        "• Or paste a YouTube link\n\n"
        "The bot will fetch the best available audio."
    )


async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    await update.message.reply_text("🔍 Processing...")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "%(title)s.%(ext)s",
        "quiet": True,
        "noplaylist": True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            # 🔗 If YouTube link
            if is_youtube_link(query):
                info = ydl.extract_info(query, download=True)
                entry = info

            # 🔍 If song name
            else:
                info = ydl.extract_info(f"ytsearch1:{query}", download=True)

                if not info.get("entries"):
                    await update.message.reply_text(
                        "❌ No results found.\n"
                        "Please try a different song name."
                    )
                    return

                entry = info["entries"][0]

            file_path = ydl.prepare_filename(entry)

            title = entry.get("title", "Unknown Title")
            artist = entry.get("uploader", "Unknown Artist")
            duration = format_duration(entry.get("duration"))

        # ℹ️ Show info BEFORE sending audio
        await update.message.reply_text(
            f"🎵 *{title}*\n"
            f"👤 {artist}\n"
            f"⏱ Duration: {duration}\n\n"
            f"⬇️ Downloading audio...",
            parse_mode="Markdown"
        )

        await update.message.reply_audio(
            audio=open(file_path, "rb"),
            title=title,
            performer=artist
        )

        os.remove(file_path)

    except Exception as e:
        await update.message.reply_text("❌ Something went wrong. Please try again later.")
        print(e)


def main():
    if not TOKEN:
        print("❌ BOT_TOKEN not set")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, song))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
