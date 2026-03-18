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

# Liens d'investissement
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK"

app = FastAPI()

# --- 📊 DB LOGIC ---
def init_db():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis INTEGER DEFAULT 0, points_unity INTEGER DEFAULT 0,
                  points_veo REAL DEFAULT 0.0, referrals INTEGER DEFAULT 0,
                  rank TEXT DEFAULT '🆕 SEEKER', last_checkin TEXT DEFAULT '')''')
    conn.commit(); conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, last_checkin, rank, referrals FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close()
    if res:
        return {"genesis": res[0], "unity": res[1], "veo": res[2], "last_checkin": res[3], "rank": res[4], "refs": res[5]}
    return {"genesis": 0, "unity": 0, "veo": 0.0, "last_checkin": None, "rank": "🆕 SEEKER", "refs": 0}

# --- 🔌 API ---
@app.get("/api/user/{user_id}")
async def api_user(user_id: int): return JSONResponse(content=get_user_data(user_id))

@app.post("/api/claim_genesis/{user_id}")
async def claim_genesis(user_id: int):
    today = date.today().isoformat(); data = get_user_data(user_id)
    if data["last_checkin"] == today: return {"status": "already_claimed"}
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE users SET points_genesis = points_genesis + 200, last_checkin = ? WHERE user_id = ?", (today, user_id))
    conn.commit(); conn.close()
    return {"status": "success"}

@app.post("/api/sync_veo/{user_id}/{amount}")
async def sync_veo(user_id: int, amount: float):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (amount, user_id))
    conn.commit(); conn.close()
    return {"status": "synced"}

# --- 🌐 INTERFACE HTML ---
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
            body {{ background: var(--bg); color: white; font-family: 'Segoe UI', sans-serif; margin: 0; padding-bottom: 90px; text-align: center; overflow-x: hidden; }}
            .page {{ display: none; padding: 20px; animation: fadeIn 0.3s forwards; }}
            .active-page {{ display: block; }}
            .header {{ padding: 15px; border-bottom: 1px solid rgba(212,175,55,0.1); }}
            .brand {{ font-size: 14px; font-weight: bold; color: var(--gold); letter-spacing: 4px; }}
            .balance-main {{ font-size: 50px; font-weight: 800; margin: 10px 0; letter-spacing: -1px; }}
            .token-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin: 20px 0; }}
            .token-box {{ background: var(--card); padding: 12px 5px; border-radius: 15px; border: 1px solid rgba(212,175,55,0.1); }}
            .pillar {{ background: var(--card); border-radius: 20px; padding: 18px; margin: 10px 0; display: flex; align-items: center; text-align: left; border: 1px solid rgba(255,255,255,0.03); }}
            .btn-action {{ background: var(--gold); color: black; border: none; padding: 12px 20px; border-radius: 12px; font-weight: bold; cursor: pointer; }}
            
            /* Roadmap Styles */
            .roadmap-item {{ text-align: left; border-left: 2px solid var(--gold); margin-left: 10px; padding-left: 20px; position: relative; margin-bottom: 25px; }}
            .roadmap-item::before {{ content: '●'; position: absolute; left: -9px; color: var(--gold); background: var(--bg); }}
            .roadmap-done {{ border-left-color: var(--green); }}
            .roadmap-done::before {{ color: var(--green); }}

            .nav-bar {{ position: fixed; bottom: 0; width: 100%; background: #12121f; display: flex; justify-content: space-around; padding: 15px 0; border-top: 1px solid rgba(255,255,255,0.05); z-index: 100; }}
            .nav-item {{ opacity: 0.5; font-size: 10px; color: white; text-transform: uppercase; }}
            .nav-item.active {{ opacity: 1; color: var(--gold); font-weight: bold; }}
            @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        </style>
    </head>
    <body>

        <div class="header"><div class="brand">OWPC TERMINAL</div></div>

        <div id="home" class="page active-page">
            <div class="balance-main" id="total-val">0</div>
            <div id="u-rank" style="color:var(--gold); font-size:12px; font-weight:bold; letter-spacing:2px; margin-bottom:20px;">🆕 SEEKER</div>

            <div class="token-grid">
                <div class="token-box" onclick="tg.openLink('{LINK_GENESIS}')"><div id="bal-g" style="font-weight:bold;">0</div><div style="font-size:8px; color:var(--gold);">GENESIS</div></div>
                <div class="token-box" onclick="tg.openLink('{LINK_UNITY}')"><div id="bal-u" style="font-weight:bold;">0</div><div style="font-size:8px; color:var(--gold);">UNITY</div></div>
                <div class="token-box" onclick="tg.openLink('{LINK_VEO}')"><div id="bal-v" style="font-weight:bold;">0.00</div><div style="font-size:8px; color:var(--gold);">VEO AI</div></div>
            </div>

            <div class="pillar">
                <div style="font-size:24px; margin-right:15px;">🏺</div>
                <div style="flex-grow:1;"><b>GENESIS</b><br><small opacity:0.6>Daily +200 OWPC</small></div>
                <button class="btn-action" onclick="claim()">CLAIM</button>
            </div>
        </div>

        <div id="friends" class="page">
            <h2 style="color:var(--gold);">NETWORK</h2>
            <div class="pillar" style="flex-direction:column; text-align:center;">
                <div style="font-size:40px;">👥</div>
                <div id="ref-count" style="font-size:24px; font-weight:bold; margin:10px 0;">0 Friends</div>
                <p style="font-size:12px; opacity:0.7;">Get 10% from your friends' claims.</p>
            </div>
            <button class="btn-action" style="width:100%;" onclick="shareRef()">INVITE COMMANDER</button>
        </div>

        <div id="roadmap" class="page">
            <h2 style="color:var(--gold);">PROTOCOL ROADMAP</h2>
            <div class="roadmap-item roadmap-done">
                <b style="color:var(--green);">PHASE 1: THE HIVE</b><br>
                <small>Terminal Launch, Genesis & Veo Mining Integration. (COMPLETED)</small>
            </div>
            <div class="roadmap-item">
                <b>PHASE 2: UNITY SYNC</b><br>
                <small>Investment multiplier, Community Tasks and Leaderboard rewards.</small>
            </div>
            <div class="roadmap-item">
                <b>PHASE 3: EVOLUTION</b><br>
                <small>OWPC Token Listing, Wallet Integration & Veo AI Pro upgrades.</small>
            </div>
        </div>

        <nav class="nav-bar">
            <div class="nav-item active" id="n-home" onclick="showPage('home', 'n-home')">🏠<br>Hive</div>
            <div class="nav-item" id="n-ref" onclick="showPage('friends', 'n-ref')">👥<br>Friends</div>
            <div class="nav-item" id="n-road" onclick="showPage('roadmap', 'n-road')">📍<br>Roadmap</div>
        </nav>

        <script>
            let tg = window.Telegram.WebApp;
            const uid = tg.initDataUnsafe.user.id;
            let state = {{ g: 0, u: 0, v: 0.0 }};
            tg.expand();

            function updateUI() {{
                document.getElementById('bal-g').innerText = Math.floor(state.g).toLocaleString();
                document.getElementById('bal-u').innerText = Math.floor(state.u).toLocaleString();
                document.getElementById('bal-v').innerText = state.v.toFixed(2);
                document.getElementById('total-val').innerText = Math.floor(state.g + state.u + state.v).toLocaleString();
            }}

            function sync() {{
                fetch('/api/user/' + uid).then(r => r.json()).then(data => {{
                    state.g = data.genesis; state.u = data.unity; state.v = data.veo;
                    document.getElementById('u-rank').innerText = data.rank;
                    document.getElementById('ref-count').innerText = data.refs + " Friends";
                    updateUI();
                }});
            }}

            function claim() {{
                fetch('/api/claim_genesis/' + uid, {{ method: 'POST' }}).then(r => r.json()).then(d => {{
                    if(d.status == 'success') {{ tg.HapticFeedback.notificationOccurred('success'); sync(); }}
                    else {{ tg.showAlert("Synced for today."); }}
                }});
            }}

            function shareRef() {{
                const link = "https://t.me/share/url?url=https://t.me/owpc_bot?start=" + uid + "&text=Join the OWPC Hive Network!";
                tg.openTelegramLink(link);
            }}

            function showPage(pId, nId) {{
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                document.getElementById(pId).classList.add('active-page');
                document.getElementById(nId).classList.add('active');
                tg.HapticFeedback.impactOccurred('light');
            }}

            setInterval(() => {{ state.v += 0.01; updateUI(); }}, 1000);
            setInterval(() => {{ fetch(`/api/sync_veo/${{uid}}/0.30`, {{ method: 'POST' }}); }}, 30000);
            sync();
        </script>
    </body>
    </html>
    """

# --- BOT SETUP ---
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("🕊️ **OWPC TERMINAL**\nWelcome, Commander.", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]]), parse_mode="Markdown")

async def run_bot():
    init_db(); bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    async with bot:
        await bot.initialize(); await bot.start(); await bot.updater.start_polling()
        while True: await asyncio.sleep(1)

@app.on_event("startup")
async def startup(): asyncio.create_task(run_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
