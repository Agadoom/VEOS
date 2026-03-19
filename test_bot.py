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

# --- 🗄️ DATABASE (FORCE CREATION) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    logger.info("Checking database tables...")
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, points_unity REAL DEFAULT 0.0, 
                  points_veo REAL DEFAULT 0.0, referred_by INTEGER,
                  last_bonus TEXT DEFAULT '', streak INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()
    logger.info("✅ Database Ready")

def get_user_data(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, streak FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    conn.close()
    return res if res else (0.0, 0.0, 0.0, 0)

# --- 🤖 BOT HANDLERS (STEALTH MODE) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    # 1. Traitement silencieux du parrainage
    ref_id = None
    if context.args:
        try:
            ref_id = int(context.args[0])
            if ref_id != uid:
                conn = sqlite3.connect(DB_PATH); c = conn.cursor()
                c.execute("INSERT OR IGNORE INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (uid, user.first_name, ref_id))
                conn.commit(); conn.close()
        except: pass

    # 2. Garantir que l'user existe
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, user.first_name))
    conn.commit(); conn.close()

    # 3. UI Épurée
    s = get_user_data(uid)
    bal = sum(s[:3])
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📊 My Stats", callback_data="st_stats"), InlineKeyboardButton("🔗 Invite", callback_data="st_ref")]
    ])
    
    await update.message.reply_photo(
        photo=open(LOGO_PATH, 'rb'), 
        caption=f"🕊️ **OWPC PROTOCOL**\n\nWelcome `{user.first_name}`\nBalance: `{bal:.2f}` OWPC", 
        reply_markup=kb, 
        parse_mode="Markdown"
    )

# --- 🌐 WEB APP API (STEALTH BACKEND) ---
@app.post("/api/sync")
async def sync_data(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    
    if uid:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        # On ajoute les points au mineur
        c.execute("UPDATE users SET points_genesis = points_genesis + 0.05 WHERE user_id = ?", (uid,))
        
        # Commission invisible L1 (10%)
        c.execute("SELECT referred_by FROM users WHERE user_id = ?", (uid,))
        ref = c.fetchone()
        if ref and ref[0]:
            c.execute("UPDATE users SET points_genesis = points_genesis + 0.005 WHERE user_id = ?", (ref[0],))
            
        conn.commit(); conn.close()
        return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return """
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="background:#000; color:#0f0; font-family:monospace; text-align:center; padding-top:20vh;">
        <h1>OWPC TERMINAL</h1>
        <div id="val" style="font-size:3em; margin:20px;">Mining...</div>
        <button onclick="mine()" style="padding:20px; background:#0f0; border:none; border-radius:10px; font-weight:bold;">EXTRACT BLOCK</button>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <script>
            let tg = window.Telegram.WebApp;
            function mine() {
                fetch('/api/sync', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: tg.initDataUnsafe.user.id})
                }).then(() => { document.getElementById('val').innerText = "SUCCESS"; setTimeout(()=> {document.getElementById('val').innerText = "Mining..."}, 1000); });
            }
        </script>
    </body></html>
    """

# --- STARTUP SEQUENCE ---
async def main():
    init_db() # ON FORCE LA CRÉATION ICI
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    
    await bot.initialize()
    await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    
    logger.info("Starting Web Server...")
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    await uvicorn.Server(config).serve()

if __name__ == "__main__":
    asyncio.run(main())
