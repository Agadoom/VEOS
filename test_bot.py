import os
import asyncio
import sqlite3
import nest_asyncio
import httpx
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
CHANNEL_ID = "@owpc_co"

app = FastAPI()

# --- 📊 LOGIC RANKS ---
def calculate_rank(points):
    if points >= 15000: return "👑 OVERLORD"
    if points >= 5000:  return "💎 ELITE"
    if points >= 1500:  return "⚔️ COMMANDER"
    if points >= 500:   return "🛡️ GUARDIAN"
    return "🆕 SEEKER"

# --- 🔌 API ---
@app.get("/api/user/{user_id}")
async def api_user(user_id: int):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT points, last_checkin FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close()
    if res:
        pts = res[0]
        return {"points": pts, "rank": calculate_rank(pts), "last_checkin": res[1]}
    return {"points": 0, "rank": "🆕 SEEKER", "last_checkin": None}

@app.get("/api/leaderboard")
async def get_leaderboard():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT name, points FROM users ORDER BY points DESC LIMIT 10")
    top = c.fetchall(); conn.close()
    return [{"name": x[0], "points": x[1], "rank": calculate_rank(x[1])} for x in top]

@app.get("/api/check_membership/{user_id}")
async def check_membership(user_id: int):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params={"chat_id": CHANNEL_ID, "user_id": user_id})
            data = resp.json()
            if data.get("ok") and data["result"]["status"] in ['member', 'administrator', 'creator']:
                return {"status": "member"}
    except: pass
    return {"status": "not_member"}

@app.post("/api/add_points/{user_id}/{amount}")
async def add_points(user_id: int, amount: int):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
    conn.commit(); conn.close()
    return {"status": "success"}

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
            :root {{ --gold: #d4af37; --bg: #0a0a12; --card: #161626; --green: #50ff50; }}
            body {{ background: var(--bg); color: white; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 0; text-align: center; overflow: hidden; }}
            .page {{ display: none; padding: 20px; height: 100vh; overflow-y: auto; box-sizing: border-box; }}
            .active-page {{ display: block; }}
            .balance {{ font-size: 52px; font-weight: 800; margin-top: 10px; }}
            .rank-badge {{ color: var(--gold); font-size: 14px; font-weight: bold; letter-spacing: 2px; margin-bottom: 20px; }}
            .pillar-card {{ background: var(--card); border-radius: 20px; padding: 18px; margin-bottom: 15px; display: flex; align-items: center; text-align: left; border: 1px solid rgba(212,175,55,0.1); }}
            .lb-item {{ display: flex; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.03); border-radius: 12px; margin-bottom: 8px; font-size: 14px; }}
            .btn-action {{ background: var(--gold); color: black; border: none; padding: 10px 18px; border-radius: 12px; font-weight: bold; }}
            .nav-bar {{ position: fixed; bottom: 0; width: 100%; background: #12121f; display: flex; justify-content: space-around; padding: 15px 0; border-top: 1px solid rgba(255,255,255,0.05); }}
            .nav-item {{ opacity: 0.5; font-size: 10px; }}
            .nav-item.active {{ opacity: 1; color: var(--gold); }}
        </style>
    </head>
    <body>
        <div id="main-content">
            <div id="home" class="page active-page">
                <div class="balance" id="u-points">0</div>
                <div id="u-rank" class="rank-badge">LOADING RANK...</div>
                
                <div class="pillar-card">
                    <div style="font-size: 24px; margin-right: 15px;">🏺</div>
                    <div style="flex-grow: 1;"><b>GENESIS</b><br><small>Daily rewards.</small></div>
                    <button class="btn-action" onclick="claimDaily()">CLAIM</button>
                </div>

                <div class="pillar-card">
                    <div style="font-size: 24px; margin-right: 15px;">🤖</div>
                    <div style="flex-grow: 1;"><b>VEO MINING</b><br><small style="color: var(--green);">ACTIVE (+0.01/s)</small></div>
                </div>
            </div>

            <div id="leaderboard" class="page">
                <h2 style="color: var(--gold);">COMMANDERS</h2>
                <div id="lb-list"></div>
            </div>

            <nav class="nav-bar">
                <div class="nav-item active" id="n-home" onclick="showPage('home', 'n-home')">🏠<br>Hive</div>
                <div class="nav-item" id="n-lb" onclick="showPage('leaderboard', 'n-lb'); loadLB();">🏆<br>Ranks</div>
            </nav>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            const user = tg.initDataUnsafe.user;
            let currentPoints = 0;
            tg.expand();

            function loadUser() {{
                fetch('/api/user/' + user.id).then(r => r.json()).then(data => {{
                    currentPoints = data.points;
                    document.getElementById('u-points').innerText = Math.floor(currentPoints).toLocaleString();
                    document.getElementById('u-rank').innerText = data.rank;
                }});
            }}

            function loadLB() {{
                const list = document.getElementById('lb-list');
                list.innerHTML = 'Syncing...';
                fetch('/api/leaderboard').then(r => r.json()).then(data => {{
                    list.innerHTML = '';
                    data.forEach((item, i) => {{
                        list.innerHTML += `<div class="lb-item">
                            <span>#${{i+1}} ${{item.name}} <br><small style="color:var(--gold)">${{item.rank}}</small></span>
                            <b>${{item.points.toLocaleString()}}</b>
                        </div>`;
                    }});
                }});
            }}

            function startFarming() {{
                setInterval(() => {{
                    currentPoints += 0.01;
                    document.getElementById('u-points').innerText = Math.floor(currentPoints).toLocaleString();
                }}, 1000);
                setInterval(() => {{ fetch('/api/add_points/' + user.id + '/1', {{ method: 'POST' }}); }}, 30000);
            }}

            function showPage(pId, nId) {{
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                document.getElementById(pId).classList.add('active-page');
                document.getElementById(nId).classList.add('active');
            }}

            loadUser();
            startFarming();
        </script>
    </body>
    </html>
    """
# --- BOT SETUP ---
async def start_bot():
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("🕊️ OWPC HIVE", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN", web_app=WebAppInfo(url=WEBAPP_URL))]]))))
    async with bot:
        await bot.initialize(); await bot.start(); await bot.updater.start_polling()
        while True: await asyncio.sleep(1)

@app.on_event("startup")
async def startup(): asyncio.create_task(start_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
