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
    conn.commit()
    conn.close()

def get_stats(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
    res = c.fetchone(); conn.close()
    if res: return {"total": int(res[0]+res[1]+res[2]), "g": res[0], "u": res[1], "v": res[2]}
    return {"total": 0, "g": 0, "u": 0, "v": 0}

# --- BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    conn.commit(); conn.close()
    
    stats = get_stats(uid)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🆔 Passport", callback_data="pass")]
    ])
    await update.message.reply_text(f"🕊️ **OWPC PROTOCOL**\n\nWelcome Commander {name}\nBalance: {stats['total']:,} OWPC", reply_markup=kb, parse_mode="Markdown")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid = query.from_user.id
    stats = get_stats(uid)
    
    if query.data == "stats":
        txt = f"📊 **ASSETS**\nGenesis: {stats['g']}\nUnity: {stats['u']}\nVeo: {stats['v']:.2f}"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu")]]))
    elif query.data == "menu":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))], [InlineKeyboardButton("📊 Stats", callback_data="stats")]])
        await query.message.edit_text("🕊️ **OWPC PROTOCOL**", reply_markup=kb)

# --- FASTAPI & LIFECYCLE ---
@app.on_event("startup")
async def startup_event():
    init_db()
    # On lance le bot en tâche de fond au démarrage de l'app
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_buttons))
    
    await bot_app.initialize()
    await bot_app.start()
    # On utilise create_task pour que le bot tourne sans bloquer FastAPI
    asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    print("✅ BOT STARTED SUCCESSFULLY")

@app.get("/", response_class=HTMLResponse)
async def home():
    return "<html><body style='background:#000;color:#0f0;text-align:center;'><h1>🚀 TERMINAL ONLINE</h1></body></html>"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
