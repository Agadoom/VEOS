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
BOT_USERNAME = os.getenv("BOT_USERNAME", "OWPCinfo_bot")
ADMIN_ID = 1414016840  # ⚠️ REMPLACE PAR TON PROPRE ID TELEGRAM (trouve-le via @userinfobot)

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

# -------- INFOS ECOSYSTÈME --------
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

# -------- COMMANDES --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    # Gestion du parrainage (si start avec ref_XXXX)
    if args and args[0].startswith("ref_"):
        referrer_id = int(args[0].replace("ref_", ""))
        if referrer_id != user.id:
            # On vérifie si l'utilisateur est nouveau
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("SELECT id FROM users WHERE id = ?", (user.id,))
            if not c.fetchone():
                update_user(referrer_id, "Referrer", score_inc=50) # Bonus parrain
                update_user(user.id, user.first_name, referred_by=referrer_id) # Enregistre le nouveau
                await context.bot.send_message(chat_id=referrer_id, text=f"🎉 **New Referral!** {user.first_name} joined. You earned +50 PTS!")

    score_res = update_user(user.id, user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS), InlineKeyboardButton("💎 UNITY", url=LINK_UNITY), InlineKeyboardButton("⚡ VEO", url=LINK_VEO)],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🚀 Quest Center", callback_data="open_q")],
        [InlineKeyboardButton("📅 Daily Points", callback_data="daily"), InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ]
    
    caption = f"🕊️ **OWPC Core v3.6**\n\nRank: {get_title(score_res[0])}\nPoints: {score_res[0]}\n\nGrow the hive. Build the future. 🚀"
    
    try:
        await update.message.reply_photo(photo=open(LOGO, "rb"), caption=caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        await update.message.reply_animation(animation=open(GIF_LAUNCH, "rb"))
    except:
        await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        update_user(target_id, "User", score_inc=amount)
        await update.message.reply_text(f"✅ {amount} points ajoutés à l'ID {target_id}")
    except:
        await update.message.reply_text("Usage: `/admin_bonus ID_TELEGRAM MONTANT`", parse_mode="Markdown")

# -------- CALLBACKS --------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid, name = query.from_user.id, query.from_user.first_name
    await query.answer()

    if query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
        rows = c.fetchall(); conn.close()
        text = "🏆 **GLOBAL LEADERBOARD**\n\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]} pts" for i, r in enumerate(rows)])
        await query.message.reply_text(text)
    
    elif query.data == "get_invite":
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        await query.message.reply_text(f"🔗 **YOUR PERSONAL INVITE LINK**\n\n`{link}`\n\nShare this link! You get **+50 PTS** for every friend who joins. 🚀", parse_mode="Markdown")

    elif query.data == "open_q":
        kb = [[InlineKeyboardButton("📢 Join Channel", url=LINK_CHANNEL)], [InlineKeyboardButton("🐦 Follow X", url=LINK_X)], [InlineKeyboardButton("💰 Claim +100 PTS", callback_data="claim_q")]]
        await query.message.reply_text("🚀 **SOCIAL MISSIONS**", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data == "claim_q":
        res = update_user(uid, name)
        if res[2]: await query.message.reply_text("⏳ Already done!")
        else:
            update_user(uid, name, score_inc=100, complete_quest=True)
            await query.message.reply_text("🔥 **SUCCESS!** +100 PTS.")

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        res = update_user(uid, name)
        if res[1] == today: await query.message.reply_text("⏳ Come back tomorrow!")
        else:
            update_user(uid, name, score_inc=10, daily=today)
            await query.message.reply_text("✅ +10 PTS Daily Reward!")

# -------- HANDLERS --------

user_messages = defaultdict(list)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user or update.message.from_user.is_bot: return
    user_id, chat_id, text = update.message.from_user.id, update.effective_chat.id, (update.message.text or "").lower()

    # Anti-Spam
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try: await update.message.delete()
        except: pass
        return

    # Anti-Scam Links
    if any(x in text for x in ["http", ".com", ".xyz", "t.me"]):
        if not any(x in text for x in allowed_links):
            try: await update.message.delete()
            except: pass
            return

    # Points Groupe
    if chat_id == GROUP_CHAT_ID:
        update_user(user_id, update.message.from_user.first_name, score_inc=1)

    # IA Chat
    if update.effective_chat.type == "private" or f"@{context.bot.username}" in text:
        try:
            from openai import ChatCompletion
            response = ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": "You are OWPC Alpha AI."}, {"role": "user", "content": text}],
                max_tokens=150
            )
            await update.message.reply_text(response.choices[0].message.content)
        except: pass

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin_bonus", admin_bonus))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 OWPC Bot v3.6 VIRAL LIVE...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
