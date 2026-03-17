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
LOGO_PATH = "media/owpc_logo.png"
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LINK_CHANNEL = "https://t.me/+SQhKj-gWWmcyODY0"
LINK_X = "https://x.com/DeepTradeX"
allowed_links = ["deeptrade.bio.link", "t.me/blum", "youtube.com/@deeptradex", "t.me/+SQhKj-gWWmcyODY0"]

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

async def get_ai_response(text):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "You are OWPC AI. Be professional."},
                      {"role": "user", "content": text}],
            max_tokens=150
        )
        return response.choices[0].message.content
    except: return None

# -------- HANDLERS --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    if args and args[0].startswith("ref_"):
        ref_id = int(args[0].replace("ref_", ""))
        if ref_id != user.id:
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("SELECT id FROM users WHERE id = ?", (user.id,))
            if not c.fetchone():
                update_user(ref_id, "Referrer", score_inc=50)
                update_user(user.id, user.first_name, referred_by=ref_id)
                try: await context.bot.send_message(chat_id=ref_id, text="🎉 **Referral Bonus!** +50 PTS added.")
                except: pass

    score_res = update_user(user.id, user.first_name)
    kb = [
        [InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS), InlineKeyboardButton("💎 UNITY", url=LINK_UNITY), InlineKeyboardButton("⚡ VEO", url=LINK_VEO)],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🆔 My Passport", callback_data="my_card")],
        [InlineKeyboardButton("🚀 Quest Center", callback_data="open_q"), InlineKeyboardButton("📊 Global Stats", callback_data="view_stats")],
        [InlineKeyboardButton("📅 Daily", callback_data="daily"), InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ]
    caption = f"🕊️ **OWPC Core v4.2**\n\nWelcome back, **{user.first_name}**.\n\nPoints: {score_res[0]}\nRank: {get_rank_info(score_res[0])[0]}\n\nBuilding the future of decentralized peace. 🚀"
    
    try:
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    except:
        await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid, name = query.from_user.id, query.from_user.first_name
    await query.answer()

    if query.data == "my_card":
        score = update_user(uid, name)[0]
        rank, next_val, msg = get_rank_info(score)
        bar = generate_progress_bar(score, next_val)
        
        # Share status button
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start=ref_{uid}&text=Join%20me%20on%20OWPC!%20My%20Rank:%20{rank}"
        kb = [[InlineKeyboardButton("📣 Share my Status", url=share_url)]]
        
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
        await query.message.reply_text(card, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data == "view_stats":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT COUNT(*), SUM(score) FROM users")
        stats_data = c.fetchone()
        conn.close()
        
        stats_txt = (
            f"📊 **OWPC GLOBAL STATS**\n\n"
            f"👥 **Total Citizens:** {stats_data[0]}\n"
            f"💰 **Total Points Issued:** {stats_data[1]} pts\n"
            f"⚡ **Ecosystem Status:** Viral 🚀\n\n"
            f"Growth is inevitable. 🕊️"
        )
        await query.message.reply_text(stats_txt, parse_mode="Markdown")

    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
        rows = c.fetchall(); conn.close()
        txt = "🏆 **GLOBAL TOP 10**\n\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]} pts" for i, r in enumerate(rows)])
        await query.message.reply_text(txt)

    elif query.data == "get_invite":
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        await query.message.reply_text(f"🔗 **INVITE LINK:**\n`{link}`\n\nEarn +50 PTS for every referral! 🚀", parse_mode="Markdown")

    elif query.data == "open_q":
        kb = [[InlineKeyboardButton("📢 Channel", url=LINK_CHANNEL)], [InlineKeyboardButton("🐦 Follow X", url=LINK_X)], [InlineKeyboardButton("💰 Claim +100", callback_data="claim_q")]]
        await query.message.reply_text("🚀 **QUEST CENTER**", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data == "claim_q":
        res = update_user(uid, name)
        if res[2]: await query.message.reply_text("⏳ Mission already completed!")
        else:
            update_user(uid, name, score_inc=100, complete_quest=True)
            await query.message.reply_text("🔥 **MISSION SUCCESS!** +100 PTS.")

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        res = update_user(uid, name)
        if res[1] == today: await query.message.reply_text("⏳ Tomorrow!")
        else:
            update_user(uid, name, score_inc=10, daily=today)
            await query.message.reply_text("✅ +10 PTS Daily Reward!")

user_messages = defaultdict(list)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user or update.message.from_user.is_bot: return
    user_id, chat_id, text = update.message.from_user.id, update.effective_chat.id, (update.message.text or "").lower()

    # ANTI-SPAM & ANTI-SCAM
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try: await update.message.delete()
        except: pass
        return
    if any(x in text for x in ["http", ".com", ".xyz", "t.me"]) and not any(x in text for x in allowed_links):
        try: await update.message.delete()
        except: pass
        return

    # GROUP LOGIC
    if chat_id == GROUP_CHAT_ID:
        update_user(user_id, update.message.from_user.first_name, score_inc=1)

    # PRIVATE AI LOGIC
    if update.effective_chat.type == "private":
        answer = await get_ai_response(text)
        if answer: await update.message.reply_text(answer)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print(f"🚀 OWPC Bot v4.2 REPAIRED & LIVE")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
