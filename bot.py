from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.error import Forbidden
import yt_dlp
import os
import re
import asyncio

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1721427995
USERS_FILE = "users.txt"

# 🔒 CHANNEL CONFIG
CHANNEL_USERNAME = "@aditya_labs"
CHANNEL_ID = -1003644491983

def is_youtube_link(text: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)", text))

def format_duration(seconds: int) -> str:
    if not seconds:
        return "Unknown"
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"

def save_user(user_id: int):
    if not os.path.exists(USERS_FILE):
        open(USERS_FILE, "w").close()
    with open(USERS_FILE, "r+") as f:
        users = f.read().splitlines()
        if str(user_id) not in users:
            f.write(str(user_id) + "\n")

# ================= CHANNEL CHECK =================

async def is_user_joined(context, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False

async def send_join_message(update: Update):
    buttons = [
        [InlineKeyboardButton("🔔 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("✅ I've Joined", callback_data="verify_join")]
    ]
    await update.message.reply_text(
        "🔒 **Access Restricted**\n\n"
        "Please join our official channel to use this bot.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)

    if not await is_user_joined(context, update.effective_user.id):
        await send_join_message(update)
        return

    await update.message.reply_text(
        "🎵 **Music Downloader Bot**\n\n"
        "Download high-quality audio directly from YouTube.\n\n"
        "**How to use:**\n"
        "• Send a song name → choose from results\n"
        "• Paste a YouTube link → instant download\n\n"
        "Fast • Clean • Simple",
        parse_mode="Markdown"
    )

# ================= SONG HANDLER =================

async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_user_joined(context, update.effective_user.id):
        await send_join_message(update)
        return

    # 🔔 ADMIN BROADCAST CAPTURE
    if (
        update.effective_user.id == ADMIN_ID
        and context.user_data.get("awaiting_broadcast")
    ):
        context.user_data["broadcast_text"] = update.message.text
        context.user_data["awaiting_broadcast"] = False

        buttons = [[
            InlineKeyboardButton("✅ Confirm", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")
        ]]

        await update.message.reply_text(
            "⚠️ **Confirm Broadcast**",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        return

    query = update.message.text.strip()
    processing_msg = await update.message.reply_text("🔍 Processing...")

    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "outtmpl": "%(title)s.%(ext)s",
        "writethumbnail": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
            {"key": "EmbedThumbnail"},
            {"key": "FFmpegMetadata"},
        ]
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if is_youtube_link(query):
                info = ydl.extract_info(query, download=True)
                await processing_msg.delete()
                await send_audio(update.message, info, ydl)
                return

            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            if not info.get("entries"):
                await processing_msg.delete()
                await update.message.reply_text("❌ No results found.")
                return

            context.user_data["results"] = info["entries"]

            buttons = [
                [InlineKeyboardButton(e.get("title", "Unknown")[:40], callback_data=f"song_{i}")]
                for i, e in enumerate(info["entries"])
            ]

            await processing_msg.delete()
            await update.message.reply_text(
                "🎧 **Select a song:**",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
    except Exception as e:
        await processing_msg.delete()
        await update.message.reply_text(f"❌ Error: {e}")

# ================= CALLBACK HANDLER =================

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "verify_join":
        if await is_user_joined(context, query.from_user.id):
            await query.message.edit_text("✅ **Verified!** You can now use the bot.")
        else:
            await query.answer("❌ Please join the channel first.", show_alert=True)
        return

    if data.startswith("song_"):
        index = int(data.split("_")[1])
        entry = context.user_data.get("results", [])[index]

        await query.message.delete()

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "%(title)s.%(ext)s",
            "quiet": True,
            "writethumbnail": True,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
                {"key": "EmbedThumbnail"},
                {"key": "FFmpegMetadata"},
            ]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(entry["webpage_url"], download=True)
            await send_audio(query.message, info, ydl)

# ================= SEND AUDIO =================

async def send_audio(message, info, ydl):
    base = ydl.prepare_filename(info)
    mp3 = os.path.splitext(base)[0] + ".mp3"

    await message.reply_audio(
        audio=open(mp3, "rb"),
        title=info.get("title"),
        performer=info.get("uploader"),
        duration=int(info.get("duration", 0))
    )

    os.remove(mp3)

# ================= ADMIN PANEL =================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    buttons = [[
        InlineKeyboardButton("📊 Statistics", callback_data="stats"),
        InlineKeyboardButton("📣 Broadcast", callback_data="broadcast")
    ]]

    await update.message.reply_text(
        "🛠️ **Admin Panel**",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, song))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
