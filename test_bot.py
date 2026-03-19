import os, sqlite3, asyncio, uvicorn, random, logging
from datetime import date, datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ⚙️ CONFIG (Vérifie bien ces variables sur Railway !) ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
# IMPORTANT: WEBAPP_URL doit être ton URL Railway (ex: https://ton-projet.up.railway.app)
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://veos-production.up.railway.app")
LOGO_PATH = "media/owpc_logo.png"
BOT_USERNAME = "OWPCsbot"

app = FastAPI()

# --- 🗄️ DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, points_unity REAL DEFAULT 0.0, 
                  points_veo REAL DEFAULT 0.0, referred_by INTEGER,
                  last_bonus TEXT DEFAULT '', tasks_sub_channel INTEGER DEFAULT 0,
                  wallet_address TEXT DEFAULT '', streak INTEGER DEFAULT 0, 
                  last_lucky TEXT DEFAULT '')''')
    conn.commit(); conn.close()

def get_stats(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, last_bonus, tasks_sub_channel, wallet_address, streak, last_lucky FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,))
    lv1 = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by IN (SELECT user_id FROM users WHERE referred_by=?)", (uid,))
    lv2 = c.fetchone()[0]
    conn.close()
    if res:
        total = sum(res[:3])
        mult = 2.5 if total > 50 else 1.0
        return {"g":res[0],"u":res[1],"v":res[2],"total":total,"mult":mult,"last_bonus":res[3],"wallet":res[5],"streak":res[6],"last_lucky":res[7],"lv1":lv1,"lv2":lv2}
    return None

# --- 🤖 BOT HANDLERS ---
async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    
    # Parrainage
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (user.id, user.first_name, ref_id))
    conn.commit(); conn.close()
    
    s = get_stats(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="btn_daily"), InlineKeyboardButton("🆔 Passport", callback_data="btn_passport")],
        [InlineKeyboardButton("🎰 Lucky Draw", callback_data="btn_lucky"), InlineKeyboardButton("🏆 Tasks Hub", callback_data="btn_tasks")],
        [InlineKeyboardButton("📊 My Network", callback_data="btn_stats"), InlineKeyboardButton("👛 Wallet", callback_data="btn_wallet")],
        [InlineKeyboardButton("🔗 Invite", callback_data="btn_invite"), InlineKeyboardButton("💰 Invest", callback_data="btn_invest")]
    ])
    
    txt = f"🕊️ **OWPC PROTOCOL**\n\nBalance: `{s['total']:.2f}` OWPC\nNetwork: `{s['lv1'] + s['lv2']}` members\n🔥 Streak: `{s['streak']}d`"
    
    if update.callback_query:
        await update.callback_query.message.edit_caption(caption=txt, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_photo(photo=open(LOGO_PATH, 'rb'), caption=txt, reply_markup=kb, parse_mode="Markdown")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id
    s = get_stats(uid)

    if q.data == "btn_back":
        await start_menu(update, context)

    elif q.data == "btn_passport":
        progress = min(int((s['total'] / 100) * 10), 10)
        bar = "🟩" * progress + "⬜" * (10 - progress)
        txt = f"🆔 **PASSPORT**\n\nRank: `EXTRACTOR`\nPower: `x{s['mult']}`\n\nXP Progress:\n{bar}"
        await q.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]]), parse_mode="Markdown")

    elif q.data == "btn_lucky":
        now = datetime.now()
        if s['last_lucky'] and now < datetime.fromisoformat(s['last_lucky']) + timedelta(hours=6):
            await q.answer("⏳ Recharge en cours (6h)...", show_alert=True)
        else:
            win = round(random.uniform(0.1, 0.4), 2)
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE users SET points_veo = points_veo + ?, last_lucky = ? WHERE user_id = ?", (win, now.isoformat(), uid))
            conn.commit(); conn.close()
            await q.answer(f"🎰 GAGNÉ : +{win} VEO AI!", show_alert=True)
            await start_menu(update, context)

    elif q.data == "btn_wallet":
        txt = f"👛 **WALLET**\n\nAddress: `None`\n\nConnect your TON wallet for withdrawals."
        await q.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Link Wallet", callback_data="soon")],[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]]), parse_mode="Markdown")

    elif q.data == "btn_stats":
        txt = f"📊 **NETWORK**\n\nL1: `{s['lv1']}` (10%)\nL2: `{s['lv2']}` (3%)"
        await q.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]]), parse_mode="Markdown")

    elif q.data == "btn_invest":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧬 Genesis", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]])
        await q.message.edit_caption(caption="💰 **INVEST HUB**", reply_markup=kb)

    elif q.data == "soon":
        await q.answer("🔒 Available after TGE", show_alert=True)

# --- 🌐 WEB APP (FIX ERROR) ---
@app.get("/", response_class=HTMLResponse)
async def terminal_page():
    return """
    <html>
    <head><title>OWPC Terminal</title><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="background:#000; color:#0f0; font-family:monospace; text-align:center; padding-top:50px;">
        <h2>OWPC TERMINAL ACTIVE</h2>
        <div id="status">Ready to mine</div>
        <button onclick="mine()" style="background:#0f0; color:#000; padding:20px; border:none; border-radius:10px; font-weight:bold; margin-top:20px;">EXTRACT GENESIS</button>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            function mine() {
                let uid = tg.initDataUnsafe.user.id;
                fetch('/update_points', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: uid, token: 'genesis'})
                }).then(() => { alert('Extracted!'); });
            }
        </script>
    </body></html>
    """

@app.post("/update_points")
async def receive_points(request: Request):
    data = await request.json(); uid, token = data.get("user_id"), data.get("token")
    if uid:
        s = get_stats(uid); gain = 0.05 * s['mult']
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute(f"UPDATE users SET points_{token} = points_{token} + ? WHERE user_id = ?", (gain, uid))
        conn.commit(); conn.close()
        return {"status": "ok"}

async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start_menu)); bot.add_handler(CallbackQueryHandler(handle_buttons))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
