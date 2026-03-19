import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = "OWPCsbot"

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "owpc_data.db")

app = FastAPI()
logging.basicConfig(level=logging.INFO)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Table Utilisateurs étendue
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0, points_unity REAL DEFAULT 0, 
                  points_veo REAL DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0,
                  last_task_date TEXT)''')
    conn.commit(); conn.close()

# --- BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (uid, name, ref_id))
        if ref_id and ref_id != uid:
            c.execute("UPDATE users SET points_unity = points_unity + 10.0, ref_count = ref_count + 1 WHERE user_id = ?", (ref_id,))
    conn.commit(); conn.close()

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 LAUNCH OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC Ecosystem.\nAll systems are green.", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user_api(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, ref_count FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    # Récupérer le TOP 3 pour le leaderboard
    c.execute("SELECT name, points_genesis FROM users ORDER BY points_genesis DESC LIMIT 3")
    top = [{"n": x[0], "p": round(x[1],2)} for x in c.fetchall()]
    conn.close()
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "top": top} if r else {"g":0,"u":0,"v":0,"rc":0, "top":[]}

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    col = {"genesis":"points_genesis", "unity":"points_unity", "veo":"points_veo"}.get(t)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET {col} = {col} + ? WHERE user_id = ?", (gain, uid))
    conn.commit(); conn.close()
    return {"ok": True}

# --- WEB UI (Premium & Multitâches) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {{ --g: #00ff88; --u: #fff; --v: #00d9ff; --bg: #080c14; --card: #121826; }}
            body {{ background: var(--bg); color: #fff; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 15px; padding-bottom: 80px; }}
            
            .tab-btn {{ background: none; border: none; color: #666; font-weight: bold; padding: 10px; font-size: 14px; cursor: pointer; }}
            .tab-btn.active {{ color: var(--g); border-bottom: 2px solid var(--g); }}
            
            .card {{ background: var(--card); border: 1px solid rgba(255,255,255,0.05); border-radius: 16px; padding: 15px; margin-bottom: 12px; }}
            .val {{ font-size: 24px; font-weight: 800; font-family: monospace; }}
            
            .btn-action {{ width: 100%; padding: 12px; border-radius: 12px; border: none; font-weight: bold; cursor: pointer; margin-top: 10px; transition: 0.2s; }}
            .btn-mine {{ background: var(--g); color: #000; }}
            .btn-task {{ background: #252f44; color: #fff; text-align: left; display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
            
            .footer {{ position: fixed; bottom: 0; left: 0; right: 0; background: #111; display: flex; justify-content: space-around; padding: 10px; border-top: 1px solid #222; }}
            .nav-item {{ font-size: 10px; color: #888; text-decoration: none; display: flex; flex-direction: column; align-items: center; }}
            
            .leader-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #222; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <h3 style="margin:0; color:var(--v)">OWPC HUB</h3>
            <div style="background:gold; color:000; padding:2px 8px; border-radius:10px; font-size:12px; font-weight:bold">⭐️ <span id="ref_count">0</span></div>
        </div>

        <div id="section-mine">
            <div class="card" style="border-left: 4px solid var(--g)">
                <div style="font-size:11px; color:#aaa">GENESIS BALANCE</div>
                <div class="val" style="color:var(--g)" id="g_val">0.00</div>
                <button class="btn-action btn-mine" onclick="mine('genesis', this)">MINE GENESIS</button>
            </div>
            
            <div class="card">
                <div style="font-size:11px; color:#aaa">DAILY TASKS</div>
                <button class="btn-action btn-task" onclick="window.open('https://t.me/BlumCryptoBot')">1. Join Blum Crypto <span>+5.0 G</span></button>
                <button class="btn-action btn-task" onclick="tg.openTelegramLink('https://t.me/YourChannel')">2. Subscribe Channel <span>+2.0 G</span></button>
                <button class="btn-action btn-task" style="background:var(--v); color:#000" onclick="donate()">💝 DONATE STARS (SUPPORT)</button>
            </div>
        </div>

        <div id="section-top" style="display:none">
            <div class="card">
                <div style="font-size:12px; color:gold; margin-bottom:10px">🏆 GLOBAL RANKING</div>
                <div id="leaderboard-list"></div>
                <button class="btn-action" style="background:#fff; color:#000; margin-top:15px" onclick="share()">INVITE FRIENDS (+10 UNITY)</button>
            </div>
        </div>

        <div class="footer">
            <div class="nav-item" onclick="showTab('mine')" style="color:var(--g)">⛏️<br>Mining</div>
            <div class="nav-item" onclick="showTab('top')">🏆<br>Top</div>
            <div class="nav-item" onclick="tg.close()">❌<br>Exit</div>
        </div>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;

            async function refresh() {{
                if(!uid) return;
                const r = await fetch('/api/user/' + uid);
                const d = await r.json();
                document.getElementById('g_val').innerText = d.g.toFixed(2);
                document.getElementById('ref_count').innerText = d.rc;
                
                let html = "";
                d.top.forEach((u, i) => {{
                    html += `<div class="leader-row"><span>${{i+1}}. ${{u.n}}</span><span style="color:var(--g)">${{u.p}} G</span></div>`;
                }});
                document.getElementById('leaderboard-list').innerHTML = html;
            }}

            async function mine(t, btn) {{
                tg.HapticFeedback.impactOccurred('medium');
                await fetch('/api/mine', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{user_id: uid, token: t}})
                }});
                refresh();
            }}

            function showTab(t) {{
                document.getElementById('section-mine').style.display = (t==='mine'?'block':'none');
                document.getElementById('section-top').style.display = (t==='top'?'block':'none');
            }}

            function share() {{
                const url = `https://t.me/{BOT_USERNAME}?start=${{uid}}`;
                tg.openTelegramLink(`https://t.me/share/url?url=${{encodeURIComponent(url)}}&text=Join the OWPC mining revolution!`);
            }}

            function donate() {{
                // Note: La gestion des Stars nécessite une intégration côté Bot (Payment)
                tg.showAlert("Merci ! Pour donner des Stars, utilisez le menu du Bot Telegram.");
            }}

            refresh();
            setInterval(refresh, 8000);
        </script>
    </body>
    </html>
    """

async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
