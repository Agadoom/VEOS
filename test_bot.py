import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, PreCheckoutQueryHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURATION DU STOCKAGE PERMANENT ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = "OWPCsbot"

# C'est ici que la magie opère : on utilise le volume Railway
DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_PATH = os.path.join(DATA_DIR, "owpc_data.db")
logging.info(f"💾 Base de données connectée sur : {DB_PATH}")

app = FastAPI()

# --- 🗄️ DATABASE (Initialisation dans le Volume) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0, points_unity REAL DEFAULT 0, 
                  points_veo REAL DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

# --- 🤖 BOT LOGIC (Inchangé mais sécurisé) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (uid, name, ref_id))
        if ref_id and ref_id != uid:
            c.execute("UPDATE users SET points_unity = points_unity + 5.0, ref_count = ref_count + 1 WHERE user_id = ?", (ref_id,))
    conn.commit(); conn.close()

    if context.args and "boost" in context.args[0]:
        token = context.args[0].split('_')[1]
        await update.message.reply_invoice(
            title=f"🚀 BOOST {token.upper()}", description="Extra tokens!",
            payload=f"boost_{token}", provider_token="", currency="XTR",
            prices=[LabeledPrice("Boost", 50)])
        return

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Terminal OWPC v1.5 Online.", reply_markup=kb)

# --- 🌐 WEB APP (L'interface qui affiche tes tokens) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <html>
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {{ background: #000; color: #fff; font-family: monospace; text-align: center; padding: 20px; }}
        .card {{ background: #111; border: 1px solid #0f0; border-radius: 10px; padding: 15px; margin-bottom: 10px; display:flex; justify-content:space-between; }}
        .btn {{ width: 100%; padding: 15px; border-radius: 8px; border: none; font-weight: bold; cursor: pointer; margin-bottom: 10px; }}
    </style>
    </head>
    <body>
        <h2 style="color:#0f0">OWPC TERMINAL</h2>
        <div class="card"><span>GENESIS</span><span id="g">0.00</span></div>
        <button class="btn" style="background:#0f0" onclick="mine('genesis')">MINE GENESIS</button>
        
        <div class="card"><span>UNITY</span><span id="u">0.00</span></div>
        <button class="btn" style="background:#fff" onclick="mine('unity')">MINE UNITY</button>

        <div class="card"><span>VEO AI</span><span id="v">0.00</span></div>
        <button class="btn" style="background:#00bcd4" onclick="mine('veo')">MINE VEO</button>

        <script>
            let tg = window.Telegram.WebApp;
            async function load() {{
                const r = await fetch('/api/user/' + tg.initDataUnsafe.user.id);
                const d = await r.json();
                document.getElementById('g').innerText = d.g.toFixed(2);
                document.getElementById('u').innerText = d.u.toFixed(2);
                document.getElementById('v').innerText = d.v.toFixed(2);
            }}
            async function mine(t) {{
                await fetch('/api/mine', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{user_id: tg.initDataUnsafe.user.id, token: t}})
                }});
                load();
            }}
            load();
        </script>
    </body></html>
    """

# --- 🛰️ API ---
@app.get("/api/user/{{uid}}")
async def get_user_api(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return {{"g": r[0], "u": r[1], "v": r[2]}} if r else {{"g":0,"u":0,"v":0}}

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET points_{{t}} = points_{{t}} + ? WHERE user_id = ?", (gain, uid))
    conn.commit(); conn.close()
    return {{"ok": True}}

# --- START ---
async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
