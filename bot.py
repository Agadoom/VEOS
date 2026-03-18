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
DB_PATH = "owpc_data.db" 
WEBAPP_URL = "https://veos-production.up.railway.app" 

# --- 📊 SYNCHRONIZED RANK LOGIC ---
def calculate_rank(points):
    if points >= 100000: return "💎 LEGEND"
    if points >= 50000:  return "👑 ELITE"
    if points >= 15000:  return "🎖️ COMMANDER"
    if points >= 5000:   return "⚔️ WARRIOR"
    if points >= 1000:   return "🛡️ GUARDIAN"
    return "🆕 SEEKER"

# --- 📊 DATABASE LOGIC ---
def init_db():
    """S'assure que la table existe si elle n'est pas encore créée"""
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis INTEGER DEFAULT 0, points_unity INTEGER DEFAULT 0,
                  points_veo REAL DEFAULT 0.0, referrals INTEGER DEFAULT 0,
                  rank TEXT DEFAULT '🆕 SEEKER', last_checkin TEXT DEFAULT '')''')
    conn.commit(); conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, last_checkin FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close()
    if res:
        total = (res[0] or 0) + (res[1] or 0) + (res[2] or 0.0)
        return {"total": int(total), "last_checkin": res[3], "rank": calculate_rank(total)}
    return {"total": 0, "last_checkin": None, "rank": "🆕 SEEKER"}

def update_user_points(user_id, name, bonus=0, daily=None):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # On utilise INSERT OR IGNORE pour créer l'user s'il n'existe pas
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user_id, name))
    if bonus:
        c.execute("UPDATE users SET points_genesis = points_genesis + ? WHERE user_id = ?", (bonus, user_id))
    if daily:
        c.execute("UPDATE users SET last_checkin = ? WHERE user_id = ?", (daily, user_id))
    conn.commit(); conn.close()

# --- ⌨️ KEYBOARDS ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb")],
        [InlineKeyboardButton("🆔 Passport", callback_data="my_card"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🔗 Invite", callback_data="get_invite")]
    ])

def back_btn(): return [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]

# --- 🛠️ HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    update_user_points(user.id, user.first_name)
    data = get_user_data(user.id)
    
    cap = (f"🕊️ **OWPC PROTOCOL**\n\n"
           f"👤 **Commander:** {user.first_name}\n"
           f"🏆 **Rank:** {data['rank']}\n"
           f"💰 **Credits:** {data['total']:,} OWPC")
    
    if os.path.exists(LOGO_PATH):
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name
    data = get_user_data(uid)

    if query.data == "back_home":
        cap = (f"🕊️ **Main Menu**\nRank: {data['rank']}\nCredits: {data['total']:,} OWPC")
        await query.message.edit_caption(caption=cap, reply_markup=main_menu_kb(), parse_mode="Markdown")
    # ... (le reste du code reste identique) ...
    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
                                    [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
                                    [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
                                    back_btn()])
        await query.message.edit_caption(caption="💰 **INVEST HUB**", reply_markup=kb)
    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if data['last_checkin'] == today:
            await query.message.reply_text("⏳ Already claimed!")
        else:
            win = random.randint(50, 150)
            update_user_points(uid, name, bonus=win, daily=today)
            await query.message.reply_text(f"🎰 Lucky Draw: +{win} OWPC!")
    elif query.data == "my_card":
        await query.message.reply_text(f"🆔 **OWPC PASSPORT**\nRank: {data['rank']}")
    elif query.data == "view_stats":
        await query.message.edit_caption(caption=f"📊 **STATS**\nTotal: {data['total']:,} OWPC", reply_markup=InlineKeyboardMarkup([back_btn()]))
    elif query.data == "get_invite":
        await query.message.edit_caption(caption=f"🔗 **LINK**\nhttps://t.me/owpcsbot?start={uid}", reply_markup=InlineKeyboardMarkup([back_btn()]))

# --- MAIN ---
async def main():
    init_db() # IMPORTANT: On crée la table au démarrage
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot Synced & Database Ready...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
