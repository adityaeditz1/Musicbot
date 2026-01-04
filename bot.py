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

# Railway handles paths automatically, so we removed manual FFMPEG_PATH

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


# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)

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

    # 🔔 ADMIN BROADCAST MESSAGE CAPTURE
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
            "⚠️ **Confirm Broadcast**\n\n"
            "This message will be sent to all active users.",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        return

    query = update.message.text.strip()
    processing_msg = await update.message.reply_text("🔍 Processing...")

    # Options updated for Title, Artist and Thumbnail
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "outtmpl": "%(title)s.%(ext)s",
        "writethumbnail": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            },
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

            if not info or not info.get("entries"):
                await processing_msg.delete()
                await update.message.reply_text(
                    "❌ No results found.\nPlease try a different song name."
                )
                return

            context.user_data["results"] = info["entries"]

            buttons = []
            for i, entry in enumerate(info["entries"]):
                buttons.append([
                    InlineKeyboardButton(entry.get("title", "Unknown")[:40], callback_data=f"song_{i}")
                ])

            await processing_msg.delete()
            await update.message.reply_text(
                "🎧 **Select a song:**",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
    except Exception as e:
        if processing_msg: await processing_msg.delete()
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")


# ================= CALLBACK HANDLER (ALL CALLBACKS HERE) =================

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # 🔐 Admin only protection
    if data.startswith("broadcast") or data == "stats":
        if query.from_user.id != ADMIN_ID:
            return

    # 📊 STATISTICS
    if data == "stats":
        total = active = 0
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE) as f:
                users = f.read().splitlines()
                total = len(users)
            for uid in users:
                try:
                    await context.bot.send_chat_action(int(uid), "typing")
                    active += 1
                    await asyncio.sleep(0.03)
                except:
                    pass
        await query.message.reply_text(
            f"📊 **Statistics**\n\n"
            f"👥 Total Users: {total}\n"
            f"✅ Active Users: {active}",
            parse_mode="Markdown"
        )
        return

    # 📣 BROADCAST START
    if data == "broadcast":
        context.user_data["awaiting_broadcast"] = True
        await query.message.reply_text(
            "✍️ Send the broadcast message.\n"
            "You will be asked to confirm before sending."
        )
        return

    # ✅ BROADCAST CONFIRM
    if data == "broadcast_confirm":
        sent = failed = 0
        text = context.user_data.get("broadcast_text", "")
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE) as f:
                users = f.read().splitlines()
            for uid in users:
                try:
                    await context.bot.send_message(int(uid), text)
                    sent += 1
                    await asyncio.sleep(0.05)
                except Forbidden:
                    failed += 1
                except:
                    failed += 1
        await query.message.reply_text(
            f"✅ **Broadcast Completed**\n\n"
            f"📤 Sent: {sent}\n"
            f"❌ Failed: {failed}",
            parse_mode="Markdown"
        )
        return

    # ❌ BROADCAST CANCEL
    if data == "broadcast_cancel":
        await query.message.reply_text("❌ Broadcast cancelled.")
        return

    # 🎵 SONG SELECTION
    if data.startswith("song_"):
        index = int(data.split("_")[1])
        results = context.user_data.get("results")
        if not results:
            await query.message.reply_text("❌ Session expired. Please search again.")
            return

        entry = results[index]
        status_msg = await query.message.reply_text("⏳ Downloading audio...")

        try:
            await query.message.delete()
        except:
            pass

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "%(title)s.%(ext)s",
            "quiet": True,
            "writethumbnail": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                },
                {"key": "EmbedThumbnail"},
                {"key": "FFmpegMetadata"},
            ]
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(entry["webpage_url"], download=True)
                await status_msg.delete()
                await send_audio(query.message, info, ydl)
        except Exception as e:
            await status_msg.edit_text(f"❌ Download failed: {str(e)}")


# ================= SEND AUDIO =================

async def send_audio(message, info, ydl):
    # This prepares the filename based on title
    base_path = ydl.prepare_filename(info)
    file_path = os.path.splitext(base_path)[0] + ".mp3"
    thumb_path = os.path.splitext(base_path)[0] + ".jpg"
    
    # Fallback paths if above fails due to extension mismatch
    if not os.path.exists(file_path):
        file_path = f"{info['title']}.mp3"
    if not os.path.exists(thumb_path):
        thumb_path = f"{info['title']}.jpg"

    try:
        if os.path.exists(file_path):
            # Send with title, performer and thumbnail
            await message.reply_audio(
                audio=open(file_path, "rb"),
                title=info.get("title"),
                performer=info.get("uploader"),
                duration=int(info.get("duration", 0)),
                thumbnail=open(thumb_path, "rb") if os.path.exists(thumb_path) else None
            )
            
            # Clean up files
            if os.path.exists(file_path): os.remove(file_path)
            if os.path.exists(thumb_path): os.remove(thumb_path)
            
            # Clean up other potential extensions from thumbnails
            for ext in [".webp", ".png", ".webp"]:
                extra_thumb = os.path.splitext(base_path)[0] + ext
                if os.path.exists(extra_thumb): os.remove(extra_thumb)
        else:
            await message.reply_text("❌ Error: Audio file creation failed.")
    except Exception as e:
        await message.reply_text(f"❌ Upload error: {str(e)}")


# ================= ADMIN PANEL =================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    buttons = [
        [
            InlineKeyboardButton("📊 Statistics", callback_data="stats"),
            InlineKeyboardButton("📣 Broadcast", callback_data="broadcast")
        ]
    ]

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

    print("Bot running on Cloud...")
    app.run_polling()


if __name__ == "__main__":
    main()

