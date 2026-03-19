import os
import asyncio
import sqlite3
import random
import nest_asyncio
import uvicorn
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

nest_asyncio.apply()

# --- ⚙️ CONFIG ---
TOKEN = os.getenv("TOKEN") 
DB_PATH = "owpc_data.db" 
WEBAPP_URL = "https://veos-production.up.railway.app" 
PORT = int(os.getenv("PORT", 8080))
LOGO_PATH = "media/owpc_logo.png" # Vérifie bien que ce dossier existe sur ton GitHub

app = FastAPI()

# --- 🌐 MINI APP INTERFACE (FastAPI) ---
@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
        <head><title>OWPC Terminal</title></head>
        <body style="background:#000;color:#0f0;text-align:center;font-family:monospace;padding:50px;">
            <h1 style="border:1px solid #0f0;display:inline-block;padding:10px;">🚀 OWPC TERMINAL ACTIVE</h1>
            <p>Protocol Synchronization: 100%</p>
            <p>Nodes: Online</p>
        </body>
    </html>
    """

# --- 📊 DATABASE & LOGIC ---
def get_user_full_data(user_id):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo, last_checkin, referrals FROM users WHERE user_id = ?", (user_id,))
        res = c.fetchone(); conn.close()
        if res:
            g, u, v = (res[0] or 0), (res[1] or 0), (res[2] or 0.0)
            total = g + u + v
            return {"total": int(total), "genesis": g, "unity": u, "veo": v, "refs": res[4] or 0, "last": res[3]}
    except: pass
    return {"total": 0, "genesis": 0, "unity": 0, "veo": 0, "refs": 0, "last": None}

def calculate_rank(points):
    if points >= 100000: return "💎 LEGEND"
    if points >= 50000:  return "👑 ELITE"
    if points >= 15000:  return "🎖️ COMMANDER"
    if points >= 5000:   return "⚔️ WARRIOR"
    if points >= 1000:   return "🛡️ GUARDIAN"
    return "🆕 SEEKER"

# --- ⌨️ KEYBOARDS ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb")],
        [InlineKeyboardButton("🆔 Passport", callback_data="my_card"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🔗 Invite", callback_data="get_invite")]
    ])

# --- 🤖 BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()
    
    data = get_user_full_data(user.id)
    rank = calculate_rank(data['total'])
    cap = (f"🕊️ **OWPC PROTOCOL**\n\n"
           f"👤 **Commander:** {user.first_name}\n"
           f"🏆 **Rank:** {rank}\n"
           f"💰 **Balance:** {data['total']:,} OWPC")
    
    try:
        if os.path.exists(LOGO_PATH):
            await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
        else:
            await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    except:
        await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid = query.from_user.id
    data = get_user_full_data(uid)
    rank = calculate_rank(data['total'])

    if query.data == "back_home":
        await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nRank: {rank}\nBalance: {data['total']:,} OWPC", reply_markup=main_menu_kb(), parse_mode="Markdown")

    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_home")]
        ])
        await query.message.edit_caption(caption="💰 **INVEST HUB**\nBoostez votre rang via Memepad.", reply_markup=kb)

    elif query.data == "view_stats":
        txt = f"📊 **ASSETS**\n\nGenesis: {data['genesis']:,}\nUnity: {data['unity']:,}\nVeo: {data['veo']:.2f}\n\nTotal: {data['total']:,} OWPC"
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]))

    elif query.data == "my_card":
        txt = f"🆔 **PASSPORT**\n\nHolder: {query.from_user.first_name}\nRank: {rank}\nStatus: VERIFIED ✅"
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]))

# --- 🚀 RUN EVERYTHING ---
async def run_bot():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(drop_pending_updates=True)

async def main():
    asyncio.create_task(run_bot())
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
