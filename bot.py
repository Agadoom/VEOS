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

# --- THE FULL MENU (As seen in your original photo) ---
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")]
    ])

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stats = get_user_stats(user.id)
    
    # Save user
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()

    msg = (f"🕊️ **OWPC PROTOCOL**\n\n"
           f"👤 **Commander:** {user.first_name}\n"
           f"🏆 **Rank:** SEEKER\n"
           f"💰 **Balance:** {stats['total']:,} OWPC\n\n"
           f"System Status: `OPERATIONAL` ✅")
    
    await update.message.reply_text(msg, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    stats = get_user_stats(uid)

    # Re-display Main Menu
    if query.data == "main_menu":
        msg = f"🕊️ **OWPC PROTOCOL**\n\nBalance: `{stats['total']:,} OWPC`"
        await query.message.edit_text(msg, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

    # Stats logic
    elif query.data == "stats":
        txt = (f"📊 **ASSETS OVERVIEW**\n\n"
               f"🧬 Genesis: `{stats['g']:,}`\n"
               f"🌍 Unity: `{stats['u']:,}`\n"
               f"🤖 Veo AI: `{stats['v']:.2f}`")
        await query.message.edit_text(txt, parse_mode="Markdown", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

    # Passport logic
    elif query.data == "passport":
        txt = (f"🆔 **OWPC PASSPORT**\n\n"
               f"Holder: `{query.from_user.first_name}`\n"
               f"Status: `VERIFIED ✅`\n"
               f"Network: `OWPC Mainnet`")
        await query.message.edit_text(txt, parse_mode="Markdown", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

    # Invest Hub logic (Fixing the missing links)
    elif query.data == "invest":
        invest_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
        ])
        await query.message.edit_text("💰 **INVEST HUB**\nSelect your target:", reply_markup=invest_kb)

# --- RUNNER ---
@app.get("/")
async def home(): return "🚀 TERMINAL ACTIVE"

if __name__ == "__main__":
    # Check if we are running the BOT or the WEB
    # If the TOKEN is here, we run the bot polling
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_callbacks))
    
    print("🤖 STARTING BOT...")
    bot_app.run_polling(drop_pending_updates=True)
