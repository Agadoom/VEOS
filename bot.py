import os
import sqlite3
import asyncio
from multiprocessing import Process
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

# --- PARTIE 1 : LE SERVEUR WEB (Mini App) ---
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def home():
    return "<html><body style='background:#000;color:#0f0;text-align:center;font-family:monospace;'><h1>🚀 TERMINAL OWPC CONNECTÉ</h1></body></html>"

def run_web():
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="error")

# --- PARTIE 2 : LOGIQUE DU BOT ---
def get_stats(uid):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
        res = c.fetchone(); conn.close()
        if res: return {"total": int(res[0]+res[1]+res[2]), "g": res[0], "u": res[1], "v": res[2]}
    except: pass
    return {"total": 0, "g": 0, "u": 0, "v": 0}

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="pass"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="ref")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, update.effective_user.first_name))
    conn.commit(); conn.close()
    
    stats = get_stats(uid)
    await update.message.reply_text(f"🕊️ **OWPC PROTOCOL**\n\nBalance: {stats['total']:,} OWPC", reply_markup=main_kb(), parse_mode="Markdown")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    stats = get_stats(uid)

    if query.data == "stats":
        txt = f"📊 **VOS ACTIFS**\n\nGenesis: {stats['g']}\nUnity: {stats['u']}\nVeo AI: {stats['v']:.2f}"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Retour", callback_data="menu")]]))
    
    elif query.data == "menu":
        await query.message.edit_text(f"🕊️ **OWPC PROTOCOL**\n\nBalance: {stats['total']:,} OWPC", reply_markup=main_kb(), parse_mode="Markdown")
    
    elif query.data == "invest":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("⬅️ Retour", callback_data="menu")]
        ])
        await query.message.edit_text("💰 **INVEST HUB**", reply_markup=kb)

    elif query.data == "pass":
        await query.message.edit_text(f"🆔 **PASSPORT**\n\nNom: {query.from_user.first_name}\nStatus: ACTIF ✅", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Retour", callback_data="menu")]]))

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_app = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_buttons))
    
    print("✅ [BOT] Prêt et cliquable !")
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    p1 = Process(target=run_web)
    p2 = Process(target=run_bot)
    p1.start()
    p2.start()
    p1.join()
    p2.join()
