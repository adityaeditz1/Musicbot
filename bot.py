from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import yt_dlp
import os
import re

# BOT TOKEN from environment
TOKEN = os.getenv("BOT_TOKEN")


def is_youtube_link(text: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)", text))


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Unknown"
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


# 🔹 PROFESSIONAL START MESSAGE
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 **Music Downloader Bot**\n\n"
        "Download high-quality audio directly from YouTube.\n\n"
        "**How to use:**\n"
        "• Send a song name → choose from results\n"
        "• Paste a YouTube link → instant download\n\n"
        "Fast • Clean • Simple\n",
        parse_mode="Markdown"
    )


async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()

    # 🔍 Processing message (store it)
    processing_msg = await update.message.reply_text("🔍 Processing...")

    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        # 🔗 DIRECT YOUTUBE LINK
        if is_youtube_link(query):
            info = ydl.extract_info(query, download=True)

            # ❌ Remove processing
            await processing_msg.delete()

            await send_audio(update.message, info, ydl)
            return

        # 🔍 SONG NAME SEARCH
        info = ydl.extract_info(f"ytsearch5:{query}", download=False)

        if not info.get("entries"):
            await processing_msg.delete()
            await update.message.reply_text(
                "❌ No results found.\nPlease try a different song name."
            )
            return

        context.user_data["results"] = info["entries"]

        buttons = []
        for i, entry in enumerate(info["entries"]):
            title = entry.get("title", "Unknown Title")
            buttons.append([
                InlineKeyboardButton(text=title, callback_data=str(i))
            ])

        # ❌ Remove processing before showing results
        await processing_msg.delete()

        # 🎧 Result message (store for deletion later)
        results_msg = await update.message.reply_text(
            "🎧 **Select a song:**",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )

        context.user_data["results_msg_id"] = results_msg.message_id


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    index = int(query.data)
    entry = context.user_data["results"][index]

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "%(title)s.%(ext)s",
        "quiet": True
    }

    # ❌ Delete result list message
    try:
        await query.message.delete()
    except:
        pass

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(entry["webpage_url"], download=True)
        await send_audio(query.message, info, ydl)


async def send_audio(message, info, ydl):
    file_path = ydl.prepare_filename(info)

    title = info.get("title", "Unknown Title")
    artist = info.get("uploader", "Unknown Artist")
    duration = format_duration(info.get("duration"))

    await message.reply_text(
        f"🎵 **{title}**\n"
        f"👤 {artist}\n"
        f"⏱ Duration: {duration}\n\n"
        f"⬇️ Downloading audio...",
        parse_mode="Markdown"
    )

    await message.reply_audio(
        audio=open(file_path, "rb"),
        title=title,
        performer=artist
    )

    os.remove(file_path)


def main():
    if not TOKEN:
        print("❌ BOT_TOKEN not set")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, song))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
