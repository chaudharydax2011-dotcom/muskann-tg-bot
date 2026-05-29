import asyncio
import logging
import os
import httpx
import sqlite3
import datetime
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
BOT_USERNAME = "itsakshara_bot"
REQUIRED_CHANNEL = "@crocodileislive"
AEROLINK_API_KEY = "3ca145339b07e4a32207dca477e6d069c9c6e898"
DB_PATH = "/app/data/bot_data.db"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)

# --- DATABASE ---
def init_db():
    if not os.path.exists("/app/data"): os.makedirs("/app/data")
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, msg_count INTEGER DEFAULT 0, 
            is_unlimited INTEGER DEFAULT 0, unlocked_at TEXT, 
            last_link_time REAL DEFAULT 0, referred_by INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

def get_or_create_db_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT msg_count, is_unlimited, unlocked_at, last_link_time, referred_by FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit(); user = (0, 0, None, 0, 0)
    conn.close()
    return user

def update_db_user(user_id, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for k, v in kwargs.items(): cursor.execute(f"UPDATE users SET {k} = ? WHERE user_id = ?", (v, user_id))
    conn.commit(); conn.close()

# --- LINK SHORTENER ---
async def get_short_link(user_id: int) -> str:
    destination = f"https://t.me/{BOT_USERNAME}?start=unlock_{user_id}"
    api_url = f"https://arolinks.com/api?api={AEROLINK_API_KEY}&url={destination}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url)
            data = resp.json()
            if data.get("status") == "success": return data.get("shortenedUrl")
    except: pass
    return destination

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Referral aur Unlock logic yahan aayega (aapka original code)
    await update.message.reply_text("Welcome back! 🥺❤️")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Message Limit aur AI Call logic yahan aayega (aapka original code)
    await update.message.reply_text("Thinking... 🤔")

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{update.effective_user.id}"
    await update.message.reply_text(f"🔗 Your Referral Link: `{link}`", parse_mode="Markdown")

# --- MAIN ---
def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Token missing in Railway Variables!")
        return

    init_db()
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Bot is fully running with all systems!")
    app.run_polling()

if __name__ == "__main__":
    main()
