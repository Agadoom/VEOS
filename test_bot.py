import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
# L'URL de ton application sur Railway
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://veos-production.up.railway.app")

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# --- 🗄️ BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, referred_by INTEGER)''')
    conn.commit()
    conn.close()
    logging.info("✅ Base de données initialisée.")

# --- 🤖 LOGIQUE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Enregistrement silencieux
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()

    # Bouton qui ouvre la Mini App
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 OPEN OWPC TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])

    await update.message.reply_text(
        f"Welcome to OWPC, {user.first_name}.\nClick below to start mining.",
        reply_markup=kb
    )

# --- 🌐 INTERFACE MINI APP (HTML/JS) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body {{ background: #000; color: #0f0; font-family: sans-serif; text-align: center; display: flex; flex-direction: column; justify-content: center; height: 100vh; margin: 0; }}
            .btn {{ width: 200px; height: 200px; border-radius: 50%; border: 4px solid #0f0; background: transparent; color: #0f0; font-size: 1.5em; font-weight: bold; box-shadow: 0 0 15px #0f0; cursor: pointer; }}
            .btn:active {{ transform: scale(0.95); opacity: 0.8; }}
        </style>
    </head>
    <body>
        <button class="btn" onclick="mine()">EXTRACT</button>
        <p id="status">> SYSTEM READY</p>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            function mine() {{
                tg.HapticFeedback.impactOccurred('medium');
                fetch('/api/mine', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{user_id: tg.initDataUnsafe.user.id}})
                }});
                document.getElementById('status').innerText = "> EXTRACTING...";
                setTimeout(() => {{ document.getElementById('status').innerText = "> SUCCESS +0.05"; }}, 300);
            }}
        </script>
    </body>
    </html>
    """

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    if uid:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE users SET points_genesis = points_genesis + 0.05 WHERE user_id = ?", (uid,))
        conn.commit(); conn.close()
    return {"status": "ok"}

# --- 🛠️ LANCEMENT ---
async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    
    await bot.initialize()
    await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    
    # Serveur Web
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
