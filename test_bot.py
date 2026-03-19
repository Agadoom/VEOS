import os, sqlite3, asyncio, uvicorn, random, logging
from datetime import date, datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- LOGGING POUR RAILWAY ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ⚙️ CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://veos-production.up.railway.app")
LOGO_PATH = "media/owpc_logo.png"
BOT_USERNAME = "OWPCsbot"

app = FastAPI()

# --- 🗄️ DATABASE REPAIR & INIT ---
def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, points_unity REAL DEFAULT 0.0, 
                  points_veo REAL DEFAULT 0.0, referred_by INTEGER,
                  last_bonus TEXT DEFAULT '', tasks_sub_channel INTEGER DEFAULT 0,
                  wallet_address TEXT DEFAULT '', streak INTEGER DEFAULT 0, 
                  last_lucky TEXT DEFAULT '')''')
    
    # Sécurité migrations
    columns = [col[1] for col in c.execute("PRAGMA table_info(users)").fetchall()]
    if 'streak' not in columns: c.execute("ALTER TABLE users ADD COLUMN streak INTEGER DEFAULT 0")
    if 'last_lucky' not in columns: c.execute("ALTER TABLE users ADD COLUMN last_lucky TEXT DEFAULT ''")
    
    conn.commit()
    conn.close()
    logger.info("✅ Database Initialized")

# --- 📊 LOGIQUE STATS (Identique V9) ---
def get_stats(uid):
    try:
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
            mult = 1.0
            if total > 50: mult = 2.5
            if total > 250: mult = 5.0
            return {"g":res[0],"u":res[1],"v":res[2],"total":total,"mult":mult,"last_bonus":res[3],"wallet":res[5],"streak":res[6],"last_lucky":res[7],"lv1":lv1,"lv2":lv2}
    except Exception as e:
        logger.error(f"DB Error: {e}")
    return None

# --- 🤖 BOT HANDLERS ---
async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
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
    
    txt = f"🕊️ **OWPC PROTOCOL V9.1**\n\nBalance: `{s['total']:.2f}` OWPC\nNetwork: `{s['lv1'] + s['lv2']}` members\n🔥 Streak: `{s['streak']}d`"
    
    if update.callback_query:
        await update.callback_query.message.edit_caption(caption=txt, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_photo(photo=open(LOGO_PATH, 'rb'), caption=txt, reply_markup=kb, parse_mode="Markdown")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id
    s = get_stats(uid)

    if q.data == "btn_lucky":
        now = datetime.now()
        if s['last_lucky'] and now < datetime.fromisoformat(s['last_lucky']) + timedelta(hours=6):
            await q.answer("⏳ Recharge en cours (6h)...", show_alert=True)
        else:
            win = round(random.uniform(0.1, 0.3), 2)
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE users SET points_veo = points_veo + ?, last_lucky = ? WHERE user_id = ?", (win, now.isoformat(), uid))
            conn.commit(); conn.close()
            await q.answer(f"🎰 +{win} VEO AI !", show_alert=True)
            await start_menu(update, context)

    elif q.data == "btn_stats":
        txt = f"📊 **NETWORK**\n\nL1: `{s['lv1']}` (10%)\nL2: `{s['lv2']}` (3%)\n\nTotal earnings optimized."
        await q.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]]), parse_mode="Markdown")

    elif q.data == "btn_back":
        await start_menu(update, context)

# --- 🌐 WEB APP API ---
@app.post("/update_points")
async def receive_points(request: Request):
    data = await request.json(); uid, token = data.get("user_id"), data.get("token")
    if uid and token:
        s = get_stats(uid); gain = 0.05 * s['mult']
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute(f"UPDATE users SET points_{token} = points_{token} + ? WHERE user_id = ?", (gain, uid))
        # Commission L1 (10%)
        c.execute("SELECT referred_by FROM users WHERE user_id = ?", (uid,))
        l1 = c.fetchone()
        if l1 and l1[0]:
            c.execute(f"UPDATE users SET points_{token} = points_{token} + ? WHERE user_id = ?", (gain*0.1, l1[0]))
            # Commission L2 (3%)
            c.execute("SELECT referred_by FROM users WHERE user_id = ?", (l1[0],))
            l2 = c.fetchone()
            if l2 and l2[0]:
                c.execute(f"UPDATE users SET points_{token} = points_{token} + ? WHERE user_id = ?", (gain*0.03, l2[0]))
        conn.commit(); conn.close()
        return {"status": "success"}

@app.get("/")
async def home(): return {"status": "Terminal V9.1 Online"}

# --- MAIN ---
async def main():
    logger.info("🚀 OWPC SYSTEM BOOTING...")
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start_menu))
    bot.add_handler(CallbackQueryHandler(handle_buttons))
    
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    logger.info("✅ TELEGRAM POLLING STARTED")
    
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
