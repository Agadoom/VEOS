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
DB_PATH = "owpc_data.db" 
WEBAPP_URL = "https://veos-production.up.railway.app" 
LOGO_PATH = "media/owpc_logo.png"

# --- 📊 SYNCHRONIZED RANK LOGIC ---
def calculate_rank(points):
    if points >= 100000: return "💎 LEGEND"
    if points >= 50000:  return "👑 ELITE"
    if points >= 15000:  return "🎖️ COMMANDER"
    if points >= 5000:   return "⚔️ WARRIOR"
    if points >= 1000:   return "🛡️ GUARDIAN"
    return "🆕 SEEKER"

# --- 📊 DATABASE ACCESS ---
def get_user_full_data(user_id):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo, last_checkin, referrals FROM users WHERE user_id = ?", (user_id,))
        res = c.fetchone(); conn.close()
        if res:
            g, u, v = (res[0] or 0), (res[1] or 0), (res[2] or 0.0)
            total = g + u + v
            return {"genesis": g, "unity": u, "veo": v, "total": int(total), "last_checkin": res[3], "refs": res[4] or 0, "rank": calculate_rank(total)}
    except: pass
    return {"genesis": 0, "unity": 0, "veo": 0, "total": 0, "last_checkin": None, "refs": 0, "rank": "🆕 SEEKER"}

# --- ⌨️ KEYBOARDS ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb")],
        [InlineKeyboardButton("🆔 Passport", callback_data="my_card"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🔗 Invite", callback_data="get_invite")],
        [InlineKeyboardButton("📡 Live Feed", callback_data="live_feed"), InlineKeyboardButton("🗺️ Roadmap", callback_data="view_roadmap")]
    ])

def back_btn(): return [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]

# --- 🛠️ HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()
    
    data = get_user_full_data(user.id)
    cap = (f"🕊️ **OWPC PROTOCOL**\n\n"
           f"👤 **Commander:** {user.first_name}\n"
           f"🏆 **Rank:** {data['rank']}\n"
           f"💰 **Balance:** {data['total']:,} OWPC")
    
    if os.path.exists(LOGO_PATH):
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name
    data = get_user_full_data(uid)

    if query.data == "back_home":
        cap = f"🕊️ **Main Menu**\nRank: {data['rank']}\nBalance: {data['total']:,} OWPC"
        await query.message.edit_caption(caption=cap, reply_markup=main_menu_kb(), parse_mode="Markdown")

    elif query.data == "invest_hub":
        invest_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [back_btn()]
        ])
        await query.message.edit_caption(caption="💰 **INVEST HUB**\n\nChoisissez un pilier pour acquérir des actifs et monter en grade.", reply_markup=invest_kb)

    elif query.data == "get_invite":
        link = f"https://t.me/owpcsbot?start={uid}"
        await query.message.edit_caption(caption=f"🔗 **INVITATION**\n\nTon lien :\n`{link}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, (points_genesis + points_unity + points_veo) as total FROM users ORDER BY total DESC LIMIT 5")
        top = c.fetchall(); conn.close()
        lb = "🏛️ **LEADERBOARD**\n\n"
        for i, u in enumerate(top, 1): lb += f"{i}. {u[0]} - {int(u[1]):,} OWPC\n"
        await query.message.edit_caption(caption=lb, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "view_stats":
        stats = (f"📊 **VOS ACTIFS**\n\n"
                 f"🧬 Genesis: {data['genesis']:,}\n"
                 f"🌍 Unity: {data['unity']:,}\n"
                 f"🤖 Veo AI: {data['veo']:.2f}\n"
                 f"──────────────\n"
                 f"💰 TOTAL: {data['total']:,} OWPC")
        await query.message.edit_caption(caption=stats, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "my_card":
        await query.message.edit_caption(caption=f"🆔 **PASSPORT**\n\nNom: {name}\nRang: {data['rank']}\nStatut: VÉRIFIÉ ✅", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if data['last_checkin'] == today:
            await query.message.reply_text("⏳ Déjà réclamé aujourd'hui.")
        else:
            win = random.randint(50, 150)
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE users SET points_genesis = points_genesis + ?, last_checkin = ? WHERE user_id = ?", (win, today, uid))
            conn.commit(); conn.close()
            await query.message.reply_text(f"🎰 Lucky Draw : +{win} OWPC !")

    # --- RETOUR DES BOUTONS MANQUANTS ---
    elif query.data == "live_feed":
        await query.message.edit_caption(caption="📡 **LIVE FEED**\n\n• Protocol Status: Stable\n• Network Nodes: Online\n• Mining: Active", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "view_roadmap":
        roadmap = ("🗺️ **ROADMAP 2026**\n\n"
                   "Q1: Lancement Terminal (Done)\n"
                   "Q2: Activation Staking Unity\n"
                   "Q3: Gouvernance DAO\n"
                   "Q4: Listing DEX")
        await query.message.edit_caption(caption=roadmap, reply_markup=InlineKeyboardMarkup([back_btn()]))

# --- MAIN ---
async def main():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, points_genesis INTEGER DEFAULT 0, points_unity INTEGER DEFAULT 0, points_veo REAL DEFAULT 0.0, referrals INTEGER DEFAULT 0, rank TEXT, last_checkin TEXT)")
    conn.commit(); conn.close()
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot One World Peace Coins (Restored & Fixed) Online...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
