import asyncio, logging, os, httpx, sqlite3, datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIG ---
REQUIRED_CHANNEL = "@crocodileislive"
BOT_USERNAME = "itsakshara_bot"
AEROLINK_API_KEY = "3ca145339b07e4a32207dca477e6d069c9c6e898"
DB_PATH = "/app/data/bot_data.db"

logging.basicConfig(level=logging.INFO)

# --- DATABASE ---
def init_db():
    if not os.path.exists("/app/data"): os.makedirs("/app/data")
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, msg_count INTEGER DEFAULT 0, 
                    is_unlimited INTEGER DEFAULT 0, unlocked_at TEXT, last_link_time REAL DEFAULT 0, referred_by INTEGER DEFAULT 0)''')
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

# --- HELPERS ---
async def is_user_joined(update, context):
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=update.effective_user.id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

async def get_short_link(user_id):
    dest = f"https://t.me/{BOT_USERNAME}?start=unlock_{user_id}"
    api = f"https://arolinks.com/api?api={AEROLINK_API_KEY}&url={dest}"
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(api)
            return r.json().get("shortenedUrl", dest)
    except: return dest

# --- HANDLERS ---
async def start(update, context):
    if not await is_user_joined(update, context):
        await update.message.reply_text("🥺 Pehle channel join karo!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}")]]))
        return
    await update.message.reply_text("Heyy! I am Muskan. 🥺❤️")

async def handle_message(update, context):
    if not await is_user_joined(update, context):
        await update.message.reply_text("⚠️ Pehle channel join karo baby! 🥺")
        return
    await update.message.reply_text("Muskan is thinking... 💭")

# --- MAIN ---
def main():
    # Token yahan load hoga, global variable ki zaroorat nahi
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if not bot_token:
        print("❌ ERROR: Railway Variable 'TELEGRAM_BOT_TOKEN' set nahi hai!")
        return

    init_db()
    app = Application.builder().token(bot_token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("refer", lambda u, c: u.message.reply_text(f"🔗 Link: https://t.me/{BOT_USERNAME}?start=ref_{u.effective_user.id}")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Bot is fully running!")
    app.run_polling()

if __name__ == "__main__":
    main()
