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

# --- CREDENTIALS & CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8181271632:AAHHTsrB5oUn3YsSGnuc4-f4YElr3xmyllk")
# Nayi Working API Key yahan dalo
# Purani line hata kar ye likho:
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", "6756026014"))

BOT_USERNAME = "itsakshara_bot"
REQUIRED_CHANNEL = "@crocodileislive"
AEROLINK_API_KEY = "3ca145339b07e4a32207dca477e6d069c9c6e898"

# Fast response ke liye Gemini Flash model
MODEL = "deepseek/deepseek-v4-flash:free"

FALLBACK_MODELS = [
    "meta-llama/llama-3.1-8b-instruct:free", # Hinglish ke liye best
    "mistralai/pixtral-12b:free",            # Naya aur smart model
    "qwen/qwen-2-7b-instruct:free",          # Multi-language expert
    "gryphe/mythomist-7b:free",              # Roleplay/Romantic baaton ke liye
    "meta-llama/llama-4-maverick:free",      # Purana fallback
    "openrouter/free"                        # Last option (Auto-select)
    "google/gemini-2.0-flash-exp:free",      # Sabse fast reply
]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tum Muskan ho — meri girlfriend. Hinglish mein baat karo. Romantic, caring aur playful bano. Short replies do (1-3 lines)."""

user_histories = {}
MAX_HISTORY = 20

# --- DATABASE PATH ---
DB_DIR = "/app/data"
DB_FILE = os.path.join(DB_DIR, "bot_data.db")

def init_db():
    # Folder check karo aur banao
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        
    conn = sqlite3.connect(DB_FILE) # Yahan path update kiya
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        msg_count INTEGER DEFAULT 0,
        is_unlimited INTEGER DEFAULT 0,
        unlocked_at TEXT,
        last_link_time REAL DEFAULT 0,
        referred_by INTEGER DEFAULT 0
    )
''')
    conn.commit()
    conn.close()

def get_or_create_db_user(user_id):
    conn = sqlite3.connect(DB_FILE) # Yahan path update kiya
    cursor = conn.cursor()
    # ... baki code same rahega
    conn.close()
    return user

def update_db_user(user_id, **kwargs):
    conn = sqlite3.connect(DB_FILE) # Yahan path update kiya
    # ... baki code same rahega
    conn.commit()
    conn.close()

# --- HELPER FUNCTIONS ---
async def is_user_joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

async def get_short_link(user_id: int) -> str:
    destination = f"https://t.me/{BOT_USERNAME}?start=unlock_{user_id}"
    api_url = f"https://arolinks.com/api?api={AEROLINK_API_KEY}&url={destination}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(api_url)
            data = response.json()
            if data.get("status") == "success": return data.get("shortenedUrl")
    except: pass
    return destination

# --- AI CALL ---
async def call_muskan(user_id, user_message):
    if user_id not in user_histories: user_histories[user_id] = []
    user_histories[user_id].append({"role": "user", "content": user_message})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + user_histories[user_id][-MAX_HISTORY:]
    
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    for model in [MODEL] + FALLBACK_MODELS:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(OPENROUTER_URL, json={"model": model, "messages": messages}, headers=headers)
                if resp.status_code == 200:
                    reply = resp.json()["choices"][0]["message"]["content"].strip()
                    user_histories[user_id].append({"role": "assistant", "content": reply})
                    return reply
        except: continue
    return "baby models busy hain 🥺 thodi der mein try karna ❤️"

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    db_user = get_or_create_db_user(user.id) # msg_count, is_unl, unl_at, last_time, ref_by

    # 1. Referral Logic
    if args and args[0].startswith("ref_"):
        referrer_id = int(args[0].replace("ref_", ""))
        # Check if user is new and not referring themselves
        if referrer_id != user.id and db_user[4] == 0:
            update_db_user(user.id, referred_by=referrer_id)
            ref_data = get_or_create_db_user(referrer_id)
            # Reward: Reduce count by 5 (Extra messages)
            new_count = max(0, ref_data[0] - 5)
            update_db_user(referrer_id, msg_count=new_count)
            try: await context.bot.send_message(chat_id=referrer_id, text="🎉 Aapke dost ne join kiya! Aapko +5 Extra Messages mil gaye hain. 😍")
            except: pass

    # 2. Bypass Check (Unlock Logic)
    if args and args[0] == f"unlock_{user.id}":
        current_time = time.time()
        # db_user[3] is last_link_time
        if current_time - db_user[3] < 35:
            await update.message.reply_text("🤨 Itni jaldi? Link bypass mat karo baby, dhang se task poora karo! 😤")
            return
        
        now_str = datetime.datetime.now().isoformat()
        update_db_user(user.id, is_unlimited=1, unlocked_at=now_str)
        await update.message.reply_text("🎉 Wow! Unlimited Access activate ho gaya! 😍❤️")
        return

    # 3. Force Join
    if not await is_user_joined(update, context):
        keyboard = [[InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}")]]
        await update.message.reply_text("🥺 Baby pehle channel join karo na, tabhi baat karungi!", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    await update.message.reply_text(f"Heyy {user.first_name}! 🥺❤️ Miss kar rahi thi tumhe...")

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    await update.message.reply_text(f"👥 **Refer & Earn**\n\n1 Dost = 5 Extra Messages\n\n🔗 Link: `{ref_link}`", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_user_joined(update, context):
        await update.message.reply_text("⚠️ Pehle channel join karo baby! 🥺")
        return

    msg_count, is_unlimited, unlocked_at, last_time, ref_by = get_or_create_db_user(user_id)

    # 24-Hour Expiry Check
    if is_unlimited == 1 and unlocked_at:
        if datetime.datetime.now() - datetime.datetime.fromisoformat(unlocked_at) > datetime.timedelta(hours=24):
            update_db_user(user_id, is_unlimited=0, msg_count=0, unlocked_at=None)
            is_unlimited = 0; msg_count = 0

    if is_unlimited == 0 and msg_count >= 10:
        # Record time when link is given
        update_db_user(user_id, last_link_time=time.time())
        short_link = await get_short_link(user_id)
        keyboard = [
            [InlineKeyboardButton("Unlock Unlimited 🔓", url=short_link)],
            [InlineKeyboardButton("Refer Friend (+5 Msg) 👥", callback_data="ref_info")]
        ]
        await update.message.reply_text("😢 Limit khatam! Task poora karo ya refer karo unlimited chat ke liye.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if is_unlimited == 0: update_db_user(user_id, msg_count=msg_count + 1)
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    reply = await call_muskan(user_id, update.message.text)
    await update.message.reply_text(reply)

def main():
    # 1. TOKEN YAHAN LOAD KARO (OS.ENVIRON SE)
    # Ismein 'TELEGRAM_BOT_TOKEN' naam ka koi variable nahi hai, seedha string hai
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("❌ ERROR: Railway Variables mein 'TELEGRAM_BOT_TOKEN' key add karo!")
        return

    init_db()
    
    # 2. TOKEN YAHAN PASS KARO
    app = Application.builder().token(token).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Bot Started Successfully!")
    app.run_polling()
if __name__ == "__main__":
    main()
