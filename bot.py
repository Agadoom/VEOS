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

# -------- CONFIGURATION RAILWAY --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID"))
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

# -------- LIENS & TITRES --------
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LOGO_PATH = "media/owpc_logo.png"

def get_title(score):
    if score >= 1000: return "👑 Alpha Legend"
    if score >= 500:  return "💎 Unity Guardian"
    if score >= 100:  return "🛠️ Builder"
    return "🐣 Seeker"

# -------- COMMANDES & CLAVIER --------
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("GENESIS 🧬", url=LINK_GENESIS),
         InlineKeyboardButton("UNITY 💎", url=LINK_UNITY),
         InlineKeyboardButton("VEO ⚡", url=LINK_VEO)],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_leaderboard"),
         InlineKeyboardButton("📅 Daily Points", callback_data="daily_claim")],
        [InlineKeyboardButton("🔗 YOUR INVITE LINK", callback_data="get_invite")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if context.args and context.args[0].startswith("ref_"):
        ref_id = int(context.args[0].replace("ref_", ""))
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT * FROM referrals WHERE referred_id = ?", (user.id,))
        if not c.fetchone() and user.id != ref_id:
            update_user(ref_id, "Referrer", score_inc=50)
            c.execute("INSERT INTO referrals VALUES (?)", (user.id,))
            conn.commit()
            try: await context.bot.send_message(ref_id, f"🔥 +50 PTS! {user.first_name} joined via your link!")
            except: pass
        conn.close()

    if update.effective_chat.type == "private":
        score, _ = update_user(user.id, user.first_name)
        await update.message.reply_photo(
            photo=open(LOGO_PATH, "rb"),
            caption=f"🕊️ **OWPC Core v2.7**\n\nRank: {get_title(score)}\nPoints: {score}",
            reply_markup=get_main_keyboard()
        )

# -------- HANDLER DE MESSAGES (OPTIMISÉ GROUPE) --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    chat = update.effective_chat
    user = update.effective_user
    text = update.message.text

    # 1. COMPTAGE POINTS GROUPE
    if chat.id == GROUP_CHAT_ID:
        old_res = update_user(user.id, user.first_name)
        new_res = update_user(user.id, user.first_name, score_inc=1)
        if get_title(old_res[0]) != get_title(new_res[0]):
            await update.message.reply_text(f"🎊 **LEVEL UP {user.first_name}!**\nNouveau Grade : **{get_title(new_res[0])}**")

    # 2. LOGIQUE IA (Privé OU Mention/Reply dans le groupe)
    is_private = chat.type == "private"
    is_mentioned = f"@{context.bot.username}" in text
    is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if is_private or is_mentioned or is_reply:
        try:
            res = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": "Tu es l'IA Alpha OWPC. Pro et visionnaire."},
                          {"role": "user", "content": text}],
                max_tokens=150
            )
            await update.message.reply_text(res.choices[0].message["content"])
        except Exception as e:
            print("OpenAI Error:", e)

# -------- BOUTONS --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if query.data == "view_leaderboard":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
        rows = c.fetchall(); conn.close()
        text = "🏆 **TOP 10 OWPC ACTIVITY**\n\n"
        for i, (n, s) in enumerate(rows, 1):
            text += f"{i}. {n} — {s} pts ({get_title(s)})\n"
        await query.message.reply_text(text)

    elif query.data == "get_invite":
        await query.message.reply_text(f"🔗 **YOUR LINK**\n\n`https://t.me/{BOT_USERNAME}?start=ref_{uid}`", parse_mode="Markdown")

    elif query.data == "daily_claim":
        today = datetime.now().strftime("%Y-%m-%d")
        score, last_d = update_user(uid, query.from_user.first_name)
        if last_d == today:
            await query.message.reply_text("⏳ Already claimed today!")
        else:
            update_user(uid, query.from_user.first_name, score_inc=10, daily=today)
            await query.message.reply_text("✅ +10 pts! Keep building. 💎")

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
