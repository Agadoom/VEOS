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

# --- 📊 DB LOGIC ---
def get_user_data(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT points, rank FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return {"points": result[0], "rank": result[1]} if result else {"points": 0, "rank": "NEWBIE"}
    except:
        return {"points": 0, "rank": "NEWBIE"}

def update_user_points(user_id, amount):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()
        return True
    except: return False

# --- 🔌 API ---
@app.get("/api/user/{user_id}")
async def api_user(user_id: int): return JSONResponse(content=get_user_data(user_id))

@app.post("/api/task/complete")
async def complete_task(data: dict):
    if update_user_points(data.get("user_id"), data.get("reward", 500)):
        return {"status": "success"}
    return {"status": "error"}

# --- 🌐 MINI APP INTERFACE ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {{ --gold: #d4af37; --bg: #0a0a12; --veo: #00f2ff; }}
            body {{ background: var(--bg); color: white; font-family: sans-serif; margin: 0; padding: 0; text-align: center; }}
            
            .page {{ display: none; padding: 20px; padding-bottom: 90px; }}
            .active-page {{ display: block; }}

            .pillar-card {{
                background: linear-gradient(145deg, #161626, #1f1f35);
                border: 1px solid rgba(212,175,55,0.2);
                border-radius: 20px; padding: 15px; margin-bottom: 15px;
                display: flex; align-items: center; justify-content: space-between;
            }}
            
            .pillar-icon {{ font-size: 24px; margin-right: 15px; }}
            .pillar-info {{ text-align: left; flex-grow: 1; }}
            .pillar-title {{ font-weight: bold; color: var(--gold); font-size: 16px; }}
            .pillar-desc {{ font-size: 11px; opacity: 0.7; }}

            .balance {{ font-size: 45px; font-weight: bold; margin: 20px 0; }}
            
            .nav-bar {{
                position: fixed; bottom: 0; width: 100%; background: #12121f;
                display: flex; justify-content: space-around; padding: 15px 0;
                border-top: 1px solid rgba(255,255,255,0.1);
            }}
            .nav-item {{ color: grey; font-size: 11px; cursor: pointer; opacity: 0.6; }}
            .nav-item.active {{ color: var(--gold); opacity: 1; font-weight: bold; }}
            
            .btn-go {{ background: var(--gold); color: black; border: none; padding: 8px 12px; border-radius: 8px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div id="home" class="page active-page">
            <h2 id="u-name">...</h2>
            <div class="balance" id="u-points">0</div>
            <div style="margin-bottom: 25px;"><span id="u-rank" style="border:1px solid var(--gold); padding:5px 15px; border-radius:15px; color:var(--gold);">RANK</span></div>
            
            <div class="pillar-card" style="border-color: var(--gold);">
                <div class="pillar-icon">🏺</div>
                <div class="pillar-info">
                    <div class="pillar-title">GENESIS</div>
                    <div class="pillar-desc">The origin of OWPC. Early access.</div>
                </div>
                <button class="btn-go" onclick="tg.showAlert('Genesis core is active')">STATUS</button>
            </div>

            <div class="pillar-card">
                <div class="pillar-icon">🌍</div>
                <div class="pillar-info">
                    <div class="pillar-title">UNITY</div>
                    <div class="pillar-desc">Community & Ecosystem growth.</div>
                </div>
                <button class="btn-go" onclick="showPage('tasks', document.getElementById('nav-tasks'))">JOIN</button>
            </div>

            <div class="pillar-card" style="border-color: var(--veo);">
                <div class="pillar-icon">🤖</div>
                <div class="pillar-info">
                    <div class="pillar-title" style="color: var(--veo);">VEO</div>
                    <div class="pillar-desc">Artificial Intelligence & Future.</div>
                </div>
                <div style="font-size: 10px; color: var(--veo);">LOCKED</div>
            </div>
        </div>

        <div id="tasks" class="page">
            <h2 style="color: var(--gold);">UNITY TASKS</h2>
            <div class="pillar-card">
                <div class="pillar-info">
                    <div class="pillar-title">Follow DeepTradeX</div>
                    <div class="pillar-desc">+1,000 CREDITS</div>
                </div>
                <button class="btn-go" onclick="doTask(1000, 'https://x.com/DeepTradeX')">GO</button>
            </div>
            <div class="pillar-card">
                <div class="pillar-info">
                    <div class="pillar-title">Join Telegram Channel</div>
                    <div class="pillar-desc">+500 CREDITS</div>
                </div>
                <button class="btn-go" onclick="doTask(500, 'https://t.me/owpc_co')">GO</button>
            </div>
        </div>

        <nav class="nav-bar">
            <div class="nav-item active" onclick="showPage('home', this)">🏠<br>Home</div>
            <div class="nav-item" id="nav-tasks" onclick="showPage('tasks', this)">💠<br>Pillars</div>
        </nav>

        <script>
            let tg = window.Telegram.WebApp;
            const user = tg.initDataUnsafe.user;

            function showPage(pId, el) {{
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                document.getElementById(pId).classList.add('active-page');
                el.classList.add('active');
                tg.HapticFeedback.impactOccurred('light');
            }}

            function refresh() {{
                fetch('/api/user/' + user.id).then(r => r.json()).then(data => {{
                    document.getElementById('u-points').innerText = data.points.toLocaleString();
                    document.getElementById('u-rank').innerText = data.rank;
                    document.getElementById('u-name').innerText = user.first_name.toUpperCase();
                }});
            }}

            function doTask(reward, url) {{
                tg.HapticFeedback.notificationOccurred('success');
                tg.openLink(url);
                fetch('/api/task/complete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ user_id: user.id, reward: reward }})
                }}).then(() => setTimeout(refresh, 2000));
            }}

            refresh();
            tg.expand();
        </script>
    </body>
    </html>
    """

# --- 🤖 BOT ---
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Launch OWPC HIVE", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📢 Official Channel", url="https://t.me/owpc_co")]
    ])
    await u.message.reply_text("🕊️ **Welcome to the HIVE**\nGenesis. Unity. Veo.", reply_markup=kb, parse_mode="Markdown")

async def run_bot():
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    async with bot:
        await bot.initialize(); await bot.start(); await bot.updater.start_polling()
        while True: await asyncio.sleep(1)

@app.on_event("startup")
async def startup(): asyncio.create_task(run_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
