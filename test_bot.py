import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://veos-production.up.railway.app")

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# --- 🗄️ DATABASE (Gestion des 3 Tokens) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, 
                  points_unity REAL DEFAULT 0.0, 
                  points_veo REAL DEFAULT 0.0)''')
    conn.commit(); conn.close()

def get_balances(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    conn.close()
    return res if res else (0.0, 0.0, 0.0)

# --- 🤖 BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome {user.first_name} to the OWPC Ecosystem.", reply_markup=kb)

# --- 🌐 WEB APP (Affichage Triple Token) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui(request: Request):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body {{ background: #000; color: #fff; font-family: 'Segoe UI', sans-serif; text-align: center; margin: 0; padding: 20px; }}
            .card {{ background: #111; border: 1px solid #333; border-radius: 15px; padding: 15px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }}
            .token-name {{ font-weight: bold; color: #0f0; }}
            .token-val {{ font-family: monospace; font-size: 1.2em; }}
            .mine-btn {{ width: 100%; padding: 20px; border-radius: 10px; border: none; background: #0f0; color: #000; font-weight: bold; font-size: 1.1em; margin-top: 20px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <h2 style="color:#0f0">OWPC HUB</h2>
        
        <div class="card">
            <span class="token-name">🧬 GENESIS</span>
            <span class="token-val" id="bal_genesis">0.00</span>
        </div>
        <div class="card">
            <span class="token-name">⚙️ UNITY</span>
            <span class="token-val" id="bal_unity">0.00</span>
        </div>
        <div class="card">
            <span class="token-name">🤖 VEO AI</span>
            <span class="token-val" id="bal_veo">0.00</span>
        </div>

        <button class="mine-btn" onclick="mine('genesis')">EXTRACT GENESIS</button>
        <button class="mine-btn" style="background:#fff" onclick="mine('unity')">EXTRACT UNITY</button>
        <button class="mine-btn" style="background:#00bcd4" onclick="mine('veo')">EXTRACT VEO</button>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            
            // Fonction pour charger les soldes au démarrage
            async function loadData() {{
                const response = await fetch('/api/get_user/' + tg.initDataUnsafe.user.id);
                const data = await response.json();
                document.getElementById('bal_genesis').innerText = data.genesis.toFixed(2);
                document.getElementById('bal_unity').innerText = data.unity.toFixed(2);
                document.getElementById('bal_veo').innerText = data.veo.toFixed(2);
            }}

            async function mine(token) {{
                tg.HapticFeedback.impactOccurred('medium');
                await fetch('/api/mine', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{user_id: tg.initDataUnsafe.user.id, token: token}})
                }});
                let el = document.getElementById('bal_' + token);
                el.innerText = (parseFloat(el.innerText) + 0.05).toFixed(2);
            }}
            loadData();
        </script>
    </body></html>
    """

@app.get("/api/get_user/{{uid}}")
async def api_get_user(uid: int):
    b = get_balances(uid)
    return {{"genesis": b[0], "unity": b[1], "veo": b[2]}}

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    uid, token = data.get("user_id"), data.get("token")
    if uid:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        col = "points_genesis" if token == "genesis" else "points_unity" if token == "unity" else "points_veo"
        c.execute(f"UPDATE users SET {col} = {col} + 0.05 WHERE user_id = ?", (uid,))
        conn.commit(); conn.close()
    return {{"ok": True}}

async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
