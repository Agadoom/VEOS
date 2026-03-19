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

# --- 🌐 FASTAPI (Pour la Mini App) ---
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
        <head><title>OWPC Terminal</title></head>
        <body style="background:#000;color:#0f0;text-align:center;font-family:monospace;">
            <h1>🚀 OWPC TERMINAL ACTIVE</h1>
            <p>Connecté au Protocole...</p>
        </body>
    </html>
    """

# --- 🤖 BOT LOGIC (Ton menu stable) ---
def get_user_full_data(user_id):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id = ?", (user_id,))
        res = c.fetchone(); conn.close()
        if res:
            total = (res[0] or 0) + (res[1] or 0) + (res[2] or 0.0)
            return int(total)
    except: pass
    return 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    total = get_user_full_data(uid)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🆔 Passport", callback_data="my_card")]
    ])
    await update.message.reply_text(f"🕊️ **OWPC PROTOCOL**\n\nBalance: {total:,} OWPC", reply_markup=kb, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "view_stats":
        await query.message.edit_text("📊 Stats en cours de sync...")

# --- 🚀 LANCEMENT SIMULTANÉ ---
async def run_bot():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    
    await bot_app.initialize()
    await bot_app.start()
    # Le secret est ici : drop_pending_updates=True pour éviter le "Conflict"
    print("🤖 Bot Telegram démarré...")
    await bot_app.updater.start_polling(drop_pending_updates=True)

async def main():
    # On lance le bot en arrière-plan
    asyncio.create_task(run_bot())
    
    # On lance le serveur Web (FastAPI) sur le port imposé par Railway
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")
    server = uvicorn.Server(config)
    print(f"🌐 Mini App Server démarré sur le port {PORT}...")
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
