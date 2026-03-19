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

# --- DATABASE ENGINE ---
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

# --- MENU COMPLET (PHOTO 1) ---
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")]
    ])

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    # Init User in DB
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, user.first_name))
    conn.commit(); conn.close()
    
    stats = get_user_stats(uid)
    
    welcome_msg = (
        f"🕊️ **OWPC PROTOCOL**\n\n"
        f"👤 **Commander:** {user.first_name}\n"
        f"🏆 **Rank:** SEEKER\n"
        f"💰 **Balance:** {stats['total']:,} OWPC\n\n"
        f"System Status: `OPERATIONAL` ✅"
    )
    
    # On gère si c'est un nouveau message ou un callback (retour au menu)
    if update.message:
        await update.message.reply_text(welcome_msg, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    else:
        await update.callback_query.message.edit_text(welcome_msg, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    stats = get_user_stats(uid)

    # Navigation : Retour au menu
    if query.data == "main_menu":
        await start(update, context)

    # Navigation : Stats
    elif query.data == "stats":
        txt = (f"📊 **ASSETS OVERVIEW**\n\n"
               f"🧬 Genesis: `{stats['g']:,}`\n"
               f"🌍 Unity: `{stats['u']:,}`\n"
               f"🤖 Veo AI: `{stats['v']:.2f}`\n\n"
               f"Total: `{stats['total']:,} OWPC`")
        await query.message.edit_text(txt, parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

    # Navigation : Passport
    elif query.data == "passport":
        txt = (f"🆔 **OWPC PASSPORT**\n\nHolder: `{query.from_user.first_name}`\n"
               f"ID: `{uid}`\nStatus: `VERIFIED ✅`")
        await query.message.edit_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

    # Navigation : Invest Hub (Liens opérationnels)
    elif query.data == "invest":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
        ])
        await query.message.edit_text("💰 **INVEST HUB**\nSelect an asset to acquire:", reply_markup=kb)
    
    # Autres sections (Placeholder)
    elif query.data in ["hof", "lucky", "invite"]:
        await query.message.edit_text(f"🚧 Sector **{query.data.upper()}** is under maintenance.", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

# --- ENGINE ---
@app.get("/")
async def home(): return {"status": "terminal_online"}

async def run_main():
    # Setup Bot
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_callbacks))
    
    await bot_app.initialize()
    await bot_app.start()
    # Nettoyage et lancement
    asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    
    # Setup Web Server
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(run_main())
