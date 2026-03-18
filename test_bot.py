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

# --- 📊 DB LOGIC ---
def init_db():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0, 
                  rank TEXT DEFAULT 'NEWBIE', last_checkin TEXT DEFAULT '')''')
    conn.commit(); conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT points, rank, last_checkin FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close()
    return {"points": res[0], "rank": res[1], "last_checkin": res[2]} if res else {"points": 0, "rank": "NEWBIE", "last_checkin": None}

# --- 🔌 API ---
@app.get("/api/leaderboard")
async def get_leaderboard():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT name, points FROM users ORDER BY points DESC LIMIT 10")
    top = c.fetchall(); conn.close()
    return [{"name": x[0], "points": x[1]} for x in top]

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

@app.get("/api/user/{user_id}")
async def api_user(user_id: int): return JSONResponse(content=get_user_data(user_id))

@app.post("/api/add_points/{user_id}/{amount}")
async def add_points(user_id: int, amount: int):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
    conn.commit(); conn.close()
    return {"status": "success"}

@app.post("/api/daily/{user_id}")
async def daily_checkin(user_id: int):
    data = get_user_data(user_id)
    today = date.today().isoformat()
    if data["last_checkin"] == today: return {"status": "already_done"}
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE users SET points = points + 200, last_checkin = ? WHERE user_id = ?", (today, user_id))
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
            :root {{ --gold: #d4af37; --bg: #0a0a12; --card: #161626; --red: #ff4d4d; }}
            body {{ background: var(--bg); color: white; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 0; text-align: center; overflow: hidden; }}
            
            #gate-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: var(--bg); z-index: 9999; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 20px; }}
            
            .page {{ display: none; padding: 20px; height: 100vh; overflow-y: auto; box-sizing: border-box; }}
            .active-page {{ display: block; }}
            
            .balance {{ font-size: 52px; font-weight: 800; color: white; margin: 10px 0; }}
            .pillar-card {{ background: var(--card); border: 1px solid rgba(212,175,55,0.1); border-radius: 20px; padding: 18px; margin-bottom: 15px; display: flex; align-items: center; text-align: left; }}
            
            /* Leaderboard Styles */
            .lb-item {{ display: flex; justify-content: space-between; padding: 15px; background: rgba(255,255,255,0.03); border-radius: 12px; margin-bottom: 8px; border: 1px solid rgba(212,175,55,0.05); }}
            .lb-rank {{ color: var(--gold); font-weight: bold; margin-right: 10px; }}
            
            .btn-action {{ background: var(--gold); color: black; border: none; padding: 10px 18px; border-radius: 12px; font-weight: bold; cursor: pointer; }}
            .nav-bar {{ position: fixed; bottom: 0; width: 100%; background: #12121f; display: flex; justify-content: space-around; padding: 15px 0; border-top: 1px solid rgba(255,255,255,0.05); }}
            .nav-item {{ opacity: 0.5; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; }}
            .nav-item.active {{ opacity: 1; color: var(--gold); }}
        </style>
    </head>
    <body>

        <div id="gate-overlay">
            <h2 style="color: var(--gold);">OWPC HIVE</h2>
            <p style="opacity: 0.7;">Accessing Secure Protocol...</p>
            <button class="btn-action" onclick="checkAccess()">[ VERIFY IDENTITY ]</button>
        </div>

        <div id="main-content" style="display:none;">
            
            <div id="home" class="page active-page">
                <div style="font-size: 12px; color: var(--gold); margin-top:20px;">TOTAL CREDITS</div>
                <div class="balance" id="u-points">0</div>
                
                <div class="pillar-card">
                    <div style="font-size: 24px; margin-right: 15px;">🏺</div>
                    <div style="flex-grow: 1;"><b>GENESIS</b><br><small>Daily rewards.</small></div>
                    <button class="btn-action" onclick="claimDaily()">CLAIM</button>
                </div>

                <div class="pillar-card">
                    <div style="font-size: 24px; margin-right: 15px;">🤖</div>
                    <div style="flex-grow: 1;"><b>VEO MINING</b><br><small id="mining-status" style="color: #50ff50;">ONLINE (+0.01/s)</small></div>
                </div>
            </div>

            <div id="leaderboard" class="page">
                <h2 style="color: var(--gold);">TOP COMMANDERS</h2>
                <div id="lb-list">
                    </div>
            </div>

            <div id="tasks" class="page">
                <h2 style="color: var(--gold);">MISSIONS</h2>
                <div class="pillar-card">
                    <div style="flex-grow: 1;"><b>DeepTradeX X-Protocol</b><br><small>+1,000 OWPC</small></div>
                    <button class="btn-action" onclick="tg.openLink('https://x.com/DeepTradeX')">GO</button>
                </div>
            </div>

            <nav class="nav-bar">
                <div class="nav-item active" id="n-home" onclick="showPage('home', 'n-home')">🏠<br>Hive</div>
                <div class="nav-item" id="n-lb" onclick="showPage('leaderboard', 'n-lb'); loadLB();">🏆<br>Ranks</div>
                <div class="nav-item" id="n-tasks" onclick="showPage('tasks', 'n-tasks')">💠<br>Tasks</div>
            </nav>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            const user = tg.initDataUnsafe.user;
            let currentPoints = 0;
            tg.expand();

            async function checkAccess() {{
                const res = await fetch('/api/check_membership/' + user.id);
                const data = await res.json();
                if (data.status === 'member') {{
                    document.getElementById('gate-overlay').style.display = 'none';
                    document.getElementById('main-content').style.display = 'block';
                    loadUser();
                    startFarming();
                }} else {{ 
                    tg.showAlert("Access Restricted. Join @owpc_co first!"); 
                    tg.openTelegramLink('https://t.me/owpc_co');
                }}
            }}

            function loadUser() {{
                fetch('/api/user/' + user.id).then(r => r.json()).then(data => {{
                    currentPoints = data.points;
                    document.getElementById('u-points').innerText = Math.floor(currentPoints).toLocaleString();
                }});
            }}

            function loadLB() {{
                const list = document.getElementById('lb-list');
                list.innerHTML = '<p>Loading database...</p>';
                fetch('/api/leaderboard').then(r => r.json()).then(data => {{
                    list.innerHTML = '';
                    data.forEach((item, index) => {{
                        list.innerHTML += `
                            <div class="lb-item">
                                <span><span class="lb-rank">#${{index+1}}</span> ${{item.name}}</span>
                                <span style="font-weight:bold;">${{item.points.toLocaleString()}}</span>
                            </div>`;
                    }});
                }});
            }}

            function startFarming() {{
                setInterval(() => {{
                    currentPoints += 0.01;
                    document.getElementById('u-points').innerText = Math.floor(currentPoints).toLocaleString();
                }}, 1000);
                setInterval(() => {{
                    fetch('/api/add_points/' + user.id + '/1', {{ method: 'POST' }});
                }}, 30000);
            }}

            function claimDaily() {{
                fetch('/api/daily/' + user.id, {{ method: 'POST' }}).then(r => r.json()).then(data => {{
                    if(data.status == 'already_done') tg.showAlert("Protocol Genesis: Already synchronized for today.");
                    else {{ tg.HapticFeedback.notificationOccurred('success'); loadUser(); }}
                }});
            }}

            function showPage(pId, nId) {{
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                document.getElementById(pId).classList.add('active-page');
                document.getElementById(nId).classList.add('active');
                tg.HapticFeedback.impactOccurred('medium');
            }}

            checkAccess();
        </script>
    </body>
    </html>
    """

# --- BOT & SERVER ---
async def start_bot():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("🕊️ **OWPC HIVE ACCESS**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 ENTER TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]]), parse_mode="Markdown")))
    async with bot:
        await bot.initialize(); await bot.start(); await bot.updater.start_polling()
        while True: await asyncio.sleep(1)

@app.on_event("startup")
async def startup(): asyncio.create_task(start_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
