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
        return {"points": result[0], "rank": result[1]} if result else {"points": 0, "rank": "NEWBIE"}
    except Exception as e:
        return {"points": 0, "rank": "ERROR"}

def update_user_points(user_id, amount):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

# --- 🔌 API ---
@app.get("/api/user/{user_id}")
async def api_get_user(user_id: int):
    return JSONResponse(content=get_user_data(user_id))

@app.post("/api/task/complete")
async def complete_task(data: dict):
    user_id = data.get("user_id")
    reward = data.get("reward", 500)
    if update_user_points(user_id, reward):
        return {"status": "success", "new_balance": get_user_data(user_id)["points"]}
    return {"status": "error"}

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
            :root {{ --gold: #d4af37; --bg: #0a0a12; --card: #161626; }}
            body {{ background-color: var(--bg); color: white; margin: 0; padding: 0; font-family: sans-serif; text-align: center; }}
            
            .page {{ display: none; padding: 20px; padding-bottom: 80px; }}
            .active-page {{ display: block; }}

            .card {{ background: var(--card); border: 1px solid rgba(212,175,55,0.2); border-radius: 20px; padding: 25px; margin-top: 20px; }}
            .balance {{ font-size: 42px; font-weight: bold; color: white; margin: 10px 0; }}
            
            /* TASKS STYLE */
            .task-item {{
                background: var(--card); border-radius: 15px; padding: 15px;
                display: flex; justify-content: space-between; align-items: center;
                margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.05);
            }}
            .task-info {{ text-align: left; }}
            .task-name {{ font-weight: bold; font-size: 14px; }}
            .task-reward {{ color: var(--gold); font-size: 12px; font-weight: bold; }}
            .btn-claim {{ background: var(--gold); color: black; border: none; padding: 8px 15px; border-radius: 8px; font-weight: bold; cursor: pointer; }}

            /* NAV BAR */
            .nav-bar {{
                position: fixed; bottom: 0; width: 100%; background: #12121f;
                display: flex; justify-content: space-around; padding: 15px 0;
                border-top: 1px solid rgba(255,255,255,0.1);
            }}
            .nav-item {{ color: grey; font-size: 12px; cursor: pointer; }}
            .nav-item.active {{ color: var(--gold); font-weight: bold; }}
        </style>
    </head>
    <body>
        <div id="home" class="page active-page">
            <h2 id="display-name">...</h2>
            <div class="card">
                <div style="font-size: 12px; color: var(--gold);">OWPC CREDITS</div>
                <div id="user-points" class="balance">0</div>
                <span id="user-rank" style="color: var(--gold); border: 1px solid var(--gold); padding: 4px 10px; border-radius: 10px; font-size: 12px;">...</span>
            </div>
            <button onclick="invite()" style="width:100%; margin-top:20px; padding:15px; border-radius:12px; background:var(--gold); border:none; font-weight:bold;">🤝 INVITE FRIENDS</button>
        </div>

        <div id="tasks" class="page">
            <h2>MISSIONS</h2>
            <div class="task-item">
                <div class="task-info">
                    <div class="task-name">Suivre OWPC sur X</div>
                    <div class="task-reward">+1,000 OWPC</div>
                </div>
                <button class="btn-claim" onclick="doTask(1000, 'https://x.com/owpc')">GO</button>
            </div>
            <div class="task-item">
                <div class="task-info">
                    <div class="task-name">Rejoindre le Channel</div>
                    <div class="task-reward">+500 OWPC</div>
                </div>
                <button class="btn-claim" onclick="doTask(500, 'https://t.me/owpc_co')">GO</button>
            </div>
        </div>

        <nav class="nav-bar">
            <div class="nav-item active" onclick="showPage('home', this)">🏠<br>Home</div>
            <div class="nav-item" onclick="showPage('tasks', this)">💎<br>Tasks</div>
        </nav>

        <script>
            let tg = window.Telegram.WebApp;
            const user = tg.initDataUnsafe.user;

            function showPage(pageId, el) {{
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                document.getElementById(pageId).classList.add('active-page');
                el.classList.add('active');
                tg.HapticFeedback.impactOccurred('light');
            }}

            function refreshData() {{
                fetch('/api/user/' + user.id).then(r => r.json()).then(data => {{
                    document.getElementById('user-points').innerText = data.points.toLocaleString();
                    document.getElementById('user-rank').innerText = data.rank;
                    document.getElementById('display-name').innerText = user.first_name.toUpperCase();
                }});
            }}

            function doTask(reward, url) {{
                tg.HapticFeedback.notificationOccurred('success');
                tg.openLink(url);
                // Simulation de validation de tâche
                fetch('/api/task/complete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ user_id: user.id, reward: reward }})
                }}).then(() => refreshData());
            }}

            function invite() {{
                tg.HapticFeedback.impactOccurred('medium');
                tg.openTelegramLink("https://t.me/share/url?url=https://t.me/ton_bot?start=" + user.id + "&text=Rejoins le Hive !");
            }}

            refreshData();
            tg.expand();
        </script>
    </body>
    </html>
    """

# --- 🤖 BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Launch OWPC HIVE", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📢 Official Channel", url="https://t.me/owpc_co")]
    ])
    await update.message.reply_text(f"Welcome back {update.effective_user.first_name}!\n\nReady to earn more?", reply_markup=kb)

async def run_bot():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    async with bot_app:
        await bot_app.initialize(); await bot_app.start(); await bot_app.updater.start_polling()
        while True: await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event(): asyncio.create_task(run_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
