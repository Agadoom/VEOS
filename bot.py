import os
import asyncio
import sqlite3
import random
import nest_asyncio
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import uvicorn

nest_asyncio.apply()

# --- ⚙️ CONFIG ---
TOKEN = os.getenv("TOKEN")
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app" # Ton URL Railway
PORT = int(os.getenv("PORT", 8080))

app = FastAPI()

# --- 📊 DATABASE LOGIC (Identique au bot stable) ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis INTEGER DEFAULT 0, points_unity INTEGER DEFAULT 0,
                  points_veo REAL DEFAULT 0.0, referrals INTEGER DEFAULT 0,
                  rank TEXT DEFAULT '🆕 SEEKER', last_checkin TEXT DEFAULT '')''')
    conn.commit(); conn.close()

def get_user_data(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, last_checkin FROM users WHERE user_id=?", (uid,))
    res = c.fetchone(); conn.close()
    if res:
        total = (res[0] or 0) + (res[1] or 0) + (res[2] or 0.0)
        return {"total": int(total), "last_checkin": res[3]}
    return {"total": 0, "last_checkin": None}

# --- 🌐 WEBAPP INTERFACE (HTML) ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return """
    <html>
        <head>
            <title>OWPC Terminal</title>
            <script src="https://telegram.org/js/telegram-web-app.js"></script>
            <style>
                body { background: #000; color: #0f0; font-family: monospace; text-align: center; padding: 20px; }
                .btn { background: #0f0; color: #000; padding: 15px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; width: 80%; }
                .stats { border: 1px solid #0f0; margin: 20px 0; padding: 10px; }
            </style>
        </head>
        <body>
            <h1>🚀 OWPC TERMINAL</h1>
            <div class="stats">
                <p>SYNCING NODES...</p>
                <p id="balance">Balance: Loading...</p>
            </div>
            <button class="btn" onclick="window.location.reload()">REFRESH DATA</button>
            <script>
                let tg = window.Telegram.WebApp;
                tg.expand();
            </script>
        </body>
    </html>
    """

# --- 🤖 BOT LOGIC (Ton menu qui marche) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Init user
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()
    
    data = get_user_data(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🆔 Passport", callback_data="my_card")]
    ])
    await update.message.reply_text(f"🕊️ **OWPC PROTOCOL**\n\nBalance: {data['total']:,} OWPC", parse_mode="Markdown", reply_markup=kb)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid = query.from_user.id
    
    if query.data == "view_stats":
        data = get_user_data(uid)
        await query.message.edit_text(f"📊 **TERMINAL STATS**\nTotal: {data['total']:,} OWPC", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back")]]))
    elif query.data == "back":
        # Relancer l'affichage du menu
        data = get_user_data(uid)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
            [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")]
        ])
        await query.message.edit_text(f"🕊️ **OWPC PROTOCOL**\n\nBalance: {data['total']:,} OWPC", reply_markup=kb)

# --- 🚀 LIFESPAN & RUN ---
async def run_bot():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_buttons))
    
    # drop_pending_updates=True RÈGLE LE PROBLÈME DE CONFLICT
    await bot_app.initialize()
    await bot_app.start()
    print("🤖 Bot is Online...")
    await bot_app.updater.start_polling(drop_pending_updates=True)

if __name__ == "__main__":
    init_db()
    # Lancer le Bot en tâche de fond
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())
    
    # Lancer l'API Web (Mini App)
    print(f"🌐 Web Server on port {PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
