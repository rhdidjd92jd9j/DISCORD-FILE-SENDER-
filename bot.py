import os
import requests
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
DISCORD_WEBHOOK_URL = os.getenv("W_URL")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

# --- FLASK APP ---
server = Flask(__name__)

# --- LOGIC ---
async def send_to_discord(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    audio_file = None
    
    if message.reply_to_message:
        if message.reply_to_message.audio:
            audio_file = message.reply_to_message.audio
        elif message.reply_to_message.document:
            audio_file = message.reply_to_message.document
    
    elif message.audio:
        audio_file = message.audio
    elif message.document:
        audio_file = message.document

    if not audio_file:
        await message.reply_text("No music file found. Please reply to an audio file with /send or use the command in the caption.")
        return

    file_size_mb = audio_file.file_size / (1024 * 1024)
    if file_size_mb > 25:
        await message.reply_text(f"Sorry, file size is {file_size_mb:.2f} MB, which exceeds the Discord 25MB limit.")
        return

    status_msg = await message.reply_text("Downloading...")

    download_path = None
    try:
        file = await context.bot.get_file(audio_file.file_id)
        file_name = audio_file.file_name if hasattr(audio_file, 'file_name') else "music.mp3"
        download_path = f"./{file_name}"
        
        await file.download_to_drive(download_path)
        
        await context.bot.edit_message_text(chat_id=message.chat_id, message_id=status_msg.message_id, text="Uploading to Discord...")

        with open(download_path, "rb") as f:
            payload = {
                "content": f"New Music Sent by: {message.from_user.first_name}"
            }
            files = {
                "file": (file_name, f)
            }
            response = requests.post(DISCORD_WEBHOOK_URL, data=payload, files=files)

        if os.path.exists(download_path):
            os.remove(download_path)

        if response.status_code == 200 or response.status_code == 204:
            await context.bot.edit_message_text(chat_id=message.chat_id, message_id=status_msg.message_id, text="Successfully sent to Discord.")
        else:
            await context.bot.edit_message_text(chat_id=message.chat_id, message_id=status_msg.message_id, text=f"Discord Error: {response.status_code}")

    except Exception as e:
        print(e)
        await message.reply_text("An error occurred. Check console.")
        if download_path and os.path.exists(download_path):
            os.remove(download_path)

# --- SETUP TELEGRAM APP ---
ptb_app = Application.builder().token(BOT_TOKEN).build()
ptb_app.add_handler(CommandHandler("send", send_to_discord))

# --- WEBHOOK ROUTES ---
@server.route('/' + BOT_TOKEN, methods=['POST'])
def webhook_update():
    update_data = request.get_json(force=True)
    
    async def process():
        await ptb_app.initialize()
        update = Update.de_json(update_data, ptb_app.bot)
        await ptb_app.process_update(update)
        await ptb_app.shutdown()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process())
        loop.close()
    except Exception as e:
        print(f"Update error: {e}")
        
    return "ok", 200

@server.route("/")
def set_webhook():
    bot_url = "https://{}/{}".format(os.environ.get("RENDER_EXTERNAL_HOSTNAME"), BOT_TOKEN)
    req = requests.get(API_URL + "setWebhook?url=" + bot_url)
    if req.status_code == 200:
        return "Webhook set!", 200
    else:
        return f"Webhook error: {req.text}", 500

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
