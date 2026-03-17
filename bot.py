import os
import asyncio
import sqlite3
import nest_asyncio
from datetime import datetime
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import openai

nest_asyncio.apply()

# -------- CONFIGURATION --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", 0))
BOT_USERNAME = "OWPCinfobot" 
ADMIN_ID = 1414016840 

openai.api_key = OPENAI_API_KEY

# -------- DATABASE --------
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER, last_daily TEXT, quests_done INTEGER DEFAULT 0, referred_by INTEGER)''')
    conn.commit()
    conn.close()

def update_user(user_id, name, score_inc=0, daily=None, complete_quest=False, referred_by=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, name, score, last_daily, referred_by) VALUES (?, ?, 0, '', ?)", (user_id, name, referred_by))
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

# -------- TOOLS --------
def get_rank_info(score):
    if score >= 1000: return "👑 Alpha Legend", "MAX", "Infinity power unlocked."
    if score >= 500:  return "💎 Unity Guardian", 1000, "Progress to Legend"
    if score >= 100:  return "🛠️ Builder", 500, "Progress to Guardian"
    return "🐣 Seeker", 100, "Progress to Builder"

def generate_progress_bar(score, next_level_score):
    if next_level_score == "MAX": return "██████████ 100%"
    percent = min(100, int((score / next_level_score) * 100))
    filled = int(percent / 10)
    return f"{'█' * filled}{'░' * (10 - filled)} {percent}%"

# -------- HANDLERS --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # ... (Referral logic kept from v4.0) ...
    score_res = update_user(user.id, user.first_name)
    
    kb = [
        [InlineKeyboardButton("🧬 GENESIS", url="..."), InlineKeyboardButton("💎 UNITY", url="..."), InlineKeyboardButton("⚡ VEO", url="...")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🆔 My Passport", callback_data="my_card")],
        [InlineKeyboardButton("🚀 Quest Center", callback_data="open_q"), InlineKeyboardButton("📅 Daily", callback_data="daily")],
        [InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ]
    caption = f"🕊️ **OWPC Core v4.1**\n\nWelcome to the hive, **{user.first_name}**.\nShape the future of Web3 with us. 🚀"
    try: await update.message.reply_photo(photo=open("media/owpc_logo.png", "rb"), caption=caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    except: await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid, name = query.from_user.id, query.from_user.first_name
    await query.answer()

    if query.data == "my_card":
        score = update_user(uid, name)[0]
        rank, next_val, msg = get_rank_info(score)
        bar = generate_progress_bar(score, next_val)
        
        card = (
            f"💳 **OWPC DIGITAL PASSPORT**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Holder:** {name}\n"
            f"🆔 **UID:** `{uid}`\n"
            f"🏅 **Rank:** {rank}\n"
            f"⭐ **Points:** {score} pts\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📈 **{msg}:**\n"
            f"`{bar}`\n\n"
            f"Build the hive. Share your status! 🐝"
        )
        await query.message.reply_text(card, parse_mode="Markdown")

    elif query.data == "view_lb":
        # ... (Leaderboard logic) ...
        pass
    # ... (Other callbacks: quests, daily, invite) ...

# -------- MESSAGE HANDLER (IA & AUTO-RESPONDER) --------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user or update.message.from_user.is_bot: return
    chat_id, text = update.effective_chat.id, (update.message.text or "").lower()

    if chat_id == GROUP_CHAT_ID:
        update_user(update.message.from_user.id, update.message.from_user.first_name, score_inc=1)
        # Smart Responder
        if "card" in text or "passport" in text or "status" in text:
            await update.message.reply_text("🆔 Pour voir ton Passeport Digital et tes points, va parler au bot en privé : @OWPCinfobot")

    if update.effective_chat.type == "private":
        # IA Response...
        pass

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
