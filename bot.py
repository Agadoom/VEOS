import os
import sqlite3
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app"

app = FastAPI()

# --- DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis INTEGER DEFAULT 0, points_unity INTEGER DEFAULT 0, 
                  points_veo REAL DEFAULT 0.0, referrals INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def get_stats(uid):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo, referrals FROM users WHERE user_id=?", (uid,))
        res = c.fetchone(); conn.close()
        if res:
            total = (res[0] or 0) + (res[1] or 0) + (res[2] or 0.0)
            return {"total": int(total), "g": res[0], "u": res[1], "v": res[2], "refs": res[3] or 0}
    except: pass
    return {"total": 0, "g": 0, "u": 0, "v": 0, "refs": 0}

# --- KEYBOARDS (Vérifie que tous les boutons sont ici) ---
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]])

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    conn.commit(); conn.close()
    
    stats = get_stats(uid)
    msg = (f"🕊️ **OWPC PROTOCOL**\n\n"
           f"Welcome, Commander **{name}**\n"
           f"Global Balance: `{stats['total']:,} OWPC`\n"
           f"Status: `System Online`")
    
    await update.message.reply_text(msg, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    stats = get_stats(uid)

    if query.data == "main_menu":
        await query.message.edit_text(f"🕊️ **OWPC PROTOCOL**\n\nGlobal Balance: `{stats['total']:,} OWPC`", 
                                      reply_markup=main_menu_keyboard(), parse_mode="Markdown")

    elif query.data == "stats":
        stats_msg = (f"📊 **ASSETS OVERVIEW**\n\n"
                     f"🧬 Genesis: `{stats['g']:,}`\n"
                     f"🌍 Unity: `{stats['u']:,}`\n"
                     f"🤖 Veo AI: `{stats['v']:.2f}`\n\n"
                     f"💰 Total: `{stats['total']:,} OWPC`")
        await query.message.edit_text(stats_msg, reply_markup=back_keyboard(), parse_mode="Markdown")

    elif query.data == "passport":
        pass_msg = (f"🆔 **OWPC PASSPORT**\n\n"
                    f"Name: `{query.from_user.first_name}`\n"
                    f"ID: `{uid}`\n"
                    f"Network: `{stats['refs']} members`\n"
                    f"Clearance: `Level 1` ✅")
        await query.message.edit_text(pass_msg, reply_markup=back_keyboard(), parse_mode="Markdown")

    elif query.data == "invest":
        await query.message.edit_text("💰 **INVEST HUB**\n\nAccess Genesis, Unity and Veo AI pools.", 
                                      reply_markup=back_keyboard())

# --- FASTAPI STARTUP ---
@app.on_event("startup")
async def startup_event():
    init_db()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_callbacks))
    
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    print("✅ BOT & DATABASE READY")

@app.get("/", response_class=HTMLResponse)
async def home():
    return "<html><body style='background:#000;color:#0f0;text-align:center;'><h1>🚀 TERMINAL ONLINE</h1></body></html>"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
