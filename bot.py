import os
import asyncio
import sqlite3
import nest_asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import openai

nest_asyncio.apply()

# -------- CONFIGURATION --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# On utilise .get() pour éviter que le bot plante si la variable est vide
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", 0))
BOT_USERNAME = os.getenv("BOT_USERNAME", "OWPCinfo_bot")
openai.api_key = OPENAI_API_KEY

# -------- BASE DE DONNÉES --------
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER, last_daily TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (referred_id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()

def update_user(user_id, name, score_inc=0, daily=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, name, score, last_daily) VALUES (?, ?, 0, '')", (user_id, name))
    if score_inc:
        c.execute("UPDATE users SET score = score + ?, name = ? WHERE id = ?", (score_inc, name, user_id))
    if daily:
        c.execute("UPDATE users SET last_daily = ?, name = ? WHERE id = ?", (daily, name, user_id))
    c.execute("SELECT score, last_daily FROM users WHERE id = ?", (user_id,))
    res = c.fetchone()
    conn.commit()
    conn.close()
    return res

init_db()

def get_title(score):
    if score >= 1000: return "👑 Alpha Legend"
    if score >= 500:  return "💎 Unity Guardian"
    if score >= 100:  return "🛠️ Builder"
    return "🐣 Seeker"

# -------- COMMANDES --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.effective_chat.type == "private":
        score_res = update_user(user.id, user.first_name)
        score = score_res[0]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_leaderboard")],
            [InlineKeyboardButton("🔗 Invite Link", callback_data="get_invite")]
        ])
        await update.message.reply_text(
            f"🕊️ **OWPC CORE**\n\nGrade: {get_title(score)}\nPoints: {score}",
            reply_markup=keyboard, parse_mode="Markdown"
        )

async def score_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    await update.message.reply_text(f"📊 {user.first_name}, ton score : {res[0]} pts ({get_title(res[0])})")

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
    rows = c.fetchall(); conn.close()
    text = "🏆 **TOP 10 OWPC**\n\n"
    for i, (n, s) in enumerate(rows, 1):
        text += f"{i}. {n} — {s} pts\n"
    await update.message.reply_text(text)

# -------- LOGIQUE DE MESSAGES --------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    chat = update.effective_chat
    user = update.effective_user
    text = update.message.text

    # 1. COMPTAGE DES POINTS (Si dans le groupe officiel)
    if chat.id == GROUP_CHAT_ID:
        old_res = update_user(user.id, user.first_name)
        new_res = update_user(user.id, user.first_name, score_inc=1)
        if get_title(old_res[0]) != get_title(new_res[0]):
            await update.message.reply_text(f"🎊 **LEVEL UP {user.first_name}!** -> {get_title(new_res[0])}")

    # 2. RÉPONSE IA (Privé OU Mention (@bot) OU Réponse (Reply))
    is_private = chat.type == "private"
    is_mentioned = f"@{context.bot.username}" in text
    is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if is_private or is_mentioned or is_reply:
        try:
            res = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": "Tu es l'IA Alpha OWPC."},
                          {"role": "user", "content": text}],
                max_tokens=150
            )
            await update.message.reply_text(res.choices[0].message["content"])
        except: pass

# -------- BOUTONS & MAIN --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "view_leaderboard":
        await leaderboard_command(update, context)
    elif query.data == "get_invite":
        await query.message.reply_text(f"https://t.me/{BOT_USERNAME}?start=ref_{query.from_user.id}")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("score", score_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
