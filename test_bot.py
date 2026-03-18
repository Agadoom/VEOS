import os
import asyncio
import sqlite3
import nest_asyncio
from datetime import datetime, date
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

nest_asyncio.apply()

# --- ⚙️ CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.environ.get("PORT", 8080))
WEBAPP_URL = "https://veos-production.up.railway.app" 
DB_NAME = "owpc_data.db"

app = FastAPI()

# --- 📊 DB LOGIC ---
def get_user_data(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT points, rank, last_checkin FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    if res:
        return {"points": res[0], "rank": res[1], "last_checkin": res[2]}
    return {"points": 0, "rank": "NEWBIE", "last_checkin": None}

def get_top_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, points, rank FROM users ORDER BY points DESC LIMIT 10")
    res = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "points": r[1], "rank": r[2]} for r in res]

# --- 🔌 API ---
@app.get("/api/user/{user_id}")
async def api_user(user_id: int): return JSONResponse(content=get_user_data(user_id))

@app.get("/api/leaderboard")
async def api_leaderboard(): return JSONResponse(content=get_top_users())

@app.post("/api/daily/{user_id}")
async def daily_checkin(user_id: int):
    data = get_user_data(user_id)
    today = date.today().isoformat()
    if data["last_checkin"] == today:
        return {"status": "already_done"}
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET points = points + 200, last_checkin = ? WHERE user_id = ?", (today, user_id))
    conn.commit(); conn.close()
    return {"status": "success", "bonus": 200}

# --- 🌐 INTERFACE ---
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
            :root {{ --gold: #d4af37; --bg: #0a0a12; --card: #161626; }}
            body {{ background: var(--bg); color: white; font-family: sans-serif; margin: 0; padding: 0; text-align: center; }}
            .page {{ display: none; padding: 20px; padding-bottom: 100px; animation: fadeIn 0.3s; }}
            .active-page {{ display: block; }}
            @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
            
            .pillar-card {{ background: var(--card); border: 1px solid rgba(212,175,55,0.1); border-radius: 20px; padding: 15px; margin-bottom: 10px; display: flex; align-items: center; text-align: left; }}
            .balance {{ font-size: 40px; font-weight: bold; margin: 10px 0; color: white; }}
            .nav-bar {{ position: fixed; bottom: 0; width: 100%; background: #12121f; display: flex; justify-content: space-around; padding: 15px 0; border-top: 1px solid rgba(255,255,255,0.05); }}
            .nav-item {{ color: #555; font-size: 10px; cursor: pointer; }}
            .active {{ color: var(--gold); font-weight: bold; }}
            .btn-action {{ background: var(--gold); color: black; border: none; padding: 10px 15px; border-radius: 10px; font-weight: bold; }}
            .rank-item {{ display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        </style>
    </head>
    <body>
        <div id="home" class="page active-page">
            <h2 id="u-name">...</h2>
            <div class="balance" id="u-points">0</div>
            <div id="u-rank" style="color: var(--gold); margin-bottom: 20px;">RANK</div>

            <div class="pillar-card">
                <div style="font-size: 24px; margin-right: 15px;">🏺</div>
                <div style="flex-grow: 1;">
                    <div style="font-weight: bold; color: var(--gold);">GENESIS DAILY</div>
                    <div style="font-size: 11px; opacity: 0.6;">Claim 200 OWPC every 24h.</div>
                </div>
                <button id="btn-daily" class="btn-action" onclick="claimDaily()">CLAIM</button>
            </div>
            <div class="pillar-card" onclick="showPage('tasks', document.getElementById('nav-tasks'))">
                <div style="font-size: 24px; margin-right: 15px;">🌍</div>
                <div style="flex-grow: 1;"><div style="font-weight: bold; color: var(--gold);">UNITY</div><div style="font-size: 11px; opacity: 0.6;">Missions & Growth.</div></div>
            </div>
        </div>

        <div id="leaderboard" class="page">
            <h2 style="color: var(--gold);">TOP COMMANDERS</h2>
            <div id="rank-list" class="pillar-card" style="display: block;">Chargement...</div>
        </div>

        <div id="tasks" class="page">
            <h2 style="color: var(--gold);">MISSIONS</h2>
            <div class="pillar-card">
                <div style="flex-grow: 1;"><div style="font-weight: bold;">Follow DeepTradeX</div><div style="font-size: 11px; color: var(--gold);">+1,000 CREDITS</div></div>
                <button class="btn-action" onclick="tg.openLink('https://x.com/DeepTradeX')">GO</button>
            </div>
        </div>

        <nav class="nav-bar">
            <div class="nav-item active" onclick="showPage('home', this)">🏠<br>Home</div>
            <div class="nav-item" id="nav-tasks" onclick="showPage('tasks', this)">💠<br>Tasks</div>
            <div class="nav-item" onclick="loadLeaderboard(this)">🏆<br>Rank</div>
        </nav>

        <script>
            let tg = window.Telegram.WebApp;
            const user = tg.initDataUnsafe.user;

            function showPage(pId, el) {{
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                document.getElementById(pId).classList.add('active-page');
                el.classList.add('active');
                tg.HapticFeedback.impactOccurred('medium');
            }}

            function refresh() {{
                fetch('/api/user/' + user.id).then(r => r.json()).then(data => {{
                    document.getElementById('u-points').innerText = data.points.toLocaleString();
                    document.getElementById('u-rank').innerText = data.rank;
                    document.getElementById('u-name').innerText = user.first_name.toUpperCase();
                }});
            }}

            function claimDaily() {{
                fetch('/api/daily/' + user.id, {{ method: 'POST' }}).then(r => r.json()).then(data => {{
                    if(data.status == 'already_done') {{
                        tg.showAlert("Revenez demain ! Protocol Genesis déjà activé.");
                    }} else {{
                        tg.HapticFeedback.notificationOccurred('success');
                        tg.showAlert("Bonus Genesis reçu : +200 OWPC");
                        refresh();
                    }}
                }});
            }}

            function loadLeaderboard(el) {{
                showPage('leaderboard', el);
                fetch('/api/leaderboard').then(r => r.json()).then(data => {{
                    let html = "";
                    data.forEach((u, index) => {{
                        html += `<div class="rank-item"><span>#${{index+1}} ${{u.rank}}</span> <b>${{u.points.toLocaleString()}}</b></div>`;
                    }});
                    document.getElementById('rank-list').innerHTML = html;
                }});
            }}

            refresh();
            tg.expand();
        </script>
    </body>
    </html>
    """

# --- BOT START ---
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Launch OWPC HIVE", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await u.message.reply_text("🕊️ **HIVE TERMINAL ONLINE**\nWelcome Commander.", reply_markup=kb, parse_mode="Markdown")

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
