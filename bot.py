import os
import asyncio
import sqlite3
import nest_asyncio
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

nest_asyncio.apply()

# -------- CONFIGURATION --------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 1414016840 
BOT_USERNAME = "OwpcInfoBot"

# -------- LIENS & ASSETS --------
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LINK_CHANNEL = "https://t.me/+SQhKj-gWWmcyODY0"
LINK_X = "https://x.com/DeepTradeX"

# -------- DATABASE LOGIC --------
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER, last_daily TEXT, 
                  quests_done INTEGER DEFAULT 0, referred_by INTEGER, is_verified INTEGER DEFAULT 0)''')
    try: c.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
    except: pass
    conn.commit(); conn.close()

def update_user(user_id, name, score_inc=0, daily=None, complete_quest=False, referred_by=None, verify=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, name, score, last_daily, referred_by, is_verified) VALUES (?, ?, 0, '', ?, 0)", (user_id, name, referred_by))
    if score_inc: c.execute("UPDATE users SET score = score + ?, name = ? WHERE id = ?", (score_inc, name, user_id))
    if daily: c.execute("UPDATE users SET last_daily = ?, name = ? WHERE id = ?", (daily, name, user_id))
    if complete_quest: c.execute("UPDATE users SET quests_done = 1 WHERE id = ?", (user_id,))
    if verify is not None: c.execute("UPDATE users SET is_verified = ? WHERE id = ?", (verify, user_id))
    c.execute("SELECT score, last_daily, quests_done, is_verified FROM users WHERE id = ?", (user_id,))
    res = c.fetchone()
    conn.commit(); conn.close()
    return res

init_db()

# -------- VISUALS --------
def create_visual_card(name, score, rank, uid, is_verified=False):
    w, h = 1600, 900
    base = Image.new('RGB', (w, h), (10, 10, 18))
    draw = ImageDraw.Draw(base)
    gold, white = (212, 175, 55), (245, 245, 245)
    draw.rectangle([30, 30, 1570, 870], outline=gold, width=8)
    try:
        logo = Image.open("media/owpc_logo.png").convert("RGBA")
        base.paste(logo.resize((150, 150)), (1380, 60), logo.resize((150, 150)))
    except: pass
    draw.text((100, 80), "OWPC DIGITAL PASSPORT", fill=gold)
    draw.text((100, 300), f"HOLDER: {name.upper()}", fill=white)
    draw.text((100, 420), f"RANK: {rank}", fill=gold)
    draw.text((100, 540), f"CREDITS: {score} OWPC PTS", fill=white)
    if is_verified:
        draw.ellipse([1200, 200, 1500, 500], outline=gold, width=6)
        draw.text((1260, 320), "VERIFIED", fill=gold)
    draw.text((100, 780), f"UID: {uid}", fill=(120, 120, 120))
    bio = BytesIO(); bio.name = 'passport.png'; base.save(bio, 'PNG'); bio.seek(0)
    return bio

def get_rank_info(score):
    if score >= 1000: return "👑 ALPHA LEGEND"
    if score >= 500:  return "💎 UNITY GUARDIAN"
    if score >= 100:  return "🛠️ BUILDER"
    return "🐣 SEEKER"

# -------- COMMAND LOGIC (SYNCED WITH MENU) --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    kb = [
        [InlineKeyboardButton("💰 Invest in OWPC", callback_data="invest_hub")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🆔 My Passport", callback_data="my_card")],
        [InlineKeyboardButton("🚀 Quest Center", callback_data="open_q"), InlineKeyboardButton("📊 Global Stats", callback_data="view_stats")],
        [InlineKeyboardButton("📅 Daily Points", callback_data="daily"), InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ]
    cap = f"🕊️ **OWPC Ecosystem v5.1**\n\nRank: {get_rank_info(res[0])}\nPoints: {res[0]}"
    try: await update.message.reply_photo(photo=open("media/owpc_logo.png", "rb"), caption=cap, reply_markup=InlineKeyboardMarkup(kb))
    except: await update.message.reply_text(cap, reply_markup=InlineKeyboardMarkup(kb))

async def invest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = "💰 **OWPC INVESTOR CENTER**\n\nChoose your asset to buy on Blum Memepad:"
    kb = [[InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS)], [InlineKeyboardButton("💎 UNITY", url=LINK_UNITY)], [InlineKeyboardButton("⚡ VEO", url=LINK_VEO)]]
    await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def passport_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    res = update_user(uid, name)
    rank = get_rank_info(res[0])
    card = create_visual_card(name, res[0], rank, uid, is_verified=(res[3] == 1))
    await update.message.reply_photo(photo=card, caption=f"🆔 Passport for {name}")

async def invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(f"🔗 **INVITE LINK:**\n`https://t.me/{BOT_USERNAME}?start=ref_{uid}`")

# -------- CALLBACK HANDLER --------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid, name = query.from_user.id, query.from_user.first_name
    await query.answer()

    if query.data == "invest_hub":
        await invest_command(query, context)
    elif query.data == "my_card":
        await passport_command(query, context)
    elif query.data == "open_q":
        kb = [[InlineKeyboardButton("📢 Channel", url=LINK_CHANNEL)], [InlineKeyboardButton("🐦 X", url=LINK_X)], [InlineKeyboardButton("💰 Claim (+100)", callback_data="claim_q")]]
        await query.message.reply_text("🚀 **QUEST CENTER**", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data == "claim_q":
        res = update_user(uid, name)
        if res[2] == 1: await query.message.reply_text("❌ Done!")
        else:
            update_user(uid, name, score_inc=100, complete_quest=True)
            await query.message.reply_text("🔥 +100 Points!")
    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        res = update_user(uid, name)
        if res[1] == today: await query.message.reply_text("⏳ Tomorrow!")
        else:
            update_user(uid, name, score_inc=15, daily=today)
            await query.message.reply_text("✅ +15 Points!")
    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
        txt = "🏆 **TOP 10**\n\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]}" for i, r in enumerate(c.fetchall())])
        await query.message.reply_text(txt)
    elif query.data == "get_invite":
        await invite_command(query, context)
    elif query.data == "view_stats":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT COUNT(*), SUM(score) FROM users")
        s = c.fetchone()
        await query.message.reply_text(f"📊 Citizens: {s[0]}\nTotal Pts: {s[1]}")

# -------- ADMIN --------
async def verify_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        tid = int(context.args[0])
        update_user(tid, "Verified", verify=1, score_inc=500)
        await update.message.reply_text(f"✅ {tid} VERIFIED.")
        await context.bot.send_message(chat_id=tid, text="👑 Profile VERIFIED!")
    except: pass

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("invest", invest_command))
    app.add_handler(CommandHandler("veos", invest_command)) # Raccourci pour ton ancienne commande
    app.add_handler(CommandHandler("passport", passport_command))
    app.add_handler(CommandHandler("invite", invite_command))
    app.add_handler(CommandHandler("verify", verify_user))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 OWPC v5.1 - Menu Synced")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
