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
from telegram.error import TelegramError

nest_asyncio.apply()

# --- ⚙️ CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.environ.get("PORT", 8080))
WEBAPP_URL = "https://veos-production.up.railway.app" 
DB_NAME = "owpc_data.db"
CHANNEL_ID = "@owpc_co" # Ton canal officiel

app = FastAPI()

# --- 📊 DB LOGIC ---
def get_user_data(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT points, rank, last_checkin FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return {"points": res[0], "rank": res[1], "last_checkin": res[2]} if res else {"points": 0, "rank": "NEWBIE", "last_checkin": None}

# --- 🔌 API ---
@app.get("/api/check_membership/{user_id}")
async def check_membership(user_id: int):
    # Note: Cette partie nécessite que le bot soit ADMIN du canal
    try:
        bot = ApplicationBuilder().token(TOKEN).build().bot
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return {"status": "member"}
    except Exception:
        pass
    return {"status": "not_member"}

@app.get("/api/user/{user_id}")
async def api_user(user_id: int): return JSONResponse(content=get_user_data(user_id))

@app.post("/api/daily/{user_id}")
async def daily_checkin(user_id: int):
    data = get_user_data(user_id)
    today = date.today().isoformat()
    if data["last_checkin"] == today: return {"status": "already_done"}
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET points = points + 200, last_checkin = ? WHERE user_id = ?", (today, user_id))
    conn.commit(); conn.close()
    return {"status": "success"}

# --- 🌐 INTERFACE (Branding OWPC + Gate) ---
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
            
            /* ACCESS DENIED OVERLAY */
            #gate-overlay {{ 
                position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                background: var(--bg); z-index: 9999; display: flex; flex-direction: column; 
                justify-content: center; align-items: center; padding: 20px; box-sizing: border-box;
            }}
            .lock-icon {{ font-size: 60px; margin-bottom: 20px; color: var(--red); }}

            .page {{ display: none; padding: 20px; padding-bottom: 100px; animation: fadeIn 0.3s; height: 100vh; overflow-y: auto; }}
            .active-page {{ display: block; }}
            
            .brand-title {{ font-size: 14px; font-weight: bold; color: var(--gold); letter-spacing: 2px; margin-top: 10px; }}
            .brand-sub {{ font-size: 10px; opacity: 0.5; margin-bottom: 20px; }}

            .pillar-card {{ background: var(--card); border: 1px solid rgba(212,175,55,0.1); border-radius: 20px; padding: 15px; margin-bottom: 12px; display: flex; align-items: center; text-align: left; }}
            .balance {{ font-size: 48px; font-weight: 800; margin: 5px 0; }}
            .nav-bar {{ position: fixed; bottom: 0; width: 100%; background: #12121f; display: flex; justify-content: space-around; padding: 15px 0; border-top: 1px solid rgba(255,255,255,0.05); }}
            
            .btn-action {{ background: var(--gold); color: black; border: none; padding: 12px 20px; border-radius: 12px; font-weight: bold; cursor: pointer; text-decoration: none; display: inline-block; }}
        </style>
    </head>
    <body>

        <div id="gate-overlay">
            <div class="lock-icon">🔒</div>
            <h2 style="color: var(--red);">ACCESS DENIED</h2>
            <p style="opacity: 0.7; font-size: 14px;">You must be a member of our official community to access the OWPC HIVE.</p>
            <br>
            <a href="https://t.me/owpc_co" class="btn-action" onclick="tg.openTelegramLink('https://t.me/owpc_co')">JOIN COMMUNITY</a>
            <br>
            <button style="background:none; border:none; color:var(--gold); cursor:pointer;" onclick="checkAccess()">[ Verify Membership ]</button>
        </div>

        <div id="main-content" style="display:none;">
            <div class="brand-title">ONE WORLD PEACE COINS</div>
            <div class="brand-sub">THE GLOBAL HIVE PROTOCOL</div>

            <div id="home" class="page active-page">
                <h3 id="u-name" style="margin: 0;">COMMANDER</h3>
                <div class="balance" id="u-points">0</div>
                <div style="font-size: 10px; opacity: 0.5; letter-spacing: 2px; margin-bottom: 20px;">TOTAL OWPC CREDITS</div>
                
                <div class="pillar-card">
                    <div style="font-size: 24px; margin-right: 15px;">🏺</div>
                    <div style="flex-grow: 1;">
                        <div style="font-weight: bold; color: var(--gold);">GENESIS</div>
                        <div style="font-size: 11px; opacity: 0.6;">Collect Daily Peace Coins.</div>
                    </div>
                    <button class="btn-action" onclick="claimDaily()">CLAIM</button>
                </div>

                <div class="pillar-card" onclick="showPage('tasks', document.getElementById('nav-tasks'))">
                    <div style="font-size: 24px; margin-right: 15px;">🌍</div>
                    <div style="flex-grow: 1;">
                        <div style="font-weight: bold; color: var(--gold);">UNITY</div>
                        <div style="font-size: 11px; opacity: 0.6;">Missions & Community.</div>
                    </div>
                </div>
            </div>

            <div id="tasks" class="page">
                <h2 style="color: var(--gold);">MISSIONS</h2>
                <div class="pillar-card">
                    <div style="flex-grow: 1;">
                        <div style="font-weight: bold;">DeepTradeX X-Protocol</div>
                        <div style="font-size: 11px; color: var(--gold);">+1,000 OWPC</div>
                    </div>
                    <button class="btn-action" onclick="tg.openLink('https://x.com/DeepTradeX')">GO</button>
                </div>
            </div>

            <nav class="nav-bar">
                <div class="nav-item active" onclick="showPage('home', this)">🏠<br>Home</div>
                <div id="nav-tasks" class="nav-item" onclick="showPage('tasks', this)">💠<br>Tasks</div>
            </nav>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            const user = tg.initDataUnsafe.user;
            tg.expand();

            async function checkAccess() {{
                const res = await fetch('/api/check_membership/' + user.id);
                const data = await res.json();
                if (data.status === 'member') {{
                    document.getElementById('gate-overlay').style.display = 'none';
                    document.getElementById('main-content').style.display = 'block';
                    refresh();
                }} else {{
                    tg.HapticFeedback.notificationOccurred('error');
                    tg.showAlert("Access Denied. Join the group first!");
                }}
            }}

            function showPage(pId, el) {{
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));
                document.getElementById(pId).classList.add('active-page');
                tg.HapticFeedback.impactOccurred('medium');
            }}

            function refresh() {{
                fetch('/api/user/' + user.id).then(r => r.json()).then(data => {{
                    document.getElementById('u-points').innerText = data.points.toLocaleString();
                    document.getElementById('u-name').innerText = user.first_name.toUpperCase();
                }});
            }}

            function claimDaily() {{
                fetch('/api/daily/' + user.id, {{ method: 'POST' }}).then(r => r.json()).then(data => {{
                    if(data.status == 'already_done') tg.showAlert("Protocol Genesis: Already claimed.");
                    else {{ tg.HapticFeedback.notificationOccurred('success'); refresh(); }}
                }});
            }}

            checkAccess();
        </script>
    </body>
    </html>
    """

# --- BOT ---
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Enter HIVE Terminal", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await u.message.reply_text("🕊️ **One World Peace Coins**\n\nAuthorized Access Only.", reply_markup=kb, parse_mode="Markdown")

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
