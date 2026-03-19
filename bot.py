import os
import sqlite3
import asyncio
import uvicorn
from fastapi import FastAPI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app"

app = FastAPI()

# --- DATABASE ---
def get_user_stats(uid):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
        res = c.fetchone(); conn.close()
        if res:
            total = (res[0] or 0) + (res[1] or 0) + (res[2] or 0.0)
            return {"total": int(total), "g": res[0] or 0, "u": res[1] or 0, "v": res[2] or 0.0}
    except: pass
    return {"total": 0, "g": 0, "u": 0, "v": 0.0}

# --- KEYBOARDS ---
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")]
    ])

# --- BOT FUNCTIONS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stats = get_user_stats(user.id)
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()

    msg = (f"🕊️ **OWPC PROTOCOL**\n\n"
           f"👤 **Commander:** {user.first_name}\n"
           f"💰 **Balance:** {stats['total']:,} OWPC\n\n"
           f"System Status: `OPERATIONAL` ✅")
    await update.message.reply_text(msg, reply_markup=main_menu(), parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    stats = get_user_stats(uid)

    if query.data == "main_menu":
        await query.message.edit_text(f"🕊️ **OWPC PROTOCOL**\n\nBalance: `{stats['total']:,} OWPC`", 
                                      reply_markup=main_menu(), parse_mode="Markdown")
    elif query.data == "stats":
        txt = f"📊 **ASSETS**\n\nGenesis: `{stats['g']}`\nUnity: `{stats['u']}`\nVeo AI: `{stats['v']:.2f}`"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")
    elif query.data == "passport":
        txt = f"🆔 **PASSPORT**\n\nHolder: `{query.from_user.first_name}`\nStatus: `VERIFIED ✅`"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")
    elif query.data == "invest":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
        ])
        await query.message.edit_text("💰 **INVEST HUB**", reply_markup=kb)

# --- WEB SERVER & STARTUP ---
@app.on_event("startup")
async def on_startup():
    # Initialisation du bot dans le cycle de vie de FastAPI
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_callbacks))
    
    await bot_app.initialize()
    await bot_app.start()
    # On lance le polling sans bloquer
    asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    print("✅ SYSTEM READY: WEB + BOT")

@app.get("/")
async def root():
    return {"status": "online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
