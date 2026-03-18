import os
import asyncio
import sqlite3
import nest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

nest_asyncio.apply()

# --- CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.environ.get("PORT", 8080))
WEBAPP_URL = "https://veos-production.up.railway.app"
DB_NAME = "owpc_data.db"

app = FastAPI()

# --- 📊 FONCTION BASE DE DONNÉES ---
def get_user_data(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # On récupère points et rank
        cursor.execute("SELECT points, rank FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return {"points": result[0], "rank": result[1]}
    except Exception as e:
        print(f"Erreur DB: {e}")
    return {"points": 0, "rank": "NEWBIE"}

# --- 🔌 ROUTE API (C'est elle qui donne les infos à la Mini App) ---
@app.get("/api/user/{user_id}")
async def api_get_user(user_id: int):
    data = get_user_data(user_id)
    return JSONResponse(content=data)

# --- 🌐 INTERFACE MINI APP ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {{ --gold: #d4af37; --bg: #0a0a12; }}
            body {{ background-color: var(--bg); color: white; margin: 0; padding: 20px; font-family: sans-serif; text-align: center; }}
            .card {{
                background: linear-gradient(145deg, #161626, #1f1f35);
                border: 1px solid rgba(212, 175, 55, 0.3);
                border-radius: 25px; padding: 30px 20px; margin-top: 40px;
            }}
            .balance-label {{ font-size: 12px; color: var(--gold); text-transform: uppercase; margin-top: 15px; }}
            .balance {{ font-size: 48px; font-weight: bold; margin: 10px 0; }}
            .rank-badge {{
                background: rgba(212, 175, 55, 0.1); color: var(--gold);
                padding: 5px 15px; border-radius: 20px; font-size: 14px; border: 1px solid var(--gold);
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div id="user-name" style="font-weight: bold; margin-bottom: 10px;">Chargement...</div>
            <div class="balance-label">Points OWPC</div>
            <div id="user-points" class="balance">...</div>
            <span id="user-rank" class="rank-badge">---</span>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            
            const user = tg.initDataUnsafe.user;
            
            if (user) {{
                document.getElementById('user-name').innerText = user.first_name;
                
                // APPEL À NOTRE API POUR RÉCUPÉRER LES VRAIS POINTS
                fetch('/api/user/' + user.id)
                    .then(response => response.json())
                    .then(data => {{
                        document.getElementById('user-points').innerText = data.points.toLocaleString();
                        document.getElementById('user-rank').innerText = data.rank;
                    }})
                    .catch(err => {{
                        document.getElementById('user-points').innerText = "Erreur";
                    }});
            }} else {{
                document.getElementById('user-name').innerText = "Utilisateur inconnu";
            }}
        </script>
    </body>
    </html>
    """

# --- 🤖 BOT TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = get_user_data(user_id)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Open OWPC HIVE", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    
    await update.message.reply_text(
        f"Bienvenue sur la Phase 2, {update.effective_user.first_name} !\n\n"
        f"Score actuel: **{data['points']}**\n"
        "Clique sur le bouton pour l'interface visuelle.",
        reply_markup=kb, parse_mode="Markdown"
    )

async def run_bot():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    async with bot_app:
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        while True: await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
