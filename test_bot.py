import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = "OWPCsbot"

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "owpc_v24.db")

logging.basicConfig(level=logging.INFO)
app = FastAPI()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0, points_unity REAL DEFAULT 0, 
                  points_veo REAL DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

# --- BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    # On nettoie le nom pour éviter les bugs SQL
    safe_name = name.replace("'", "")
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, safe_name))
    conn.commit(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ TERMINAL LOGIN", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"ACCESS GRANTED.\\nID: {uid}\\nSTATUS: ACTIVE", reply_markup=kb)

# --- API ---
@app.get("/api/user/{{uid}}")
async def get_user_api(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, ref_count FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    c.execute("SELECT name, points_genesis FROM users ORDER BY points_genesis DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1],2)} for x in c.fetchall()]
    conn.close()
    if r:
        return {{"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "top": top}}
    return None

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    col = {{"genesis":"points_genesis", "unity":"points_unity", "veo":"points_veo"}}.get(t)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET {{col}} = {{col}} + ? WHERE user_id = ?", (gain, uid))
    conn.commit(); conn.close()
    return {{"ok": True}}

# --- UI (FULL TERMINAL) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {{ --neon: #0f0; --bg: #000; }}
            body {{ background: var(--bg); color: var(--neon); font-family: 'Courier New', monospace; margin: 0; padding: 15px; }}
            .card {{ border: 1px solid var(--neon); padding: 15px; margin-bottom: 10px; background: rgba(0,255,0,0.05); }}
            .btn {{ width: 100%; padding: 12px; background: transparent; border: 1px solid var(--neon); color: var(--neon); font-weight: bold; cursor: pointer; }}
            .btn:active {{ background: var(--neon); color: #000; }}
            #log {{ font-size: 10px; color: #555; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div id="p-mine">
            <div style="border-bottom:1px solid var(--neon); margin-bottom:10px; font-weight:bold">>> OWPC_NODE_V24.5</div>
            <div class="card">
                <div>[ GENESIS ]</div>
                <div style="font-size:24px;font-weight:bold" id="gv">0.00</div>
                <button class="btn" onclick="mine('genesis')">EXEC_MINE</button>
            </div>
            <div class="card">
                <div>[ UNITY ]</div>
                <div style="font-size:24px;font-weight:bold" id="uv">0.00</div>
                <button class="btn" onclick="mine('unity')">SYNC_NODE</button>
            </div>
            <div id="log">CONNECTING...</div>
        </div>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;

            async function refresh() {{
                if(!uid) {{ document.getElementById('log').innerText="ERR: NO_UID"; return; }}
                try {{
                    const r = await fetch('/api/user/' + uid);
                    const d = await r.json();
                    if(d) {{
                        document.getElementById('gv').innerText = d.g.toFixed(2);
                        document.getElementById('uv').innerText = d.u.toFixed(2);
                        document.getElementById('log').innerText = "STATUS: LINK_ACTIVE";
                    }} else {{
                        document.getElementById('log').innerText = "ERR: USER_NOT_IN_DB. TYPE /START IN BOT.";
                    }}
                }} catch(e) {{ document.getElementById('log').innerText = "ERR: API_OFFLINE"; }}
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

            refresh(); setInterval(refresh, 4000);
        </script>
    </body>
    </html>
    """

async def main():
    init_db()
    # On réduit le timeout pour éviter que Railway ne bloque le polling
    bot = ApplicationBuilder().token(TOKEN).read_timeout(30).connect_timeout(30).build()
    bot.add_handler(CommandHandler("start", start))
    
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
