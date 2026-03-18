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
TOKEN = os.getenv("TOKEN") # Assure-toi que c'est le Token de @OWPCsbot dans Railway
PORT = int(os.environ.get("PORT", 8080))
WEBAPP_URL = "https://veos-production.up.railway.app" 
DB_NAME = "owpc_data.db"

app = FastAPI()

# --- 📊 LOGIQUE BASE DE DONNÉES ---
def get_user_data(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT points, rank FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return {"points": result[0], "rank": result[1]} if result else {"points": 0, "rank": "NEWBIE"}
    except: return {"points": 0, "rank": "NEWBIE"}

def update_user_points(user_id, amount):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
        conn.commit(); conn.close()
        return True
    except: return False

# --- 🔌 API POUR LA MINI APP ---
@app.get("/api/user/{user_id}")
async def api_user(user_id: int): return JSONResponse(content=get_user_data(user_id))

@app.post("/api/task/complete")
async def complete_task(data: dict):
    if update_user_points(data.get("user_id"), data.get("reward", 500)):
        return {"status": "success"}
    return {"status": "error"}

# --- 🌐 INTERFACE MINI APP (DESIGN PREMIUM) ---
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
            body {{ background: var(--bg); color: white; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 0; overflow: hidden; }}
            .page {{ display: none; padding: 20px; padding-bottom: 100px; height: 100vh; box-sizing: border-box; overflow-y: auto; }}
            .active-page {{ display: block; animation: fadeIn 0.4s ease-out; }}
            @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}

            .balance {{ font-size: 52px; font-weight: 800; margin: 10px 0; color: white; }}
            .progress-container {{ background: rgba(255,255,255,0.1); height: 6px; border-radius: 10px; margin: 15px 40px; overflow: hidden; }}
            .progress-bar {{ background: var(--gold); height: 100%; width: 35%; box-shadow: 0 0 10px var(--gold); }}

            .pillar-card {{
                background: linear-gradient(145deg, #1a1a2e, #161626);
                border: 1px solid rgba(212,175,55,0.1);
                border-radius: 24px; padding: 18px; margin-bottom: 15px;
                display: flex; align-items: center; text-align: left;
            }}
            .pillar-icon {{ font-size: 26px; margin-right: 15px; }}
            .pillar-title {{ font-weight: 800; color: var(--gold); font-size: 15px; }}
            .pillar-desc {{ font-size: 11px; opacity: 0.6; }}

            .task-btn {{ background: var(--gold); color: black; border: none; padding: 10px 18px; border-radius: 12px; font-weight: bold; font-size: 13px; }}
            .task-btn.loading {{ background: #333; color: #777; }}

            .nav-bar {{
                position: fixed; bottom: 0; width: 100%; background: rgba(18, 18, 31, 0.98);
                display: flex; justify-content: space-around; padding: 15px 0; border-top: 1px solid rgba(255,255,255,0.05);
            }}
            .nav-item {{ color: #555; font-size: 10px; cursor: pointer; text-transform: uppercase; }}
            .nav-item.active {{ color: var(--gold); font-weight: bold; }}
        </style>
    </head>
    <body>
        <div id="home" class="page active-page">
            <div style="font-weight: bold; letter-spacing: 2px; color: var(--gold); font-size: 11px; margin-top: 10px;">OWPC COMMANDER</div>
            <h2 id="u-name" style="margin: 5px 0 15px 0;">...</h2>
            
            <div class="balance" id="u-points">0</div>
            <div style="font-size: 11px; opacity: 0.5; letter-spacing: 2px;">TOTAL CREDITS</div>

            <div class="progress-container"><div class="progress-bar" id="p-bar"></div></div>
            <div id="u-rank" style="font-size: 12px; font-weight: bold; color: var(--gold);">RANK</div>

            <div style="margin-top: 25px;">
                <div class="pillar-card"><div class="pillar-icon">🏺</div><div class="pillar-info"><div class="pillar-title">GENESIS</div><div class="pillar-desc">Core protocols engaged.</div></div></div>
                <div class="pillar-card" onclick="showPage('tasks', document.getElementById('nav-tasks'))"><div class="pillar-icon">🌍</div><div class="pillar-info"><div class="pillar-title">UNITY</div><div class="pillar-desc">Expand and earn.</div></div></div>
                <div class="pillar-card" style="border-color: var(--veo); opacity: 0.8;"><div class="pillar-icon">🤖</div><div class="pillar-info"><div class="pillar-title" style="color: var(--veo);">VEO</div><div class="pillar-desc">AI modules loading...</div></div></div>
            </div>
        </div>

        <div id="tasks" class="page">
            <h2 style="letter-spacing: 2px; color: var(--gold);">MISSIONS</h2>
            <div class="pillar-card">
                <div class="pillar-info"><div class="pillar-title">Follow DeepTradeX</div><div class="pillar-desc">+1,000 CREDITS</div></div>
                <button id="btn-x" class="task-btn" onclick="runTask('btn-x', 1000, 'https://x.com/DeepTradeX')">GO</button>
            </div>
            <div class="pillar-card">
                <div class="pillar-info"><div class="pillar-title">Join Channel</div><div class="pillar-desc">+500 CREDITS</div></div>
                <button id="btn-tg" class="task-btn" onclick="runTask('btn-tg', 500, 'https://t.me/owpc_co')">GO</button>
            </div>
        </div>

        <nav class="nav-bar">
            <div class="nav-item active" onclick="showPage('home', this)">🏠<br>Home</div>
            <div class="nav-item" id="nav-tasks" onclick="showPage('tasks', this)">💠<br>Pillars</div>
            <div class="nav-item" onclick="tg.showAlert('Leaderboard coming soon...')">🏆<br>Rank</div>
        </nav>

        <script>
            let tg = window.Telegram.WebApp;
            const user = tg.initDataUnsafe.user;
            tg.expand();

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
                    document.getElementById('u-rank').innerText = data.rank.toUpperCase();
                    document.getElementById('u-name').innerText = user.first_name.toUpperCase();
                    let prog = (data.points % 5000) / 50;
                    document.getElementById('p-bar').style.width = prog + "%";
                }});
            }}

            function runTask(btnId, reward, url) {{
                let btn = document.getElementById(btnId);
                tg.HapticFeedback.impactOccurred('heavy');
                tg.openLink(url);
                btn.innerText = "WAIT..."; btn.classList.add('loading'); btn.disabled = true;
                setTimeout(() => {{
                    fetch('/api/task/complete', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ user_id: user.id, reward: reward }})
                    }}).then(() => {{
                        btn.innerText = "DONE ✅";
                        tg.HapticFeedback.notificationOccurred('success');
                        refresh();
                    }});
                }}, 4000);
            }}
            refresh();
        </script>
    </body>
    </html>
    """

# --- 🤖 BOT START LOGIC ---
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Launch OWPC HIVE", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📢 Official Channel", url="https://t.me/owpc_co")]
    ])
    await u.message.reply_text(
        "🕊️ **Welcome to OWPC HIVE**\n\n"
        "Accédez à votre terminal de commande Genesis via le bouton ci-dessous.", 
        reply_markup=kb, parse_mode="Markdown"
    )

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
