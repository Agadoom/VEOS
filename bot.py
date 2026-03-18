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

# --- CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 1414016840 
BOT_USERNAME = "OwpcInfoBot"
LOGO_PATH = "media/owpc_logo.png"

# --- LIENS OFFICIELS ---
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LINK_CHANNEL = "https://t.me/+SQhKj-gWWmcyODY0"
LINK_X = "https://x.com/DeepTradeX"

# --- BASE DE DONNÉES (CORRIGÉE) ---
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0, last_daily TEXT DEFAULT '', 
                  quests_done INTEGER DEFAULT 0, referred_by INTEGER DEFAULT 0, is_verified INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()
    print("✅ Database ready.")

def update_user(user_id, name, score_inc=0, daily=None, complete_quest=False):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, name, score, last_daily, referred_by, is_verified) VALUES (?, ?, 0, '', 0, 0)", (user_id, name))
    if score_inc: c.execute("UPDATE users SET score = score + ? WHERE id = ?", (score_inc, user_id))
    if daily: c.execute("UPDATE users SET last_daily = ? WHERE id = ?", (daily, user_id))
    if complete_quest: c.execute("UPDATE users SET quests_done = 1 WHERE id = ?", (user_id,))
    c.execute("SELECT score, last_daily, quests_done, is_verified FROM users WHERE id = ?", (user_id,))
    res = c.fetchone(); conn.commit(); conn.close()
    return res

init_db()

# --- INTERFACE ---

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Invest in OWPC", callback_data="invest_hub")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🆔 My Passport", callback_data="my_card")],
        [InlineKeyboardButton("🚀 Quest Center", callback_data="open_q"), InlineKeyboardButton("📊 Global Stats", callback_data="view_stats")],
        [InlineKeyboardButton("📅 Daily Points", callback_data="daily"), InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ])

# --- GESTIONNAIRES ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    
    # MESSAGE D'ACCUEIL PERSONNALISÉ
    cap = (f"🕊️ **Welcome to the Hive, {user.first_name}!**\n\n"
           f"Your current status: **Active Citizen**\n"
           f"Credits: **{res[0]} OWPC PTS**\n\n"
           "Use the menu below to manage your assets and identity.")
    
    if os.path.exists(LOGO_PATH):
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name
    res = update_user(uid, name)

    # 1. RETOUR AU MENU
    if query.data == "back_home":
        await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nCitizen: {name}\nPoints: {res[0]}", reply_markup=main_menu_kb())

    # 2. INVEST HUB
    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS)], [InlineKeyboardButton("💎 UNITY", url=LINK_UNITY)], [InlineKeyboardButton("⚡ VEO", url=LINK_VEO)], [InlineKeyboardButton("⬅️ Back", callback_data="back_home")]])
        await query.message.edit_caption(caption="💰 **INVESTOR HUB**\n\nSelect a token to buy on Blum Memepad:", reply_markup=kb)

    # 3. QUEST CENTER
    elif query.data == "open_q":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Channel", url=LINK_CHANNEL)], [InlineKeyboardButton("🐦 X", url=LINK_X)], [InlineKeyboardButton("💰 Claim (+100)", callback_data="claim_q")], [InlineKeyboardButton("⬅️ Back", callback_data="back_home")]])
        await query.message.edit_caption(caption="🚀 **QUEST CENTER**\n\nComplete all tasks to claim your reward.", reply_markup=kb)

    # 4. DAILY POINTS
    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if res[1] == today:
            await query.message.reply_text("⏳ Come back tomorrow for more points!")
        else:
            update_user(uid, name, score_inc=15, daily=today)
            await query.message.reply_text("✅ Daily Reward: +15 Points added!")

    # 5. STATS
    elif query.data == "view_stats":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT COUNT(*), SUM(score) FROM users"); s = c.fetchone(); conn.close()
        await query.message.edit_caption(caption=f"📊 **GLOBAL STATS**\n\nCitizens: {s[0]}\nTotal Supply: {s[1]} Credits", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]))

    # 6. LEADERBOARD
    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 5")
        lb_txt = "🏆 **TOP 5 CITIZENS**\n\n" + "\n".join([f"👤 {r[0]}: {r[1]} pts" for r in c.fetchall()])
        conn.close()
        await query.message.edit_caption(caption=lb_txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]))

    # 7. INVITE
    elif query.data == "get_invite":
        txt = f"🔗 **YOUR REFERRAL LINK**\n\n`https://t.me/{BOT_USERNAME}?start=ref_{uid}`\n\nShare this to earn 50 points per friend!"
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]), parse_mode="Markdown")

    # 8. PASSPORT (Lancement manuel car nouvelle image)
    elif query.data == "my_card":
        await query.message.reply_text("🆔 Use /passport to generate your official ID!")

# --- LANCEMENT ---
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 OWPC v5.7 Ready - No more errors.")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
