import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app" # Votre URL Railway

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# --- DB INIT ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                    (user_id INTEGER PRIMARY KEY, name TEXT, points_genesis REAL DEFAULT 0.0)''')
    conn.commit()
    conn.close()

# --- BOT HANDLER ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # On initialise l'utilisateur en silence
    user = update.effective_user
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit()
    conn.close()

    # On prépare le bouton spécial "Persistent" en bas à gauche
    # Note: BotFather gère le bouton permanent, mais on peut aussi envoyer un bouton de clavier WebApp
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 ENTER TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])

    await update.message.reply_text(
        f"Welcome to OWPC Protocol, {user.first_name}.\nPress the button below or the icon in the menu to start.",
        reply_markup=kb
    )

# --- WEB APP INTERFACE ---
@app.get("/", response_class=HTMLResponse)
async def web_index():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body {{ background: #000; color: #0f0; font-family: monospace; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .hex-btn {{ width: 150px; height: 150px; background: #0f0; color: #000; border: none; border-radius: 50%; font-weight: bold; font-size: 1.2em; cursor: pointer; box-shadow: 0 0 20px #0f0; }}
            .status {{ margin-top: 20px; font-size: 0.8em; opacity: 0.7; }}
        </style>
    </head>
    <body>
        <button class="hex-btn" onclick="mine()">EXTRACT</button>
        <div class="status" id="stat">> IDLE</div>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            tg.ready();
            function mine() {{
                tg.HapticFeedback.impactOccurred('heavy');
                document.getElementById('stat').innerText = "> EXTRACTING...";
                fetch('/api/mine', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{user_id: tg.initDataUnsafe.user.id}})
                }}).then(() => {{
                    setTimeout(() => {{ document.getElementById('stat').innerText = "> SUCCESS +0.05"; }}, 500);
                }});
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
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE users SET points_genesis = points_genesis + 0.05 WHERE user_id = ?", (uid,))
        conn.commit()
        conn.close()
    return {"ok": True}

# --- MAIN ---
async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    await bot.initialize()
    await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
