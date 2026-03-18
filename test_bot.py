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

# --- 📊 DB LOGIC (Initialisation propre des colonnes) ---
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
    c.execute("SELECT points_genesis, points_unity, points_veo, last_checkin, rank FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close()
    if res:
        total = int(res[0] + res[1] + res[2])
        return {"genesis": res[0], "unity": res[1], "veo": res[2], "total": total, "last_checkin": res[3], "rank": res[4]}
    return {"genesis": 0, "unity": 0, "veo": 0.0, "total": 0, "last_checkin": None, "rank": "🆕 SEEKER"}

# --- 🔌 API ---
@app.get("/api/user/{user_id}")
async def api_user(user_id: int): return JSONResponse(content=get_user_data(user_id))

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
            body {{ background: var(--bg); color: white; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 0; text-align: center; }}
            
            .header {{ padding: 15px; border-bottom: 1px solid rgba(212,175,55,0.1); margin-bottom: 10px; }}
            .brand-title {{ font-size: 14px; font-weight: bold; color: var(--gold); letter-spacing: 4px; }}
            
            .balance-main {{ font-size: 50px; font-weight: 800; margin: 5px 0; }}
            .rank-text {{ font-size: 12px; color: var(--gold); font-weight: bold; letter-spacing: 1px; margin-bottom: 20px; }}

            .token-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; padding: 0 20px; margin-bottom: 25px; }}
            .token-box {{ background: var(--card); padding: 12px 5px; border-radius: 15px; border: 1px solid rgba(212,175,55,0.1); }}
            .token-val {{ font-weight: bold; color: white; font-size: 14px; }}
            .token-label {{ font-size: 9px; color: var(--gold); text-transform: uppercase; margin-top: 4px; }}

            .pillar {{ background: var(--card); border-radius: 20px; padding: 18px; margin: 10px 20px; display: flex; align-items: center; text-align: left; border: 1px solid rgba(212,175,55,0.05); }}
            .pillar-icon {{ font-size: 24px; margin-right: 15px; }}
            .btn-claim {{ background: var(--gold); color: black; border: none; padding: 10px 15px; border-radius: 12px; font-weight: bold; font-size: 11px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="brand-title">OWPC TERMINAL</div>
        </div>

        <div class="balance-main" id="total-val">0</div>
        <div id="u-rank" class="rank-text">🆕 SEEKER</div>

        <div class="token-grid">
            <div class="token-box">
                <div class="token-val" id="bal-g">0</div>
                <div class="token-label">Genesis</div>
            </div>
            <div class="token-box">
                <div class="token-val" id="bal-u">0</div>
                <div class="token-label">Unity</div>
            </div>
            <div class="token-box">
                <div class="token-val" id="bal-v">0.00</div>
                <div class="token-label">Veo AI</div>
            </div>
        </div>

        <div class="pillar">
            <div class="pillar-icon">🏺</div>
            <div style="flex-grow: 1;"><b>GENESIS</b><br><small style="opacity:0.6;">Daily Grant</small></div>
            <button class="btn-claim" onclick="claim()">CLAIM</button>
        </div>

        <div class="pillar">
            <div class="pillar-icon">🤖</div>
            <div style="flex-grow: 1;"><b>VEO AI MINING</b><br><small style="color:var(--green);">SYNC ACTIVE (+0.01/s)</small></div>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            const uid = tg.initDataUnsafe.user.id;
            let state = {{ g: 0, u: 0, v: 0.0 }};

            function updateDisplay() {{
                document.getElementById('bal-g').innerText = Math.floor(state.g).toLocaleString();
                document.getElementById('bal-u').innerText = Math.floor(state.u).toLocaleString();
                document.getElementById('bal-v').innerText = state.v.toFixed(2);
                document.getElementById('total-val').innerText = Math.floor(state.g + state.u + state.v).toLocaleString();
            }}

            function sync() {{
                fetch('/api/user/' + uid).then(r => r.json()).then(data => {{
                    state.g = data.genesis; state.u = data.unity; state.v = data.veo;
                    document.getElementById('u-rank').innerText = data.rank;
                    updateDisplay();
                }});
            }}

            // Farming temps réel (visuel)
            setInterval(() => {{
                state.v += 0.01;
                updateDisplay();
            }}, 1000);

            // Sync Database (réel) toutes les 30s
            setInterval(() => {{
                fetch(`/api/sync_veo/${{uid}}/0.30`, {{ method: 'POST' }});
            }}, 30000);

            tg.expand();
            sync();
        </script>
    </body>
    </html>
    """

# --- BOT & SERVER ---
async def start_bot():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("🕊️ **OWPC TERMINAL**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]]), parse_mode="Markdown")))
    async with bot:
        await bot.initialize(); await bot.start(); await bot.updater.start_polling()
        while True: await asyncio.sleep(1)

@app.on_event("startup")
async def startup(): asyncio.create_task(start_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
