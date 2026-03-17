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

# -------- LIENS OFFICIELS --------
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LOGO_PATH = "media/owpc_logo.png"

def get_title(score):
    if score >= 1000: return "👑 Alpha Legend"
    if score >= 500:  return "💎 Unity Guardian"
    if score >= 100:  return "🛠️ Builder"
    return "🐣 Seeker"

# -------- COMMANDES DU MENU --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    score_res = update_user(user.id, user.first_name)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS),
         InlineKeyboardButton("💎 UNITY", url=LINK_UNITY),
         InlineKeyboardButton("⚡ VEO", url=LINK_VEO)],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_leaderboard"),
         InlineKeyboardButton("📅 Daily Points", callback_data="daily_claim")],
        [InlineKeyboardButton("🔗 YOUR INVITE LINK", callback_data="get_invite")]
    ])
    
    caption = (f"🕊️ **OWPC Core v3.0**\n\n"
               f"Rank: {get_title(score_res[0])}\n"
               f"Points: {score_res[0]}\n\n"
               f"Build the hive. 🐝")
               
    if update.effective_chat.type == "private":
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=caption, reply_markup=keyboard, parse_mode="Markdown")

async def veos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ("⚡ **À PROPOS DE VEO**\n\n"
            "VEO est notre moteur d'innovation technologique. "
            "Il propulse l'écosystème OWPC vers de nouveaux sommets Web3.")
    await update.message.reply_text(text, parse_mode="Markdown")

async def links_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ("🌐 **OFFICIAL LINKS**\n\n"
            "🔹 [Website](https://deeptrade.bio.link)\n"
            "🔹 [Twitter](https://x.com/DeepTradeX)\n"
            "🔹 [YouTube](https://youtube.com/@deeptradex)")
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

async def invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    await update.message.reply_text(f"🔗 **INVITE FRIENDS & EARN 50 PTS**\n\n`{link}`", parse_mode="Markdown")

async def score_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    await update.message.reply_text(f"📊 {user.first_name}, Score: {res[0]} pts | {get_title(res[0])}")

# -------- LOGIQUE MESSAGES & IA --------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    chat, user, text = update.effective_chat, update.effective_user, update.message.text

    if chat.id == GROUP_CHAT_ID:
        old_s = update_user(user.id, user.first_name)[0]
        new_s = update_user(user.id, user.first_name, score_inc=1)[0]
        if get_title(old_s) != get_title(new_s):
            await update.message.reply_text(f"🎊 **LEVEL UP {user.first_name}!** Grade: {get_title(new_s)}")

    is_private = chat.type == "private"
    is_mentioned = f"@{context.bot.username}" in text
    is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if is_private or is_mentioned or is_reply:
        try:
            res = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": "IA Alpha OWPC."}, {"role": "user", "content": text}],
                max_tokens=150
            )
            await update.message.reply_text(res.choices[0].message["content"])
        except: pass

# -------- CALLBACKS --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid, name = query.from_user.id, query.from_user.first_name
    await query.answer()

    if query.data == "view_leaderboard":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
        rows = c.fetchall(); conn.close()
        txt = "🏆 **LEADERBOARD**\n\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]} pts" for i, r in enumerate(rows)])
        await query.message.reply_text(txt)
    elif query.data == "daily_claim":
        today = datetime.now().strftime("%Y-%m-%d")
        _, last_d = update_user(uid, name)
        if last_d == today: await query.message.reply_text("⏳ Déjà fait !")
        else:
            update_user(uid, name, score_inc=10, daily=today)
            await query.message.reply_text("✅ +10 pts !")
    elif query.data == "get_invite":
        await query.message.reply_text(f"`https://t.me/{BOT_USERNAME}?start=ref_{uid}`", parse_mode="Markdown")

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veos", veos_command))
    app.add_handler(CommandHandler("links", links_command))
    app.add_handler(CommandHandler("invite", invite_command))
    app.add_handler(CommandHandler("score", score_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
