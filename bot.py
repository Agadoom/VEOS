import os
import sqlite3
import asyncio
import uvicorn
from fastapi import FastAPI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app"

app = FastAPI()

# --- DB HELPERS ---
def get_stats(uid):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
        res = c.fetchone(); conn.close()
        if res: return {"total": int((res[0] or 0)+(res[1] or 0)+(res[2] or 0)), "g": res[0], "u": res[1], "v": res[2]}
    except: pass
    return {"total": 0, "g": 0, "u": 0, "v": 0}

# --- KEYBOARD ---
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport")]
    ])

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stats = get_stats(user.id)
    msg = f"🕊️ **OWPC PROTOCOL**\n\nCommander: {user.first_name}\nBalance: {stats['total']:,} OWPC"
    await update.message.reply_text(msg, reply_markup=main_kb(), parse_mode="Markdown")

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    stats = get_stats(query.from_user.id)
    if query.data == "stats":
        await query.message.edit_text(f"📊 Genesis: {stats['g']}\nUnity: {stats['u']}", reply_markup=main_kb())
    elif query.data == "passport":
        await query.message.edit_text(f"🆔 Passport: {query.from_user.first_name}", reply_markup=main_kb())

# --- WEB ---
@app.get("/")
async def root(): return {"status": "running"}

# --- THE FIX: MANUAL STARTUP ---
def run_everything():
    # 1. Configurer le bot
    print("🤖 [STARTING] Bot initialization...")
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(cb_handler))

    # 2. Lancer le polling en tâche de fond
    loop = asyncio.get_event_loop()
    loop.create_task(bot_app.initialize())
    loop.create_task(bot_app.start())
    loop.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    print("✅ [OK] Bot is running background")

    # 3. Lancer le serveur Web (Bloquant, donc à la fin)
    print(f"🌐 [STARTING] Web Server on port {PORT}")
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())

if __name__ == "__main__":
    run_everything()
