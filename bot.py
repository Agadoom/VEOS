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

# --- 📊 DATABASE & DATA ---
def get_user_full_data(user_id):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo, last_checkin, referrals FROM users WHERE user_id = ?", (user_id,))
        res = c.fetchone(); conn.close()
        if res:
            g, u, v = (res[0] or 0), (res[1] or 0), (res[2] or 0.0)
            total = g + u + v
            return {"genesis": g, "unity": u, "veo": v, "total": int(total), "refs": res[4] or 0}
    except: pass
    return {"genesis": 0, "unity": 0, "veo": 0, "total": 0, "refs": 0}

def calculate_rank(points):
    if points >= 100000: return "💎 LEGEND"
    if points >= 50000:  return "👑 ELITE"
    if points >= 15000:  return "🎖️ COMMANDER"
    if points >= 5000:   return "⚔️ WARRIOR"
    if points >= 1000:   return "🛡️ GUARDIAN"
    return "🆕 SEEKER"

# --- ⌨️ KEYBOARDS (Vérifie bien les callback_data ici) ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb")],
        [InlineKeyboardButton("🆔 Passport", callback_data="my_card"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🔗 Invite", callback_data="get_invite")],
        [InlineKeyboardButton("📡 Live Feed", callback_data="live_feed"), InlineKeyboardButton("🗺️ Roadmap", callback_data="view_roadmap")]
    ])

# --- 🛠️ HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()
    
    data = get_user_full_data(user.id)
    rank = calculate_rank(data['total'])
    cap = f"🕊️ **OWPC PROTOCOL**\n\n👤 **Commander:** {user.first_name}\n🏆 **Rank:** {rank}\n💰 **Balance:** {data['total']:,} OWPC"
    
    if os.path.exists(LOGO_PATH):
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = query.from_user.id
    # Log pour débuguer sur Railway
    print(f"DEBUG: Clic détecté sur -> {query.data}")

    if query.data == "back_home":
        data = get_user_full_data(uid)
        rank = calculate_rank(data['total'])
        await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nRank: {rank}\nBalance: {data['total']:,} OWPC", reply_markup=main_menu_kb(), parse_mode="Markdown")

    # --- LE FIX POUR INVEST HUB ---
    elif query.data == "invest_hub":
        invest_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_home")]
        ])
        await query.message.edit_caption(caption="💰 **INVEST HUB**\n\nSélectionnez un actif pour investir via Memepad.", reply_markup=invest_kb)

    elif query.data == "get_invite":
        link = f"https://t.me/owpcsbot?start={uid}"
        await query.message.edit_caption(caption=f"🔗 **REFERRAL**\n\nLien d'invitation :\n`{link}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]))

    elif query.data == "view_stats":
        data = get_user_full_data(uid)
        txt = f"📊 **ASSETS**\n\nGenesis: {data['genesis']:,}\nUnity: {data['unity']:,}\nVeo: {data['veo']:.2f}\n\nTotal: {data['total']:,}"
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]))

    elif query.data == "live_feed":
        await query.message.edit_caption(caption="📡 **LIVE FEED**\n\nNodes: Online\nSync: 100%", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]))

    elif query.data == "view_roadmap":
        await query.message.edit_caption(caption="🗺️ **ROADMAP**\n\nPhase 2 : Mars 2026", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]))

# --- MAIN ---
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot Démarré...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
