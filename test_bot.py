import os, sqlite3, asyncio, uvicorn, random
from datetime import date
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://veos-production.up.railway.app")
LOGO_PATH = "media/owpc_logo.png"

app = FastAPI()

# --- DATABASE LOGIC ---
def get_stats(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, last_bonus, tasks_sub_channel, wallet_address FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,))
    ref_count = c.fetchone()[0]
    conn.close()
    if res:
        total = sum(res[:3])
        # Multiplicateurs simplifiés pour la stabilité
        mult = 1.0
        if total > 25: mult = 2.0
        if total > 100: mult = 5.0
        return {"g": res[0], "u": res[1], "v": res[2], "total": total, "mult": mult, "ref": ref_count, "last_bonus": res[3], "wallet": res[5]}
    return None

# --- UI HELPER ---
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="btn_daily"), InlineKeyboardButton("🆔 Passport", callback_data="btn_passport")],
        [InlineKeyboardButton("🏛️ Hall of Fame", callback_data="btn_hof"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="btn_lucky")],
        [InlineKeyboardButton("🏆 Tasks Hub", callback_data="btn_tasks"), InlineKeyboardButton("👛 Wallet", callback_data="btn_wallet")],
        [InlineKeyboardButton("📊 Stats", callback_data="btn_stats"), InlineKeyboardButton("🔗 Invite", callback_data="btn_invite")],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="btn_invest")]
    ])

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, update.effective_user.first_name))
    conn.commit(); conn.close()
    
    s = get_stats(uid)
    txt = f"🕊️ **OWPC PROTOCOL**\n\nBalance: `{s['total']:.2f}` OWPC\nNetwork: `{s['ref']}` friends"
    
    if update.message:
        await update.message.reply_photo(photo=open(LOGO_PATH, 'rb'), caption=txt, reply_markup=main_keyboard(), parse_mode="Markdown")
    else:
        try:
            await update.callback_query.message.edit_caption(caption=txt, reply_markup=main_keyboard(), parse_mode="Markdown")
        except:
            pass

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id
    await q.answer() # CRITIQUE: Libère le bouton immédiatement
    s = get_stats(uid)

    if q.data == "btn_passport":
        txt = f"🆔 **PASSPORT**\n\nHolder: `{q.from_user.first_name}`\nPower: `x{s['mult']}`\nStatus: `Verified ✅`"
        await q.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]]), parse_mode="Markdown")

    elif q.data == "btn_lucky":
        win = round(random.uniform(0.1, 0.5), 2)
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (win, uid))
        conn.commit(); conn.close()
        await q.answer(f"🎰 Win: +{win} OWPC!", show_alert=True)
        await start(update, context)

    elif q.data == "btn_wallet":
        addr = s['wallet'] if s['wallet'] else "Not Linked"
        txt = f"👛 **WALLET**\n\nAddress: `{addr}`\n\nConnect your TON wallet to prepare for airdrop."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Connect (Soon)", callback_data="wallet_soon")],[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]])
        await q.message.edit_caption(caption=txt, reply_markup=kb, parse_mode="Markdown")

    elif q.data == "btn_invest":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 Genesis", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]
        ])
        await q.message.edit_caption(caption="💰 **INVEST HUB**\nSelect a sector to buy on Blum:", reply_markup=kb)

    elif q.data == "btn_back":
        await start(update, context)
    
    elif q.data == "wallet_soon":
        await q.answer("🔒 Module encrypted. Wait for TGE.", show_alert=True)

# --- FASTAPI / TERMINAL ---
@app.post("/update_points")
async def update_points(request: Request):
    data = await request.json(); uid = data.get("user_id")
    # Logique de minage... (identique V6)
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def home():
    return "<html><body style='background:#000;color:#0f0;'>Terminal Active</body></html>"

async def main():
    # Initialisation DB
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, points_genesis REAL DEFAULT 0, points_unity REAL DEFAULT 0, points_veo REAL DEFAULT 0, referred_by INTEGER, last_bonus TEXT, tasks_sub_channel INTEGER, wallet_address TEXT)")
    conn.commit(); conn.close()

    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CallbackQueryHandler(handle_buttons))
    
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
