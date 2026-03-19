import os, sqlite3, asyncio, uvicorn, random, logging
from datetime import date, datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- LOGS ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://veos-production.up.railway.app")
LOGO_PATH = "media/owpc_logo.png"

app = FastAPI()

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, points_unity REAL DEFAULT 0.0, 
                  points_veo REAL DEFAULT 0.0, referred_by INTEGER,
                  last_bonus TEXT DEFAULT '', last_lucky TEXT DEFAULT '', 
                  streak INTEGER DEFAULT 0, wallet_address TEXT DEFAULT '')''')
    conn.commit(); conn.close()

def get_stats(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, streak, last_lucky, referred_by FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,))
    lv1 = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by IN (SELECT user_id FROM users WHERE referred_by=?)", (uid,))
    lv2 = c.fetchone()[0]
    conn.close()
    if res:
        total = sum(res[:3])
        return {"total": total, "streak": res[3], "last_lucky": res[4], "lv1": lv1, "lv2": lv2, "mult": (2.0 if total > 100 else 1.0)}
    return None

# --- BOT INTERFACE ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (user.id, user.first_name, ref_id))
    conn.commit(); conn.close()
    
    s = get_stats(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("🆔 Passport", callback_data="btn_passport"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="btn_lucky")],
        [InlineKeyboardButton("📊 Network", callback_data="btn_stats"), InlineKeyboardButton("👛 Wallet", callback_data="btn_wallet")],
        [InlineKeyboardButton("🔗 Invite", callback_data="btn_invite"), InlineKeyboardButton("💰 Invest", callback_data="btn_invest")]
    ])
    
    txt = f"🕊️ **OWPC PROTOCOL**\n\nBalance: `{s['total']:.2f}` OWPC\nStreak: `{s['streak']}j` | Power: `x{s['mult']}`"
    if update.callback_query: await update.callback_query.message.edit_caption(caption=txt, reply_markup=kb, parse_mode="Markdown")
    else: await update.message.reply_photo(photo=open(LOGO_PATH, 'rb'), caption=txt, reply_markup=kb, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id
    s = get_stats(uid)

    if q.data == "btn_passport":
        txt = f"🆔 **PASSPORT**\n\nUser: `{q.from_user.first_name}`\nStatus: `Active`"
        await q.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back")]]), parse_mode="Markdown")
    
    elif q.data == "btn_lucky":
        now = datetime.now()
        if s['last_lucky'] and now < datetime.fromisoformat(s['last_lucky']) + timedelta(hours=6):
            await q.answer("⏳ Recharge en cours (6h)", show_alert=True)
        else:
            win = round(random.uniform(0.1, 0.5), 2)
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE users SET points_veo = points_veo + ?, last_lucky = ? WHERE user_id = ?", (win, now.isoformat(), uid))
            conn.commit(); conn.close()
            await q.answer(f"🎰 +{win} VEO!", show_alert=True); await start(update, context)

    elif q.data == "btn_stats":
        txt = f"📊 **NETWORK**\n\nDirect (L1): `{s['lv1']}`\nIndirect (L2): `{s['lv2']}`"
        await q.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back")]]), parse_mode="Markdown")

    elif q.data == "back": await start(update, context)

# --- WEB TERMINAL (HTML/JS) ---
@app.get("/", response_class=HTMLResponse)
async def web_index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { background: #000; color: #0f0; font-family: 'Courier New', monospace; text-align: center; }
            .btn { background: #0f0; color: #000; padding: 15px 30px; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }
            #console { border: 1px solid #0f0; height: 150px; overflow-y: auto; margin: 20px; padding: 10px; font-size: 12px; text-align: left; }
        </style>
    </head>
    <body>
        <h2>OWPC TERMINAL v1.0</h2>
        <div id="console"> > System ready...<br> > Waiting for extraction command...</div>
        <button class="btn" onclick="mine()">START EXTRACTION</button>
        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            function mine() {
                let log = document.getElementById('console');
                log.innerHTML += "<br> > Requesting blocks...";
                fetch('/update_points', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: tg.initDataUnsafe.user.id, token: 'genesis'})
                }).then(r => r.json()).then(d => {
                    log.innerHTML += "<br> > <span style='color:white'>Success! +0.05 Genesis</span>";
                });
            }
        </script>
    </body></html>
    """

@app.post("/update_points")
async def api_points(request: Request):
    data = await request.json(); uid = data.get("user_id")
    if uid:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE users SET points_genesis = points_genesis + 0.05 WHERE user_id = ?", (uid,))
        conn.commit(); conn.close()
        return {"status": "ok"}

# --- SERVER ---
async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start)); bot.add_handler(CallbackQueryHandler(button_handler))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
