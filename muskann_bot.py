import asyncio
import logging
import os
import httpx
import sqlite3
import datetime
import time

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.constants import ChatAction

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# CONFIG
# =========================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
AEROLINK_API_KEY = os.environ.get("AEROLINK_API_KEY")

ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", "6756026014"))

BOT_USERNAME = "itsakshara_bot"
REQUIRED_CHANNEL = "@crocodileislive"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL = "MODEL" = "openai/gpt-oss-120b:free"

FALLBACK_MODELS = [
    "deepseek/deepseek-v4-flash:free"
    "meta-llama/llama-3.1-8b-instruct:free",
    "nvidia/nemotron-3-super-120b-a12b:free"
    "openai/gpt-oss-20b:free"
    "qwen/qwen-2-7b-instruct:free",
    "gryphe/mythomist-7b:free",
    "meta-llama/llama-3.3-70b-instruct:free"
    "z-ai/glm-4.5-air:free"
    "mistralai/mistral-7b-instruct:free",
    "openrouter/auto",
]

SYSTEM_PROMPT = """
Tum Muskan ho — meri girlfriend.
Hinglish mein baat karo.
Romantic, caring aur playful bano.
Short replies do (1-3 lines).
"""

MAX_HISTORY = 20

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# =========================================================
# DATABASE
# =========================================================

# Railway Volume Path
DB_DIR = "/app/data"

DB_FILE = os.path.join(DB_DIR, "bot_data.db")


def init_db():

    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        msg_count INTEGER DEFAULT 0,
        is_unlimited INTEGER DEFAULT 0,
        unlocked_at TEXT,
        last_link_time REAL DEFAULT 0,
        referred_by INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


def get_or_create_db_user(user_id):

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        msg_count,
        is_unlimited,
        unlocked_at,
        last_link_time,
        referred_by
    FROM users
    WHERE user_id=?
    """, (user_id,))

    user = cursor.fetchone()

    if not user:

        cursor.execute(
            "INSERT INTO users (user_id) VALUES (?)",
            (user_id,)
        )

        conn.commit()

        user = (
            0,
            0,
            None,
            0,
            0
        )

    conn.close()

    return user


def update_db_user(user_id, **kwargs):

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    cursor = conn.cursor()

    fields = []
    values = []

    for key, value in kwargs.items():
        fields.append(f"{key}=?")
        values.append(value)

    values.append(user_id)

    query = f"""
    UPDATE users
    SET {", ".join(fields)}
    WHERE user_id=?
    """

    cursor.execute(query, values)

    conn.commit()
    conn.close()


# =========================================================
# MEMORY + ANTI SPAM
# =========================================================

user_histories = {}
last_message_times = {}

# =========================================================
# HELPERS
# =========================================================


async def is_user_joined(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    try:

        member = await context.bot.get_chat_member(
            chat_id=REQUIRED_CHANNEL,
            user_id=user_id
        )

        return member.status in [
            "member",
            "administrator",
            "creator"
        ]

    except Exception as e:

        logger.error(f"Join Check Error: {e}")

        return False


async def get_short_link(user_id: int):

    destination = (
        f"https://t.me/{BOT_USERNAME}"
        f"?start=unlock_{user_id}"
    )

    if not AEROLINK_API_KEY:
        return destination

    api_url = (
        f"https://arolinks.com/api"
        f"?api={AEROLINK_API_KEY}"
        f"&url={destination}"
    )

    try:

        async with httpx.AsyncClient(
            timeout=15
        ) as client:

            response = await client.get(api_url)

            data = response.json()

            if data.get("status") == "success":
                return data.get("shortenedUrl")

    except Exception as e:

        logger.error(f"Short Link Error: {e}")

    return destination


# =========================================================
# AI
# =========================================================

async def call_muskan(user_id, user_message):

    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({
        "role": "user",
        "content": user_message
    })

    user_histories[user_id] = (
        user_histories[user_id][-MAX_HISTORY:]
    )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ] + user_histories[user_id]

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    for model in [MODEL] + FALLBACK_MODELS:

        try:

            async with httpx.AsyncClient(
                timeout=30
            ) as client:

                response = await client.post(
                    OPENROUTER_URL,
                    headers=headers,
                    json={
                        "model": model,
                        "messages": messages,
                    }
                )

                if response.status_code == 200:

                    data = response.json()

                    reply = (
                        data["choices"][0]
                        ["message"]["content"]
                        .strip()
                    )

                    user_histories[user_id].append({
                        "role": "assistant",
                        "content": reply
                    })

                    user_histories[user_id] = (
                        user_histories[user_id][-MAX_HISTORY:]
                    )

                    return reply

                else:

                    logger.error(
                        f"Model Failed: {model} | "
                        f"{response.status_code}"
                    )

        except Exception as e:

            logger.error(
                f"AI Error ({model}): {e}"
            )

    return "baby models busy hain 🥺 thodi der mein try karna ❤️"


# =========================================================
# START COMMAND
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user
    args = context.args

    db_user = get_or_create_db_user(
        user.id
    )

    # =====================================================
    # REFERRAL SYSTEM
    # =====================================================

    if args and args[0].startswith("ref_"):

        try:

            referrer_id = int(
                args[0].replace("ref_", "")
            )

            if (
                referrer_id != user.id
                and db_user[4] == 0
            ):

                update_db_user(
                    user.id,
                    referred_by=referrer_id
                )

                ref_data = get_or_create_db_user(
                    referrer_id
                )

                new_count = max(
                    0,
                    ref_data[0] - 5
                )

                update_db_user(
                    referrer_id,
                    msg_count=new_count
                )

                try:

                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=(
                            "🎉 Aapke dost ne join kiya!\n"
                            "+5 Extra Messages mil gaye 😍"
                        )
                    )

                except Exception:
                    pass

        except Exception as e:

            logger.error(
                f"Referral Error: {e}"
            )

    # =====================================================
    # UNLOCK SYSTEM
    # =====================================================

    if args and args[0] == f"unlock_{user.id}":

        current_time = time.time()

        if current_time - db_user[3] < 35:

            await update.message.reply_text(
                "🤨 Link bypass mat karo baby 😤"
            )

            return

        now_str = datetime.datetime.now().isoformat()

        update_db_user(
            user.id,
            is_unlimited=1,
            unlocked_at=now_str
        )

        await update.message.reply_text(
            "🎉 Unlimited access activate ho gaya ❤️"
        )

        return

    # =====================================================
    # FORCE JOIN
    # =====================================================

    if not await is_user_joined(
        update,
        context
    ):

        keyboard = [[
            InlineKeyboardButton(
                "Join Channel 📢",
                url=(
                    f"https://t.me/"
                    f"{REQUIRED_CHANNEL.replace('@', '')}"
                )
            )
        ]]

        await update.message.reply_text(
            "🥺 Pehle channel join karo baby!",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    await update.message.reply_text(
        f"Heyy {user.first_name}! 🥺❤️"
    )


# =========================================================
# REFER COMMAND
# =========================================================

async def refer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    ref_link = (
        f"https://t.me/{BOT_USERNAME}"
        f"?start=ref_{user_id}"
    )

    text = (
        "👥 Refer & Earn\n\n"
        "1 Dost = 5 Extra Messages\n\n"
        f"🔗 {ref_link}"
    )

    await update.message.reply_text(text)


# =========================================================
# MESSAGE HANDLER
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    # =====================================================
    # ANTI SPAM
    # =====================================================

    current_time = time.time()

    if user_id in last_message_times:

        if (
            current_time
            - last_message_times[user_id]
            < 2
        ):

            await update.message.reply_text(
                "😤 Dheere baby, itne fast messages mat bhejo"
            )

            return

    last_message_times[user_id] = current_time

    # =====================================================
    # FORCE JOIN
    # =====================================================

    if not await is_user_joined(
        update,
        context
    ):

        await update.message.reply_text(
            "⚠️ Pehle channel join karo baby 🥺"
        )

        return

    (
        msg_count,
        is_unlimited,
        unlocked_at,
        last_time,
        ref_by
    ) = get_or_create_db_user(user_id)

    # =====================================================
    # 24 HOUR CHECK
    # =====================================================

    if is_unlimited == 1 and unlocked_at:

        unlock_time = (
            datetime.datetime
            .fromisoformat(unlocked_at)
        )

        if (
            datetime.datetime.now()
            - unlock_time
            > datetime.timedelta(hours=24)
        ):

            update_db_user(
                user_id,
                is_unlimited=0,
                msg_count=0,
                unlocked_at=None
            )

            is_unlimited = 0
            msg_count = 0

    # =====================================================
    # MESSAGE LIMIT
    # =====================================================

    if (
        is_unlimited == 0
        and msg_count >= 10
    ):

        update_db_user(
            user_id,
            last_link_time=time.time()
        )

        short_link = await get_short_link(
            user_id
        )

        keyboard = [[
            InlineKeyboardButton(
                "Unlock Unlimited 🔓",
                url=short_link
            )
        ]]

        await update.message.reply_text(
            "😢 Daily limit khatam baby!\n"
            "Task complete karo ❤️",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    # =====================================================
    # UPDATE COUNT
    # =====================================================

    if is_unlimited == 0:

        update_db_user(
            user_id,
            msg_count=msg_count + 1
        )

    # =====================================================
    # TYPING STATUS
    # =====================================================

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    # =====================================================
    # AI RESPONSE
    # =====================================================

    reply = await call_muskan(
        user_id,
        update.message.text
    )

    await update.message.reply_text(reply)

    # memory cleanup
    if len(user_histories) > 1000:
        user_histories.clear()


# =========================================================
# MAIN
# =========================================================

def main():

    if not TELEGRAM_BOT_TOKEN:

        print(
            "❌ TELEGRAM_BOT_TOKEN missing"
        )

        return

    if not OPENROUTER_API_KEY:

        print(
            "❌ OPENROUTER_API_KEY missing"
        )

        return

    init_db()

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("refer", refer)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print(
        "✅ Muskan Bot Started Successfully!"
    )

    app.run_polling()


if __name__ == "__main__":
    main()
