import os
import asyncio
import sqlite3
import random
import nest_asyncio
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

nest_asyncio.apply()

# --- ⚙️ CONFIG ---
TOKEN = os.getenv("TOKEN") 
LOGO_PATH = "media/owpc_logo.png"
DB_PATH = "owpc_data.db" 
# C'est ici qu'on pointe vers la Mini App de @OWPCsbot
WEBAPP_URL = "https://veos-production.up.railway.app" 

# --- 📊 LOGIC DB ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0, 
                  rank TEXT DEFAULT 'NEWBIE', last_checkin TEXT DEFAULT '')''')
    conn.commit(); conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points, last_checkin, rank FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close(); return res

def update_user_db(user_id, name, score_inc=0, daily=None):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name, points, rank) VALUES (?, ?, 0, 'NEWBIE')", (user_id, name))
    if score_inc: c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (score_inc, user_id))
    if daily: c.execute("UPDATE users SET last_checkin = ? WHERE user_id = ?", (daily, user_id))
    conn.commit(); conn.close()
    return get_user_data(user_id)

# --- ⌨️ KEYBOARDS ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        # Ce bouton ouvre DIRECTEMENT la Mini App de @OWPCsbot
        [InlineKeyboardButton("🚀 LAUNCH HIVE APP", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb")],
        [InlineKeyboardButton("📡 Live Feed", callback_data="live_feed"), InlineKeyboardButton("💎 Staking Sim", callback_data="staking_sim")],
        [InlineKeyboardButton("🆔 Passport", callback_data="my_card"), InlineKeyboardButton("🚀 Quests", callback_data="open_q")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("🗺️ Roadmap", callback_data="view_roadmap"), InlineKeyboardButton("🔗 Invite", callback_data="get_invite")]
    ])

def back_btn(): return [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]

# --- 🛠️ HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user_db(user.id, user.first_name)
    cap = f"🕊️ **One World Peace Coins**\n\nCommander: {user.first_name}\nCredits: {res[0]:,} OWPC"
    if os.path.exists(LOGO_PATH):
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name
    res = get_user_data(uid)
    score = res[0] if res else 0

    # 🏠 RETOUR ACCUEIL
    if query.data == "back_home":
        await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nCredits: {score:,} OWPC", reply_markup=main_menu_kb(), parse_mode="Markdown")

    # 💰 INVEST HUB (GENESIS, UNITY, VEO)
    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            back_btn()
        ])
        await query.message.edit_caption(caption="💰 **INVEST HUB**\nChoose your pillar:", reply_markup=kb)

    # 🎰 LUCKY DRAW
    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if res and res[1] == today:
            await query.message.reply_text("⏳ Already claimed! Return tomorrow.")
        else:
            win = random.randint(20, 100)
            update_user_db(uid, name, score_inc=win, daily=today)
            await query.message.reply_text(f"🎰 Lucky Draw: +{win} PTS!")

    # 📊 STATS
    elif query.data == "view_stats":
        await query.message.edit_caption(caption=f"📊 **HIVE STATS**\n\nScore: {score:,} OWPC\nRank: SEEKER", reply_markup=InlineKeyboardMarkup([back_btn()]))

    # 🆔 PASSPORT (SIMPLIFIÉ)
    elif query.data == "my_card":
        await query.message.reply_text(f"🆔 **PASSPORT**\nHolder: {name}\nScore: {score:,} OWPC\nVerified: YES ✅")

    # 🏛️ LEADERBOARD
    elif query.data == "view_lb":
        await query.message.edit_caption(caption="🏛️ **HALL OF FAME**\n\n1. Top Global: 154,200\n2. Your position: #142", reply_markup=InlineKeyboardMarkup([back_btn()]))

    # 💎 STAKING
    elif query.data == "staking_sim":
        await query.message.edit_caption(caption="💎 **STAKING SIMULATOR**\nYield: 308 OWPC/month (Estimated)", reply_markup=InlineKeyboardMarkup([back_btn()]))

    # 🚀 QUESTS
    elif query.data == "open_q":
        await query.message.edit_caption(caption="🚀 **QUESTS**\n- Join @owpc_co (+50)\n- Follow X (+50)", reply_markup=InlineKeyboardMarkup([back_btn()]))

    # 📡 LIVE FEED
    elif query.data == "live_feed":
        await query.message.edit_caption(caption="📡 **LIVE FEED**\nHive Protocol is stable. 🚀", reply_markup=InlineKeyboardMarkup([back_btn()]))

    # 🔗 INVITE
    elif query.data == "get_invite":
        await query.message.edit_caption(caption=f"🔗 **INVITE LINK**\nhttps://t.me/OwpcInfoBot?start=ref_{uid}", reply_markup=InlineKeyboardMarkup([back_btn()]))
    
    # 🗺️ ROADMAP
    elif query.data == "view_roadmap":
        await query.message.edit_caption(caption="🗺️ **ROADMAP**\nPhase 2: Mini-App Expansion.", reply_markup=InlineKeyboardMarkup([back_btn()]))

# --- MAIN ---
async def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot One World Peace Coins Online...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
