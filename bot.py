

import os
import logging
import httpx

from io import BytesIO
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")
JAMENDO_ID = os.getenv("JAMENDO_CLIENT_ID")

logging.basicConfig(level=logging.INFO)

API = "https://api.jamendo.com/v3.0/tracks/"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Welcome to Music Search Bot!\n\n"
        "Song ka naam bhejo aur music search karo.\n\n"
        "Example: Alan Walker\n\n"
        "👇 Start searching!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎧 Music Bot Help\n\n"
        "1. Song ya artist ka naam bhejo.\n"
        "2. Search results dekho.\n"
        "3. Download button press karo.\n"
        "4. Sirf downloadable tracks milenge."
    )


async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.message.text.strip()

    if len(query) < 2:
        await update.message.reply_text("Song ka naam thora bara likho.")
        return

    msg = await update.message.reply_text("🔎 Searching songs...")

    try:
        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.get(
                API,
                params={
                    "client_id": JAMENDO_ID,
                    "format": "json",
                    "namesearch": query,
                    "limit": 5,
                    "audioformat": "mp32"
                }
            )

            response.raise_for_status()
            data = response.json()

        tracks = data.get("results", [])

        if not tracks:
            await msg.edit_text("❌ Koi song nahi mila.")
            return

        keyboard = []

        for track in tracks:

            track_id = track["id"]
            name = track["name"][:35]
            artist = track["artist_name"][:25]

            allowed = track.get("audiodownload_allowed", False)

            if allowed:
                keyboard.append([
                    InlineKeyboardButton(
                        f"⬇️ {name} - {artist}",
                        callback_data=f"dl:{track_id}"
                    )
                ])

        if not keyboard:
            await msg.edit_text(
                "Songs mile hain, lekin unmein downloadable tracks nahi hain."
            )
            return

        await msg.edit_text(
            f"🎵 Search Results: {query}\n\n"
            "Apna song download karne ke liye button dabao.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception:
        logging.exception("Search error")
        await msg.edit_text("⚠️ Search error. Dobara try karo.")


async def download_song(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    track_id = query.data.split(":")[1]

    await query.message.reply_text("⬇️ Download preparing...")

    try:
        async with httpx.AsyncClient(
            timeout=60,
            follow_redirects=True
        ) as client:

            check = await client.get(
                API,
                params={
                    "client_id": JAMENDO_ID,
                    "format": "json",
                    "id": track_id,
                    "limit": 1
                }
            )

            check.raise_for_status()
            results = check.json().get("results", [])

            if not results or not results[0].get(
                "audiodownload_allowed", False
            ):
                await query.message.reply_text(
                    "❌ Is track ka download allowed nahi hai."
                )
                return

            track = results[0]

            file_url = (
                "https://api.jamendo.com/v3.0/tracks/file/"
            )

            audio_response = await client.get(
                file_url,
                params={
                    "client_id": JAMENDO_ID,
                    "id": track_id,
                    "action": "download",
                    "audioformat": "mp32"
                }
            )

            audio_response.raise_for_status()

            if len(audio_response.content) > 45 * 1024 * 1024:
                await query.message.reply_text(
                    "File Telegram ki upload limit ke liye bohat bari hai."
                )
                return

            audio = BytesIO(audio_response.content)
            audio.seek(0)

        await query.message.reply_audio(
            audio=InputFile(
                audio,
                filename=f"{track['name']}.mp3"
            ),
            title=track["name"],
            performer=track["artist_name"],
            caption="🎵 Music from Jamendo"
        )

    except Exception:
        logging.exception("Download error")
        await query.message.reply_text(
            "❌ Download nahi ho saka. Dobara try karo."
        )


def main():

    if not TOKEN or not JAMENDO_ID:
        raise RuntimeError("BOT_TOKEN or JAMENDO_CLIENT_ID missing!")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(
        CallbackQueryHandler(download_song, pattern=r"^dl:\d+$")
    )

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, search_song)
    )

    print("🎵 Music Bot Started!")

    app.run_polling()


if __name__ == "__main__":
    main()
