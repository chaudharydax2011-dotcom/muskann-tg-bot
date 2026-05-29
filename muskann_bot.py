import asyncio
import logging
import os
import httpx
import sqlite3
import datetime
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", "6756026014"))

BOT_USERNAME = "itsakshara_bot"
REQUIRED_CHANNEL = "@crocodileislive"
AEROLINK_API_KEY = "3ca145339b07e4a32207dca477e6d069c9c6e898"
MODEL = "deepseek/deepseek-v4-flash:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- DATABASE ---
DB_DIR = "/app/data"
DB_PATH = os.path.join(DB_DIR, "bot_data.db")
if not os.path.exists(DB_DIR): os.makedirs(DB_DIR)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
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
        conn.commit()
        user = (0, 0, None, 0, 0)
    conn.close()
    return user

def update_db_user(user_id, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for key, value in kwargs.items():
        cursor.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))
    conn.commit(); conn.close()

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # (Referral & Unlock Logic same as yours)
    await update.message.reply_text(f"Heyy {user.first_name}! 🥺❤️ Miss kar rahi thi tumhe...")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # (Your existing message logic)
    reply = await call_muskan(update.effective_user.id, update.message.text)
    await update.message.reply_text(reply)

# --- MAIN ---
def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ CRITICAL: TELEGRAM_BOT_TOKEN missing!")
        return

    init_db()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("refer", lambda u, c: u.message.reply_text("🔗 Use /refer for link")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Bot Started Successfully!")
    app.run_polling()

if __name__ == '__main__':
    main()
