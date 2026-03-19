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

# --- PART 1: WEB SERVER (MINI APP) ---
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
        <body style="background:#000;color:#0f0;text-align:center;font-family:monospace;padding-top:100px;">
            <h1 style="border:2px solid #0f0;display:inline-block;padding:20px;">🚀 OWPC TERMINAL ONLINE</h1>
            <p>Protocol Status: <span style="color:white;">STABLE</span></p>
        </body>
    </html>
    """

def run_web():
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="error")

# --- PART 2: DATABASE LOGIC ---
def get_user_stats(uid):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
        res = c.fetchone()
        conn.close()
        if res:
            total = (res[0] or 0) + (res[1] or 0) + (res[2] or 0.0)
            return {"total": int(total), "g": res[0], "u": res[1], "v": res[2]}
    except: pass
    return {"total": 0, "g": 0, "u": 0, "v": 0}

# --- PART 3: BOT LOGIC (ALL ENGLISH) ---
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="pass"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="ref")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    
    # Init User in DB
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    conn.commit(); conn.close()
    
    stats = get_user_stats(uid)
    await update.message.reply_text(
        f"🕊️ **OWPC PROTOCOL**\n\n"
        f"Welcome Commander, **{name}**\n"
        f"Global Balance: `{stats['total']:,} OWPC`",
        reply_markup=main_kb(),
        parse_mode="Markdown"
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    stats = get_user_stats(uid)

    if query.data == "menu":
        await query.message.edit_text(
            f"🕊️ **OWPC PROTOCOL**\n\nGlobal Balance: `{stats['total']:,} OWPC`",
            reply_markup=main_kb(),
            parse_mode="Markdown"
        )

    elif query.data == "stats":
        txt = (f"📊 **DETAILED ASSETS**\n\n"
               f"🧬 Genesis: `{stats['g']:,}`\n"
               f"🌍 Unity: `{stats['u']:,}`\n"
               f"🤖 Veo AI: `{stats['v']:.2f}`\n\n"
               f"Total: `{stats['total']:,} OWPC`")
        await query.message.edit_text(txt, parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu")]]))

    elif query.data == "pass":
        txt = (f"🆔 **OWPC PASSPORT**\n\n"
               f"Holder: `{query.from_user.first_name}`\n"
               f"ID: `{uid}`\n"
               f"Status: `VERIFIED ✅`\n"
               f"Network: `Active`")
        await query.message.edit_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu")]]))

    elif query.data == "invest":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu")]
        ])
        await query.message.edit_text("💰 **INVEST HUB**\nSelect an asset to grow your portfolio.", reply_markup=kb)

def run_bot():
    if not TOKEN: return
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_app = ApplicationBuilder().token(TOKEN).build()
    
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_buttons))
    
    print("✅ [BOT] English Protocol Active")
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    p1 = Process(target=run_web)
    p2 = Process(target=run_bot)
    p1.start()
    p2.start()
    p1.join()
    p2.join()
