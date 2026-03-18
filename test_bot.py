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
BOT_USERNAME = "owpcsbot"

LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK"

app = FastAPI()

# --- 📊 DATABASE ---
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
    if res: return {"genesis": res[0], "unity": res[1], "veo": res[2], "last_checkin": res[3], "rank": res[4], "refs": res[5]}
    return {"genesis": 0, "unity": 0, "veo": 0.0, "last_checkin": None, "rank": "🆕 SEEKER", "refs": 0}

# --- 🔌 API ---
@app.get("/api/stats")
async def get_stats():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    # FIX: Use COALESCE to avoid NULL returning 0
    c.execute("SELECT SUM(COALESCE(points_genesis,0) + COALESCE(points_unity,0) + COALESCE(points_veo,0)) FROM users")
    total = c.fetchone()[0] or 0
    conn.close()
    return {"user_count": count, "total_claimed": int(total)}

@app.get("/api/user/{user_id}")
async def api_user(user_id: int): return JSONResponse(content=get_user_data(user_id))

@app.post("/api/claim_genesis/{user_id}")
async def claim_genesis(user_id: int):
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    # FIX: Ensure user exists before update
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    c.execute("UPDATE users SET points_genesis = points_genesis + 200, last_checkin = ? WHERE user_id = ?", (today, user_id))
    conn.commit(); conn.close()
    return {"status": "success"}

@app.post("/api/sync_veo/{user_id}/{amount}")
async def sync_veo(user_id: int, amount: float):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (amount, user_id))
    conn.commit(); conn.close()
    return {"status": "synced"}

# --- 🌐 WEBAPP INTERFACE ---
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
            
            .stats-bar {{ background: rgba(212,175,55,0.05); border-radius: 50px; padding: 6px 15px; display: inline-flex; gap: 15px; font-size: 9px; margin: 15px 0; border: 1px solid rgba(212,175,55,0.1); text-transform: uppercase; }}
            .live-dot {{ height: 6px; width: 6px; background: var(--green); border-radius: 50%; display: inline-block; margin-right: 5px; animation: blink 1.5s infinite; }}
            
            .header {{ padding: 15px; font-weight: bold; color: var(--gold); letter-spacing: 4px; font-size: 14px; border-bottom: 1px solid rgba(212,175,55,0.1); }}
            .balance-main {{ font-size: 55px; font-weight: 800; margin: 5px 0; letter-spacing: -2px; position: relative; }}
            
            .float-text {{ position: absolute; color: var(--green); font-size: 24px; font-weight: bold; pointer-events: none; animation: floatUp 1s forwards; left: 50%; transform: translateX(-50%); }}
            
            .token-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin: 20px 0; }}
            .token-box {{ background: var(--card); padding: 12px 5px; border-radius: 15px; border: 1px solid rgba(212,175,55,0.1); }}
            .pillar {{ background: var(--card); border-radius: 20px; padding: 18px; margin: 10px 0; display: flex; align-items: center; text-align: left; }}
            .btn-action {{ background: var(--gold); color: black; border: none; padding: 12px 20px; border-radius: 12px; font-weight: bold; cursor: pointer; }}
            
            .nav-bar {{ position: fixed; bottom: 0; width: 100%; background: #12121f; display: flex; justify-content: space-around; padding: 15px 0; border-top: 1px solid rgba(255,255,255,0.05); }}
            .nav-item {{ opacity: 0.4; font-size: 10px; color: white; text-align: center; }}
            .nav-item.active {{ opacity: 1; color: var(--gold); font-weight: bold; }}

            @keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}
            @keyframes floatUp {{ 0% {{ opacity: 1; transform: translateY(0) translateX(-50%); }} 100% {{ opacity: 0; transform: translateY(-60px) translateX(-50%); }} }}
            @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        </style>
    </head>
    <body>

        <div class="header">OWPC TERMINAL</div>

        <div class="stats-bar">
            <span><span class="live-dot"></span><b id="st-users">0</b> COMMANDERS</span>
            <span>💎 <b id="st-total">0</b> ASSETS</span>
        </div>

        <div id="home" class="page active-page">
            <div style="position: relative; display: inline-block;">
                <div class="balance-main" id="total-val">0</div>
                <div id="fx-container"></div>
            </div>
            <div id="u-rank" style="color:var(--gold); font-size:11px; font-weight:bold; letter-spacing:2px; margin-bottom:20px;">🆕 SEEKER</div>

            <div class="token-grid">
                <div class="token-box" onclick="tg.openLink('{LINK_GENESIS}')"><div id="bal-g" style="font-weight:bold;">0</div><div style="font-size:8px; color:var(--gold);">GENESIS</div></div>
                <div class="token-box" onclick="tg.openLink('{LINK_UNITY}')"><div id="bal-u" style="font-weight:bold;">0</div><div style="font-size:8px; color:var(--gold);">UNITY</div></div>
                <div class="token-box" onclick="tg.openLink('{LINK_VEO}')"><div id="bal-v" style="font-weight:bold;">0.00</div><div style="font-size:8px; color:var(--gold);">VEO AI</div></div>
            </div>

            <div class="pillar">
                <div style="font-size:24px; margin-right:15px;">🏺</div>
                <div style="flex-grow:1;"><b>GENESIS GRANT</b><br><small opacity:0.6>Claim daily +200 OWPC</small></div>
                <button class="btn-action" onclick="claim(event)">CLAIM</button>
            </div>
        </div>

        <div id="friends" class="page">
            <h2 style="color:var(--gold);">HIVE NETWORK</h2>
            <div class="pillar" style="flex-direction:column; text-align:center;">
                <div id="ref-count" style="font-size:40px; font-weight:bold; margin-bottom:10px;">0</div>
                <p>Commanders joined your network.</p>
            </div>
            <button class="btn-action" style="width:100%" onclick="tg.openTelegramLink('https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start='+uid+'&text=Join the OWPC Hive Network!')">INVITE FRIENDS</button>
        </div>

        <div id="roadmap" class="page">
            <h2 style="color:var(--gold);">PROTOCOL ROADMAP</h2>
            <div style="text-align:left; padding:0 20px; border-left:2px solid var(--gold); margin-left:10px;">
                <p style="margin-bottom:25px;"><b>PHASE 1: HIVE START</b><br><small>Terminal Launch & Genesis Mining (LIVE)</small></p>
                <p style="margin-bottom:25px;"><b>PHASE 2: UNITY SYNC</b><br><small>Investment multipliers & Community Tasks.</small></p>
                <p><b>PHASE 3: EVOLUTION</b><br><small>Listing & DEX deployment.</small></p>
            </div>
        </div>

        <nav class="nav-bar">
            <div class="nav-item active" id="n-home" onclick="showPage('home','n-home')">🏠<br>Hive</div>
            <div class="nav-item" id="n-ref" onclick="showPage('friends','n-ref')">👥<br>Friends</div>
            <div class="nav-item" id="n-road" onclick="showPage('roadmap','n-road')">📍<br>Roadmap</div>
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

            function loadData() {{
                fetch('/api/user/'+uid).then(r=>r.json()).then(d=>{{
                    // FIX: Don't reset if local mining is ahead
                    state.g = d.genesis;
                    state.u = d.unity;
                    if (d.veo > state.v) state.v = d.veo;
                    
                    document.getElementById('u-rank').innerText = d.rank;
                    document.getElementById('ref-count').innerText = d.refs;
                    updateUI();
                }});
                fetch('/api/stats').then(r=>r.json()).then(s=>{{
                    document.getElementById('st-users').innerText = s.user_count.toLocaleString();
                    document.getElementById('st-total').innerText = s.total_claimed.toLocaleString();
                }});
            }}

            function claim(e) {{
                fetch('/api/claim_genesis/'+uid, {{method:'POST'}}).then(r=>r.json()).then(d=>{{
                    const fx = document.createElement('div');
                    fx.className = 'float-text';
                    fx.innerText = '+200';
                    document.getElementById('fx-container').appendChild(fx);
                    setTimeout(() => fx.remove(), 1000);
                    
                    tg.HapticFeedback.notificationOccurred('success');
                    loadData();
                }});
            }}

            function showPage(p,n) {{
                document.querySelectorAll('.page').forEach(x=>x.classList.remove('active-page'));
                document.querySelectorAll('.nav-item').forEach(x=>x.classList.remove('active'));
                document.getElementById(p).classList.add('active-page');
                document.getElementById(n).classList.add('active');
            }}

            setInterval(() => {{ state.v += 0.01; updateUI(); }}, 1000);
            setInterval(loadData, 30000); 
            loadData();
        </script>
    </body>
    </html>
    """

# --- 🤖 BOT LOGIC ---
async def run_bot():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    
    async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (u.effective_user.id, u.effective_user.first_name))
        conn.commit(); conn.close()
        
        await u.message.reply_text(
            f"🕊️ **OWPC TERMINAL**\n\nWelcome Commander {u.effective_user.first_name}.\nAccess your assets below.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]]),
            parse_mode="Markdown"
        )

    bot.add_handler(CommandHandler("start", start))
    async with bot:
        await bot.initialize(); await bot.start(); await bot.updater.start_polling()
        while True: await asyncio.sleep(1)

@app.on_event("startup")
async def startup(): asyncio.create_task(run_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
