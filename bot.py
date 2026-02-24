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
import asyncpg
import html

TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = 1721427995

# Force Subscribe Configuration
FORCE_CHANNEL_USERNAME = "@aditya_labs"
FORCE_CHANNEL_ID = -1003644491983

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None
BOT_ID = 3


# ================= FORCE JOIN CHECK =================

async def check_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(
            chat_id=FORCE_CHANNEL_ID,
            user_id=user_id
        )
        return member.status in ["member", "administrator", "creator"]
    except:
        # ❌ Error aaye to NOT JOINED maanenge
        return False

async def force_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if await check_membership(user.id, context):
        return True

    buttons = [
        [InlineKeyboardButton(
            "🔔 Join Channel",
            url="https://t.me/aditya_labs"
        )],
        [InlineKeyboardButton(
            "✅ I've Joined",
            callback_data="check_subscription"
        )]
    ]

    text = (
        "🔒 <b>Access Restricted</b>\n\n"
        "<b>Please join our official channel to use this bot.</b>"
    )

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )

    return False
# ================= /start (VERIFY ONLY) =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await save_user(user)

    if not await force_verify(update, context):
        return

    msg = """
<b>🎵 Music Downloader Bot</b>

<b>🎧 Download high-quality audio directly from YouTube.</b>

<b>📌 How to use:</b><blockquote>
<b>🎶 Send a song name</b> → choose from results  
<b>🔗 Paste a YouTube link</b> → instant download</blockquote>

⚡ Fast • ✨ Clean • 🚀 Simple

🔥 <b>Official channel: @aditya_labs</b>
"""

    if update.message:
        await update.message.reply_text(msg, parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.message.reply_text(msg, parse_mode="HTML")

async def save_user(user):
    async with db_pool.acquire() as conn:

        # users table
        await conn.execute(
        """
        INSERT INTO users (user_id, username, first_name, blocked)
        VALUES ($1, $2, $3, FALSE)
        ON CONFLICT (user_id)
        DO UPDATE SET username = EXCLUDED.username, first_name = EXCLUDED.first_name, blocked = FALSE, last_active = now()
        """,
            user.id,
            user.username,
            user.first_name
        )

        # user_bot_map table
        await conn.execute(
        """
            INSERT INTO user_bot_map (user_id, bot_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            user.id,
            BOT_ID
        )


# ================= /admin PANEL =================

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


# ================= CALLBACK ROUTER =================

async def admin_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # ================= VERIFY BUTTON =================
    if data == "check_subscription":
        user_joined = await check_membership(user_id, context)

        # ---------- NOT JOINED ----------
        if not user_joined:
            await query.answer("❌ You haven't joined yet!", show_alert=True)

            failed_msg = await query.message.reply_text(
                "❌ <b>Verification Failed!</b>\n\n"
                "Please join the channel and try again.",
                parse_mode="HTML"
            )

            # store ALL failed message ids
            failed_ids = context.user_data.get("failed_verify_msg_ids", [])
            failed_ids.append(failed_msg.message_id)
            context.user_data["failed_verify_msg_ids"] = failed_ids
            return

        # ---------- JOINED ----------
        await query.answer("✅ Verified!")

        # delete verify button message
        try:
            await query.message.delete()
        except:
            pass

        # delete ALL failed verification messages
        failed_ids = context.user_data.get("failed_verify_msg_ids", [])
        for mid in failed_ids:
            try:
                await context.bot.delete_message(
                    chat_id=query.message.chat_id,
                    message_id=mid
                )
            except:
                pass

        context.user_data.pop("failed_verify_msg_ids", None)

        await query.message.reply_text(
            "✅ <b>Verified!</b>\nNow you can use the bot.",
            parse_mode="HTML"
        )
        # 🔥 Automatically run start
        await start(update, context)
        return

    await query.answer()

    # ================= ADMIN ONLY =================
    if (data.startswith("broadcast") or data == "stats") and user_id != ADMIN_ID:
        return

    # ================= STATISTICS =================
    if data == "stats":
        async with db_pool.acquire() as conn:

            total = await conn.fetchval(
                "SELECT COUNT(*) FROM user_bot_map WHERE bot_id = $1",
                BOT_ID
            )

            active = await conn.fetchval(
                """
                SELECT COUNT(*) FROM users u
                JOIN user_bot_map m ON u.user_id = m.user_id
                WHERE m.bot_id = $1 AND u.blocked = FALSE
                """,
                BOT_ID
            )


        await query.message.reply_text(
            f"📊 **Statistics**\n\n"
            f"👥 Total Users: {total}\n"
            f"✅ Active Users: {active}",
            parse_mode="Markdown"
        )
        return

    # ================= BROADCAST START =================
    if data == "broadcast":
        context.user_data["awaiting_broadcast"] = True
        await query.message.reply_text(
            "✍️ Send the broadcast message.\n"
            "You will be asked to confirm before sending."
        )
        return

    # ================= BROADCAST CONFIRM =================
    if data == "broadcast_confirm":
        # delete confirm message
        try:
            await query.message.delete()
        except:
            pass

        sent = failed = 0
        text = context.user_data.get("broadcast_text", "")

        async with db_pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT u.user_id
                FROM users u
                JOIN user_bot_map m ON u.user_id = m.user_id
                WHERE m.bot_id = $1 AND u.blocked = FALSE
                """,
                BOT_ID
            )

            for r in rows:
                uid = r["user_id"]
                try:
                    await context.bot.send_message(uid, text)
                    sent += 1
                    await asyncio.sleep(0.05)

                except Forbidden:
                    failed += 1
                    # user ne bot block kar diya
                    await conn.execute(
                    "UPDATE users SET blocked = TRUE WHERE user_id = $1",
                    uid
                    )

                except:
                    failed += 1


        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                f"✅ **Broadcast Completed**\n\n"
                f"📤 Sent: {sent}\n"
                f"❌ Failed: {failed}"
            ),
            parse_mode="Markdown"
        )

        context.user_data.clear()
        return

    # ================= BROADCAST CANCEL =================
    if data == "broadcast_cancel":
        # delete confirm message
        try:
            await query.message.delete()
        except:
            pass

        context.user_data.clear()
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ Broadcast cancelled."
        )
        return
    
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.user_data.get("awaiting_broadcast"):
        return

    text = update.message.text
    context.user_data["broadcast_text"] = text

    buttons = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")
        ]
    ]

    await update.message.reply_text(
        "⚠️ <b>Confirm Broadcast</b>\n\n"
        f"{html.escape(text)}",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )

    context.user_data["awaiting_broadcast"] = False

# ================= REGISTER (PLUG & PLAY) =================

def register_core_panel(app):
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(admin_callback_router, pattern="^(stats|broadcast|broadcast_confirm|broadcast_cancel|check_subscription)$"))

def is_youtube_link(text: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)", text))


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Unknown"
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


async def song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_verify(update, context):
        return

    query = update.message.text.strip()
    processing_msg = await update.message.reply_text("🔍 Processing...")

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "cookiefile": "cookies.txt",
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
        if processing_msg:
            await processing_msg.delete()
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data != "check_subscription":
        if not await force_verify(update, context):
            return

    await query.answer()

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
            "cookiefile": "cookies.txt",
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
                await send_audio(query.message, info, ydl)
                try:
                    await status_msg.delete()
                except:
                    pass
        except Exception as e:
            await status_msg.edit_text(f"❌ Download failed: {str(e)}")


async def send_audio(message, info, ydl):
    base_path = ydl.prepare_filename(info)
    base_without_ext = os.path.splitext(base_path)[0]

    file_path = base_without_ext + ".mp3"

    try:
        if os.path.exists(file_path):
            with open(file_path, "rb") as audio_file:
                await message.reply_audio(
                    audio=audio_file,
                    title=info.get("title"),
                    performer=info.get("uploader"),
                    duration=int(info.get("duration", 0)),
                    caption="🤖 <b>Powered By @aditya_labs</b>",
                    parse_mode="HTML"
                )
        else:
            await message.reply_text("❌ Error: Audio file creation failed.")

    except Exception as e:
        await message.reply_text(f"❌ Upload error: {str(e)}")

    finally:
        # 🔥 Force delete ALL related files no matter what
        for ext in [".mp3", ".webp", ".jpg", ".png", ".m4a"]:
            file_to_delete = base_without_ext + ext
            if os.path.exists(file_to_delete):
                try:
                    os.remove(file_to_delete)
                except:
                    pass

def main():
    global db_pool

    loop = asyncio.get_event_loop()
    db_pool = loop.run_until_complete(
        asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5
        )
    )

    app = ApplicationBuilder().token(TOKEN).build()

    register_core_panel(app)

    app.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_ID),
    broadcast_message
    ))
    

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, song))

    print("Bot running on Cloud...")
    app.run_polling()


if __name__ == "__main__":
    main()
