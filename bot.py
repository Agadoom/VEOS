import os
import asyncio
import sqlite3
import random
import nest_asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

nest_asyncio.apply()

# --- ⚙️ CONFIG ---
TOKEN = os.getenv("TOKEN")
LOGO_PATH = "media/owpc_logo.png"
WEBAPP_URL = "https://veos-production.up.railway.app" 
DB_PATH = "owpc_data.db" 

# --- 📊 DATABASE INITIALIZATION (CRITIQUE) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # On crée la table users si elle n'existe pas
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0, 
                  rank TEXT DEFAULT 'NEWBIE', last_checkin TEXT DEFAULT '')''')
    # On crée la table settings si elle n'existe pas
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('live_feed', 'Welcome to the Hive! 🚀')")
    conn.commit()
    conn.close()
    print("✅ Database initialized and table 'users' is ready.")

def get_user_data(user_id):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points, last_checkin, rank FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close(); return res

def update_user_db(user_id, name, score_inc=0, daily=None):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # Vérification sécurisée
    c.execute("INSERT OR IGNORE INTO users (user_id, name, points, rank) VALUES (?, ?, 0, 'NEWBIE')", (user_id, name))
    if score_inc:
        c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (score_inc, user_id))
    if daily:
        c.execute("UPDATE users SET last_checkin = ? WHERE user_id = ?", (daily, user_id))
    conn.commit(); conn.close()
    return get_user_data(user_id)

# --- ⌨️ KEYBOARDS ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH HIVE APP", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🏛️ Leaderboard", callback_data="view_lb")],
        [InlineKeyboardButton("📡 Live Feed", callback_data="live_feed"), InlineKeyboardButton("💎 Staking Sim", callback_data="staking_sim")],
        [InlineKeyboardButton("🆔 Passport", callback_data="my_card"), InlineKeyboardButton("🚀 Quests", callback_data="open_q")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("🗺️ Roadmap", callback_data="view_roadmap"), InlineKeyboardButton("🔗 Invite", callback_data="get_invite")]
    ])

def back_btn(): return [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]

# --- 🛠️ HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # On met à jour ou on crée l'utilisateur
    res = update_user_db(user.id, user.first_name)
    points = res[0] if res else 0
    cap = f"🕊️ **Welcome to OWPC HIVE**\n\nCommander: {user.first_name}\nCredits: {points:,} OWPC"
    
    if os.path.exists(LOGO_PATH):
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name
    res = get_user_data(uid)
    score = res[0] if res else 0

    if query.data == "back_home":
        await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nCredits: {score:,} OWPC", reply_markup=main_menu_kb(), parse_mode="Markdown")

    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            back_btn()
        ])
        await query.message.edit_caption(caption="💰 **INVEST HUB**", reply_markup=kb)

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if res and res[1] == today:
            await query.message.reply_text("⏳ Come back tomorrow!")
        else:
            win = random.randint(20, 100)
            update_user_db(uid, name, score_inc=win, daily=today)
            await query.message.reply_text(f"🎰 Lucky Draw: +{win} PTS!")
    
    # Ajoute ici les autres elif (open_q, staking_sim, etc.) comme précédemment

# --- MAIN ---
async def main():
    # 1. INITIALISER LA BASE AVANT TOUT
    init_db()
    
    # 2. LANCER LE BOT
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is starting...")
    await app.run_polling(drop_pending_updates=True) # drop_pending_updates évite le conflit au démarrage

if __name__ == "__main__":
    asyncio.run(main())
