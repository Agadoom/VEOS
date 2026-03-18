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

# --- 📊 DB LOGIC (Updated for Multi-Tokens) ---
def init_db():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis INTEGER DEFAULT 0,
                  points_unity INTEGER DEFAULT 0,
                  points_veo REAL DEFAULT 0.0,
                  rank TEXT DEFAULT '🆕 SEEKER', last_checkin TEXT DEFAULT '')''')
    conn.commit(); conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, last_checkin FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close()
    if res:
        total = res[0] + res[1] + int(res[2])
        return {"genesis": res[0], "unity": res[1], "veo": res[2], "total": total, "last_checkin": res[3]}
    return {"genesis": 0, "unity": 0, "veo": 0.0, "total": 0, "last_checkin": None}

# --- 🔌 API ---
@app.post("/api/sync_veo/{user_id}/{amount}")
async def sync_veo(user_id: int, amount: float):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (amount, user_id))
    conn.commit(); conn.close()
    return {"status": "synced"}

@app.post("/api/claim_genesis/{user_id}")
async def claim_genesis(user_id: int):
    today = date.today().isoformat()
    data = get_user_data(user_id)
    if data["last_checkin"] == today: return {"status": "already_claimed"}
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE users SET points_genesis = points_genesis + 200, last_checkin = ? WHERE user_id = ?", (today, user_id))
    conn.commit(); conn.close()
    return {"status": "success"}

@app.get("/api/user/{user_id}")
async def api_user(user_id: int): return JSONResponse(content=get_user_data(user_id))

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
            body {{ background: var(--bg); color: white; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 0; text-align: center; }}
            .header {{ padding: 20px; border-bottom: 1px solid rgba(212,175,55,0.2); }}
            .title {{ font-size: 16px; font-weight: bold; color: var(--gold); letter-spacing: 3px; }}
            
            .total-balance {{ font-size: 48px; font-weight: 800; margin: 10px 0; }}
            .token-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; padding: 0 20px; margin-bottom: 20px; }}
            .token-box {{ background: var(--card); padding: 10px; border-radius: 12px; border: 1px solid rgba(212,175,55,0.1); }}
            .token-val {{ font-weight: bold; color: var(--gold); font-size: 14px; }}
            .token-lab {{ font-size: 9px; opacity: 0.6; text-transform: uppercase; }}

            .pillar-card {{ background: var(--card); border-radius: 20px; padding: 18px; margin: 10px 20px; display: flex; align-items: center; text-align: left; border: 1px solid rgba(212,175,55,0.1); }}
            .btn-claim {{ background: var(--gold); color: black; border: none; padding: 8px 15px; border-radius: 10px; font-weight: bold; font-size: 12px; }}
            
            .nav-bar {{ position: fixed; bottom: 0; width: 100%; background: #12121f; display: flex; justify-content: space-around; padding: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="title">OWPC TERMINAL</div>
        </div>

        <div class="total-balance" id="total-pts">0</div>
        <div style="font-size: 10px; opacity: 0.5; margin-bottom: 20px;">TOTAL OWPC ASSETS</div>

        <div class="token-grid">
            <div class="token-box">
                <div class="token-val" id="val-genesis">0</div>
                <div class="token-lab">Genesis</div>
            </div>
            <div class="token-box">
                <div class="token-val" id="val-unity">0</div>
                <div class="token-lab">Unity</div>
            </div>
            <div class="token-box">
                <div class="token-val" id="val-veo">0.00</div>
                <div class="token-lab">Veo AI</div>
            </div>
        </div>

        <div class="pillar-card">
            <div style="font-size: 24px; margin-right: 15px;">🏺</div>
            <div style="flex-grow: 1;"><b>GENESIS PROTOCOL</b><br><small>Daily synchronisation.</small></div>
            <button class="btn-claim" onclick="claimG()">CLAIM</button>
        </div>

        <div class="pillar-card">
            <div style="font-size: 24px; margin-right: 15px;">🤖</div>
            <div style="flex-grow: 1;"><b>VEO AI MINER</b><br><small style="color:var(--green)">MINING ACTIVE...</small></div>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            const uid = tg.initDataUnsafe.user.id;
            let bal = {{ g:0, u:0, v:0.0 }};

            function updateUI() {{
                document.getElementById('val-genesis').innerText = bal.g.toLocaleString();
                document.getElementById('val-unity').innerText = bal.u.toLocaleString();
                document.getElementById('val-veo').innerText = bal.v.toFixed(2);
                document.getElementById('total-pts').innerText = Math.floor(bal.g + bal.u + bal.v).toLocaleString();
            }}

            function load() {{
                fetch('/api/user/'+uid).then(r=>r.json()).then(data=>{{
                    bal.g = data.genesis; bal.u = data.unity; bal.v = data.veo;
                    updateUI();
                }});
            }}

            function claimG() {{
                fetch('/api/claim_genesis/'+uid, {{method:'POST'}}).then(r=>r.json()).then(d=>{{
                    if(d.status=='success') {{ tg.HapticFeedback.notificationOccurred('success'); load(); }}
                    else tg.showAlert("Already synced for today.");
                }});
            }}

            // Farming VEO en temps réel
            setInterval(() => {{
                bal.v += 0.01;
                updateUI();
            }}, 1000);

            // Sync DB toutes les 30s
            setInterval(() => {{
                fetch(`/api/sync_veo/${{uid}}/0.30`, {{method:'POST'}});
            }}, 30000);

            load();
            tg.expand();
        </script>
    </body>
    </html>
    """

# --- BOT ---
async def start_bot():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("🕊️ OWPC HIVE", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN", web_app=WebAppInfo(url=WEBAPP_URL))]]))))
    async with bot:
        await bot.initialize(); await bot.start(); await bot.updater.start_polling()
        while True: await asyncio.sleep(1)

@app.on_event("startup")
async def startup(): asyncio.create_task(start_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
