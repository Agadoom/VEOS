import os
import asyncio
import sqlite3
import random
import nest_asyncio
import uvicorn
from threading import Thread
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

nest_asyncio.apply()

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app"
PORT = int(os.getenv("PORT", 8080))

app = FastAPI()

# --- 🌐 WEBAPP INTERFACE ---
@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <body style="background:#000;color:#0f0;text-align:center;font-family:monospace;padding-top:50px;">
        <h1 style="border:1px solid #0f0;display:inline-block;padding:10px;">🚀 OWPC TERMINAL</h1>
        <p>SYSTEM ONLINE | NODES SYNCED</p>
    </body>
    """

# --- 📊 DATA LOGIC ---
def get_user_stats(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
    res = c.fetchone(); conn.close()
    if res:
        return {"total": int(res[0]+res[1]+res[2]), "g": res[0], "u": res[1], "v": res[2]}
    return {"total": 0, "g": 0, "u": 0, "v": 0}

# --- 🤖 BOT MENUS ---
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="pass"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="draw")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="ref")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, update.effective_user.first_name))
    conn.commit(); conn.close()
    
    stats = get_user_stats(uid)
    await update.message.reply_text(f"🕊️ **OWPC PROTOCOL**\n\nBalance: {stats['total']:,} OWPC", 
                                  reply_markup=main_kb(), parse_mode="Markdown")

async def btn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid = query.from_user.id
    stats = get_user_stats(uid)

    if query.data == "back":
        await query.message.edit_text(f"🕊️ **OWPC PROTOCOL**\n\nBalance: {stats['total']:,} OWPC", reply_markup=main_kb(), parse_mode="Markdown")
    
    elif query.data == "stats":
        txt = f"📊 **ASSETS**\n\nGenesis: {stats['g']}\nUnity: {stats['u']}\nVeo: {stats['v']:.2f}"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Retour", callback_data="back")]]))
    
    elif query.data == "invest":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum")], [InlineKeyboardButton("⬅️ Retour", callback_data="back")]])
        await query.message.edit_text("💰 **INVEST HUB**", reply_markup=kb)

# --- 🚀 LE MOTEUR DOUBLE ---
def start_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(btn_handler))
    print("✅ BOT TELEGRAM DÉMARRÉ")
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    # 1. On lance le bot dans un thread séparé
    Thread(target=start_bot, daemon=True).start()
    
    # 2. On lance le serveur Web normalement
    print(f"🌐 SERVEUR WEB SUR PORT {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
