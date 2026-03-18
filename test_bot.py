import os
import asyncio
import sqlite3
import nest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

nest_asyncio.apply()

# --- CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.environ.get("PORT", 8080))
# Ton URL Railway actuelle
WEBAPP_URL = "https://veos-production.up.railway.app"
DB_NAME = "owpc_data.db"

app = FastAPI()

# --- 📊 FONCTION BASE DE DONNÉES ---
def get_user_data(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT points, rank FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return {"points": result[0], "rank": result[1]}
    except Exception as e:
        print(f"Erreur DB: {e}")
    return {"points": 0, "rank": "NEWBIE"}

# --- 🌐 INTERFACE MINI APP (HTML/CSS/JS) ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <title>OWPC HIVE</title>
        <style>
            :root {{
                --gold: #d4af37;
                --bg: #0a0a12;
            }}
            body {{
                background-color: var(--bg);
                color: white;
                margin: 0; padding: 20px;
                font-family: 'Segoe UI', sans-serif;
                text-align: center;
            }}
            .card {{
                background: linear-gradient(145deg, #161626, #1f1f35);
                border: 1px solid rgba(212, 175, 55, 0.3);
                border-radius: 25px;
                padding: 30px 20px;
                margin-top: 40px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            }}
            .logo {{ width: 80px; filter: drop-shadow(0 0 10px var(--gold)); }}
            .balance-label {{ font-size: 12px; color: var(--gold); letter-spacing: 2px; text-transform: uppercase; margin-top: 15px; }}
            .balance {{ font-size: 48px; font-weight: bold; margin: 10px 0; }}
            .rank-badge {{
                background: rgba(212, 175, 55, 0.1);
                color: var(--gold);
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid var(--gold);
            }}
            .footer-nav {{
                position: fixed; bottom: 20px; left: 20px; right: 20px;
                display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;
            }}
            .nav-btn {{
                background: rgba(255,255,255,0.05);
                border: none; color: white; padding: 10px;
                border-radius: 12px; font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <img src="https://api.dicebear.com/7.x/bottts/svg?seed=OWPC" class="logo">
            <div class="balance-label">OWPC Credits</div>
            <div id="user-points" class="balance">...</div>
            <span id="user-rank" class="rank-badge">LOADING...</span>
        </div>

        <div class="footer-nav">
            <button class="nav-btn" onclick="tg.showAlert('Quêtes bientôt disponibles')">🛠 Quests</button>
            <button class="nav-btn" onclick="tg.showAlert('Staking en cours')">💎 Staking</button>
            <button class="nav-btn" onclick="tg.close()">❌ Close</button>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            
            // Récupérer les infos de l'utilisateur depuis Telegram
            const user = tg.initDataUnsafe.user;
            
            if (user) {{
                // On pourrait appeler une API ici, mais pour le test on simule
                // En Phase 3, on fera un fetch vers ton serveur
                document.getElementById('user-points').innerText = "12,450"; 
                document.getElementById('user-rank').innerText = "👑 OVERLORD";
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
        [InlineKeyboardButton("🚀 Launch OWPC HIVE", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📊 Statut Classique", callback_data="stats")]
    ])
    
    await update.message.reply_text(
        f"Salut {update.effective_user.first_name} ! 🕊️\n\n"
        f"Tes points actuels : **{data['points']}**\n"
        "Accède à l'interface visuelle via le bouton ci-dessous :",
        reply_markup=kb,
        parse_mode="Markdown"
    )

async def run_bot():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    
    async with bot_app:
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        while True:
            await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
