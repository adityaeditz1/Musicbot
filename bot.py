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

# 🔒 PASTE YOUR BOT TOKEN BELOW
TOKEN = "7906748728:AAF7QOooOffLeRCGxgFSH52O3Ji0_LMNeaI"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Welcome to Music Downloader Bot\n\n"
        "This bot lets you search and download high-quality audio from YouTube.\n\n"
        "Features:\n"
        "• Search songs by name\n"
        "• Download best available audio quality\n"
        "• Fast and simple usage\n\n"
        "Send the song name."
    )


async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    await update.message.reply_text("🔍 Searching...")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "song.%(ext)s",
        "quiet": True,
        "noplaylist": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=True)

        # 🔐 SAFETY CHECK (NO RESULT)
        if not info or not info.get("entries"):
            await update.message.reply_text(
                "❌ No results found.\nPlease try a different song name."
            )
            return

        entry = info["entries"][0]
        file_path = ydl.prepare_filename(entry)

        title = entry.get("title", "Unknown Title")
        uploader = entry.get("uploader", "Unknown Artist")

    await update.message.reply_audio(
        audio=open(file_path, "rb"),
        title=title,
        performer=uploader
    )

    os.remove(file_path)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, song))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
