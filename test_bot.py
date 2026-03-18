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

# --- ⚙️ CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.environ.get("PORT", 8080))
# Remplace bien par ton URL réelle si elle change
WEBAPP_URL = "https://veos-production.up.railway.app" 
DB_NAME = "owpc_data.db"

app = FastAPI()

# --- 📊 GESTION BASE DE DONNÉES ---
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
        print(f"Erreur Database: {e}")
    return {"points": 0, "rank": "NEWBIE"}

# --- 🔌 API POUR LA MINI APP ---
@app.get("/api/user/{user_id}")
async def api_get_user(user_id: int):
    data = get_user_data(user_id)
    return JSONResponse(content=data)

# --- 🌐 INTERFACE MINI APP (HTML/JS/CSS) ---
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
            :root {{ --gold: #d4af37; --bg: #0a0a12; --card-bg: #161626; }}
            
            body {{ 
                background-color: var(--bg); color: white; margin: 0; padding: 20px; 
                font-family: 'Segoe UI', Roboto, sans-serif; text-align: center; overflow: hidden;
            }}
            
            .header {{ margin-top: 10px; margin-bottom: 20px; }}
            .logo {{ 
                width: 85px; height: 85px; border-radius: 50%; 
                border: 2px solid var(--gold); padding: 5px;
                box-shadow: 0 0 15px rgba(212, 175, 55, 0.4);
            }}

            #user-name {{ font-size: 20px; font-weight: bold; margin-top: 10px; letter-spacing: 1px; }}

            .card {{
                background: linear-gradient(145deg, #161626, #1f1f35);
                border: 1px solid rgba(212, 175, 55, 0.2);
                border-radius: 28px; padding: 35px 20px; margin: 20px 0;
                box-shadow: 0 15px 35px rgba(0,0,0,0.6);
            }}

            .balance-label {{ font-size: 11px; color: var(--gold); letter-spacing: 3px; text-transform: uppercase; opacity: 0.8; }}
            .balance {{ font-size: 52px; font-weight: 800; margin: 10px 0; text-shadow: 0 0 20px rgba(214, 175, 55, 0.2); }}
            
            .rank-badge {{
                background: rgba(212, 175, 55, 0.15); color: var(--gold);
                padding: 7px 20px; border-radius: 50px; font-size: 13px; 
                font-weight: bold; border: 1px solid var(--gold); text-transform: uppercase;
            }}

            .btn-invite {{
                background: var(--gold); color: #000; border: none; 
                padding: 18px; border-radius: 18px; font-weight: 800; 
                font-size: 16px; width: 100%; cursor: pointer;
                margin-top: 20px; transition: transform 0.1s;
                box-shadow: 0 5px 15px rgba(212, 175, 55, 0.3);
            }}

            .btn-invite:active {{ transform: scale(0.96); }}
        </style>
    </head>
    <body>
        <div class="header">
            <img src="https://api.dicebear.com/7.x/bottts/svg?seed=OWPC" class="logo">
            <div id="user-name">CHARGEMENT...</div>
        </div>

        <div class="card">
            <div class="balance-label">OWPC Credits</div>
            <div id="user-points" class="balance">0</div>
            <span id="user-rank" class="rank-badge">...</span>
        </div>

        <button class="btn-invite" onclick="inviteFriends()">🤝 INVITE FRIENDS</button>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            tg.ready();

            // Récupération des données Telegram
            const user = tg.initDataUnsafe.user;
            
            if (user) {{
                document.getElementById('user-name').innerText = user.first_name.toUpperCase();
                
                // Appel API pour les points réels
                fetch('/api/user/' + user.id)
                    .then(response => response.json())
                    .then(data => {{
                        document.getElementById('user-points').innerText = data.points.toLocaleString();
                        document.getElementById('user-rank').innerText = data.rank;
                    }})
                    .catch(err => console.error("Erreur API:", err));
            }}

            function inviteFriends() {{
                // Vibration Haptique Medium
                tg.HapticFeedback.impactOccurred('medium');
                
                const botUsername = "ton_bot_username"; // Remplace par l'ID de ton bot si besoin
                const inviteLink = "https://t.me/" + botUsername + "?start=" + user.id;
                const text = "Rejoins-moi sur OWPC HIVE ! Gagne des crédits et grimpe dans le classement. 🕊️💎";
                const shareUrl = "https://t.me/share/url?url=" + encodeURIComponent(inviteLink) + "&text=" + encodeURIComponent(text);
                
                tg.openTelegramLink(shareUrl);
            }}
        </script>
    </body>
    </html>
    """

# --- 🤖 BOT TELEGRAM LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = get_user_data(user_id)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Open OWPC HIVE", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📢 Channel", url="https://t.me/owpc_co")]
    ])
    
    await update.message.reply_text(
        f"Salut **{update.effective_user.first_name}** ! 🕊️\n\n"
        f"Ton solde : **{data['points']:,} OWPC**\n"
        f"Ton rang : **{data['rank']}**\n\n"
        "Prêt pour la Phase 2 ? Lance l'app visuelle ci-dessous :",
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
