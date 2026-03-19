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

# --- DATABASE HELPER (Force values if missing) ---
def get_user_stats(uid):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
        res = c.fetchone()
        conn.close()
        if res:
            total = (res[0] or 0) + (res[1] or 0) + (res[2] or 0.0)
            return {"total": int(total), "g": res[0] or 0, "u": res[1] or 0, "v": res[2] or 0.0}
    except Exception as e:
        print(f"DB Error: {e}")
    # Default values to prevent button crash
    return {"total": 0, "g": 0, "u": 0, "v": 0.0}

# --- KEYBOARDS ---
def main_menu_kb(stats_total):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")]
    ])

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    
    # Ensure user exists in DB
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    conn.commit(); conn.close()
    
    stats = get_user_stats(uid)
    await update.message.reply_text(
        f"🕊️ **OWPC PROTOCOL**\n\nWelcome Commander **{name}**\nBalance: `{stats['total']:,} OWPC`",
        reply_markup=main_menu_kb(stats['total']), parse_mode="Markdown"
    )

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    stats = get_user_stats(uid)

    if query.data == "main_menu":
        await query.message.edit_text(
            f"🕊️ **OWPC PROTOCOL**\n\nBalance: `{stats['total']:,} OWPC`",
            reply_markup=main_menu_kb(stats['total']), parse_mode="Markdown"
        )

    elif query.data == "stats":
        # Structure de retour forcée pour éviter le blocage
        txt = (f"📊 **YOUR ASSETS**\n\n"
               f"🧬 Genesis: `{stats['g']:,}`\n"
               f"🌍 Unity: `{stats['u']:,}`\n"
               f"🤖 Veo AI: `{stats['v']:.2f}`\n\n"
               f"Total: `{stats['total']:,} OWPC`")
        await query.message.edit_text(txt, parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

    elif query.data == "passport":
        txt = (f"🆔 **OWPC PASSPORT**\n\n"
               f"Holder: `{query.from_user.first_name}`\n"
               f"ID: `{uid}`\n"
               f"Status: `VERIFIED ✅`\n"
               f"Clearance: `Level 1`")
        await query.message.edit_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

    elif query.data == "invest":
        invest_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
        ])
        await query.message.edit_text("💰 **INVEST HUB**", reply_markup=invest_kb)

# --- SYSTEM ---
@app.on_event("startup")
async def startup():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_callbacks))
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))

@app.get("/")
async def home(): return "🚀 TERMINAL ACTIVE"

if __name__ == "__main__":
    uvicorn.run("bot:app", host="0.0.0.0", port=PORT, factory=False)
