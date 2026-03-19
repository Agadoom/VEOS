import os
import sqlite3
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app"

app = FastAPI()

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis INTEGER DEFAULT 0, points_unity INTEGER DEFAULT 0, 
                  points_veo REAL DEFAULT 0.0)''')
    conn.commit(); conn.close()

# --- BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport")]
    ])
    await update.message.reply_text(f"🕊️ **OWPC PROTOCOL**\n\nWelcome Commander!", reply_markup=kb, parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "invest":
        invest_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ Back", callback_data="main")]
        ])
        await query.message.edit_text("💰 **INVEST HUB**", reply_markup=invest_kb)
    elif query.data == "main":
        await start(query, context) # Simple return to main menu

# --- THE FIX: LIFESPAN HANDLING ---
@app.on_event("startup")
async def startup_event():
    init_db()
    # On initialise le bot ici
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_callbacks))
    
    await bot_app.initialize()
    await bot_app.start()
    # ON LANCE LE POLLING EN TÂCHE DE FOND
    asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    print("✅ [SYSTEM] BOT IS NOW LISTENING")

@app.get("/", response_class=HTMLResponse)
async def home():
    return "<h1>🚀 TERMINAL ONLINE</h1>"

# --- MAIN ENTRY ---
if __name__ == "__main__":
    # Très important: ne pas mettre de code après uvicorn.run
    print(f"🌐 [SYSTEM] STARTING WEB SERVER ON PORT {PORT}")
    uvicorn.run("bot:app", host="0.0.0.0", port=PORT, factory=False)
