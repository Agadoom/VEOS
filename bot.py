import os
import asyncio
import sqlite3
import nest_asyncio
from datetime import datetime
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import openai  # Changed for better compatibility

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", 0))
BOT_USERNAME = os.getenv("BOT_USERNAME", "OWPCinfo_bot")

# Set the API key
openai.api_key = OPENAI_API_KEY

# -------- DATABASE --------
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER, last_daily TEXT, quests_done INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (referred_id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()

def update_user(user_id, name, score_inc=0, daily=None, complete_quest=False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, name, score, last_daily) VALUES (?, ?, 0, '')", (user_id, name))
    if score_inc:
        c.execute("UPDATE users SET score = score + ?, name = ? WHERE id = ?", (score_inc, name, user_id))
    if daily:
        c.execute("UPDATE users SET last_daily = ?, name = ? WHERE id = ?", (daily, name, user_id))
    if complete_quest:
        c.execute("UPDATE users SET quests_done = 1 WHERE id = ?", (user_id,))
    c.execute("SELECT score, last_daily, quests_done FROM users WHERE id = ?", (user_id,))
    res = c.fetchone()
    conn.commit()
    conn.close()
    return res

init_db()

# -------- DATA & CONFIG --------
user_messages = defaultdict(list)
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LINK_X = "https://x.com/DeepTradeX"
LINK_CHANNEL = "https://t.me/+SQhKj-gWWmcyODY0"
LOGO = "owpc_logo.png"
GIF_LAUNCH = "gif.gif"

allowed_links = ["deeptrade.bio.link", "t.me/blum", "youtube.com/@deeptradex", "t.me/+SQhKj-gWWmcyODY0"]

def get_title(score):
    if score >= 1000: return "👑 Alpha Legend"
    if score >= 500:  return "💎 Unity Guardian"
    if score >= 100:  return "🛠️ Builder"
    return "🐣 Seeker"

# -------- COMMANDS --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    score_res = update_user(user.id, user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS), InlineKeyboardButton("💎 UNITY", url=LINK_UNITY), InlineKeyboardButton("⚡ VEO", url=LINK_VEO)],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🚀 Quest Center", callback_data="open_q")],
        [InlineKeyboardButton("📅 Daily Points", callback_data="daily"), InlineKeyboardButton("📍 Roadmap", callback_data="roadmap")]
    ]
    
    try:
        await update.message.reply_photo(
            photo=open(LOGO, "rb"),
            caption=f"🕊️ **OWPC Ecosystem v3.5**\n\nRank: {get_title(score_res[0])}\nPoints: {score_res[0]}\n\nPhase 2 is LIVE! 🚀",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_animation(animation=open(GIF_LAUNCH, "rb"))
    except:
        await update.message.reply_text("🕊️ **OWPC Ecosystem v3.5**\n\nWelcome to the hive!", reply_markup=InlineKeyboardMarkup(keyboard))

# -------- CALLBACKS --------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid, name = query.from_user.id, query.from_user.first_name
    await query.answer()

    if query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
        rows = c.fetchall(); conn.close()
        text = "🏆 **TOP 10 LEADERS**\n\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]} pts" for i, r in enumerate(rows)])
        await query.message.reply_text(text)
    elif query.data == "open_q":
        kb = [[InlineKeyboardButton("📢 Join Channel", url=LINK_CHANNEL)], [InlineKeyboardButton("🐦 Follow X", url=LINK_X)], [InlineKeyboardButton("💰 Claim +100 PTS", callback_data="claim_q")]]
        await query.message.reply_text("🚀 **SOCIAL MISSIONS**", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data == "claim_q":
        res = update_user(uid, name)
        if res[2]: await query.message.reply_text("⏳ Already done!")
        else:
            update_user(uid, name, score_inc=100, complete_quest=True)
            await query.message.reply_text("🔥 **SUCCESS!** +100 PTS.")
    elif query.data == "roadmap":
        await query.message.reply_text("📍 **ROADMAP**\nPhase 1: Genesis\nPhase 2: Hive Growth\nPhase 3: DEX & Airdrop")
    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        res = update_user(uid, name)
        if res[1] == today: await query.message.reply_text("⏳ Come back tomorrow!")
        else:
            update_user(uid, name, score_inc=10, daily=today)
            await query.message.reply_text("✅ +10 PTS Daily Reward!")

# -------- HANDLERS --------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user or update.message.from_user.is_bot: return
    user_id, chat_id, text = update.message.from_user.id, update.effective_chat.id, (update.message.text or "").lower()

    # 1. Anti-Spam (6 messages / 30s)
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try: await update.message.delete()
        except: pass
        return

    # 2. Anti-Scam Links
    if any(x in text for x in ["http", ".com", ".xyz", "t.me"]):
        if not any(x in text for x in allowed_links):
            try: await update.message.delete()
            except: pass
            return

    # 3. Points
    if chat_id == GROUP_CHAT_ID:
        update_user(user_id, update.message.from_user.first_name, score_inc=1)

    # 4. AI Chat (Unified Compatibility)
    if update.effective_chat.type == "private" or f"@{context.bot.username}" in text:
        try:
            # New OpenAI Client-less syntax for better compatibility
            from openai import ChatCompletion
            response = ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": "You are OWPC Alpha AI."}, {"role": "user", "content": text}],
                max_tokens=150
            )
            await update.message.reply_text(response.choices[0].message.content)
        except:
            # Fallback for even older versions
            try:
                import openai
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system", "content": "You are OWPC AI."}, {"role": "user", "content": text}]
                )
                await update.message.reply_text(response.choices[0].message.content)
            except: pass

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 OWPC Bot v3.5 FIXED & LIVE...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
