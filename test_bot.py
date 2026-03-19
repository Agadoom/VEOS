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
DB_PATH = os.path.join(DATA_DIR, "owpc_pro.db")

logging.basicConfig(level=logging.INFO)
app = FastAPI()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  p_genesis REAL DEFAULT 0, p_unity REAL DEFAULT 0, 
                  p_veo REAL DEFAULT 0, ref_count INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

# --- BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    conn.commit(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC Ecosystem, {name}.", reply_markup=kb)

# --- API ---
@app.get("/api/user/{{uid}}")
async def get_user(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return {{"g": r[0], "u": r[1], "v": r[2], "rc": r[3]}} if r else None

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    col = {{"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}}.get(t)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET {{col}} = {{col}} + ? WHERE user_id = ?", (gain, uid))
    conn.commit(); conn.close()
    return {{"ok": True}}

# --- UI RÉALISTE (NEUMORPHISM) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {{ --bg: #f0f2f5; --text: #1c1e21; --blue: #007bff; --glass: rgba(255, 255, 255, 0.7); }}
            body {{ background: var(--bg); color: var(--text); font-family: 'Poppins', sans-serif; margin: 0; padding: 20px; }}
            
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; }}
            .logo {{ font-weight: 800; font-size: 20px; color: var(--blue); }}
            
            .token-card {{ 
                background: white; border-radius: 24px; padding: 20px; margin-bottom: 15px;
                box-shadow: 10px 10px 20px #d1d9e6, -10px -10px 20px #ffffff;
                transition: transform 0.2s;
            }}
            .token-card:active {{ transform: scale(0.98); box-shadow: inset 5px 5px 10px #d1d9e6, inset -5px -5px 10px #ffffff; }}
            
            .label {{ font-size: 12px; color: #65676b; font-weight: 600; text-transform: uppercase; }}
            .value {{ font-size: 32px; font-weight: 800; margin: 5px 0; color: #050505; }}
            
            .btn-mine {{ 
                background: var(--blue); color: white; border: none; padding: 12px 20px; 
                border-radius: 12px; font-weight: bold; width: 100%; cursor: pointer; margin-top: 10px;
            }}

            .nav {{ position: fixed; bottom: 20px; left: 20px; right: 20px; background: var(--glass); backdrop-filter: blur(10px); border-radius: 20px; display: flex; justify-content: space-around; padding: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
            .nav-item {{ font-size: 20px; cursor: pointer; }}
            
            .task-btn {{ background: #e4e6eb; color: #050505; padding: 15px; border-radius: 15px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; text-decoration: none; font-weight: 600; }}
        </style>
    </head>
    <body>
        <div id="p-home">
            <div class="header"><div class="logo">OWPC HUB</div><div id="user-tag" style="font-size:12px; font-weight:600">PRO</div></div>
            
            <div class="token-card">
                <div class="label">Genesis Token</div>
                <div class="value" id="gv">0.00</div>
                <button class="btn-mine" onclick="mine('genesis')">Mine Genesis</button>
            </div>

            <div class="token-card">
                <div class="label">Unity Core</div>
                <div class="value" id="uv">0.00</div>
                <button class="btn-mine" style="background:#28a745" onclick="mine('unity')">Harvest Unity</button>
            </div>

            <div class="token-card">
                <div class="label">Veo AI</div>
                <div class="value" id="vv">0.00</div>
                <button class="btn-mine" style="background:#6f42c1" onclick="mine('veo')">Compute AI</button>
            </div>
        </div>

        <div id="p-tasks" style="display:none">
            <h2>Community Tasks</h2>
            <a href="https://t.me/BlumCryptoBot" class="task-btn"><span>🌱 Join Blum</span><span>+5.0</span></a>
            <a href="https://t.me/OWPC_Official" class="task-btn"><span>📢 Official Channel</span><span>+2.0</span></a>
            <div class="task-btn" onclick="donate()" style="background:gold"><span>⭐ Support with Stars</span><span>BUY</span></div>
        </div>

        <div class="nav">
            <div onclick="show('home')" class="nav-item">🏠</div>
            <div onclick="show('tasks')" class="nav-item">📋</div>
            <div onclick="tg.close()" class="nav-item">🚪</div>
        </div>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;

            async function refresh() {{
                if(!uid) return;
                const r = await fetch('/api/user/' + uid);
                const d = await r.json();
                if(d) {{
                    document.getElementById('gv').innerText = d.g.toFixed(2);
                    document.getElementById('uv').innerText = d.u.toFixed(2);
                    document.getElementById('vv').innerText = d.v.toFixed(2);
                }}
            }}

            async function mine(t) {{
                tg.HapticFeedback.impactOccurred('medium');
                await fetch('/api/mine', {{
                    method: 'POST',
                    headers: {{'Content-Type':'application/json'}},
                    body: JSON.stringify({{user_id: uid, token: t}})
                }});
                refresh();
            }}

            function donate() {{
                tg.openTelegramLink('https://t.me/' + '{BOT_USERNAME}' + '?start=donate');
                tg.close();
            }}

            function show(p) {{
                document.getElementById('p-home').style.display = (p=='home'?'block':'none');
                document.getElementById('p-tasks').style.display = (p=='tasks'?'block':'none');
            }}

            refresh(); setInterval(refresh, 5000);
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
