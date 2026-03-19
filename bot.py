import os, sqlite3, asyncio, uvicorn
from fastapi import FastAPI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEB_URL = "https://veos-production.up.railway.app"

app = FastAPI()

# --- DB ---
def get_stats(uid):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
        res = c.fetchone(); conn.close()
        if res: return {"total": int((res[0] or 0)+(res[1] or 0)+(res[2] or 0)), "g": res[0] or 0, "u": res[1] or 0, "v": res[2] or 0.0}
    except: pass
    return {"total": 0, "g": 0, "u": 0, "v": 0.0}

# --- KEYBOARDS ---
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEB_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")]
    ])

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    s = get_stats(user.id)
    msg = f"🕊️ **OWPC PROTOCOL**\n\n👤 **Commander:** {user.first_name}\n💰 **Balance:** {s['total']:,} OWPC"
    target = update.message if update.message else update.callback_query.message
    await target.reply_text(msg, reply_markup=main_kb(), parse_mode="Markdown")

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id; s = get_stats(uid)
    if q.data == "main_menu": await start(update, context)
    elif q.data == "stats":
        await q.message.edit_text(f"📊 **ASSETS**\n\nGen: {s['g']}\nUni: {s['u']}\nVeo: {s['v']:.2f}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")
    elif q.data == "passport":
        await q.message.edit_text(f"🆔 **PASSPORT**\n\nHolder: {q.from_user.first_name}\nStatus: VERIFIED ✅", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")
    elif q.data == "invest":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],[InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],[InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]])
        await q.message.edit_text("💰 **INVEST HUB**", reply_markup=kb)
    elif q.data in ["hof", "lucky", "invite"]:
        await q.message.edit_text(f"🚧 {q.data.upper()} in progress...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

# --- ENGINE ---
@app.get("/")
async def root(): return {"status": "ok"}

async def run_bot():
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start)); bot.add_handler(CallbackQueryHandler(cb_handler))
    await bot.initialize(); await bot.start()
    await bot.updater.start_polling(drop_pending_updates=True)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot()) # Lance le bot en tâche de fond
    uvicorn.run(app, host="0.0.0.0", port=PORT) # Lance le web
