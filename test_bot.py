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
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (uid, name, ref_id))
        if ref_id and ref_id != uid:
            c.execute("UPDATE users SET points_unity = points_unity + 10 WHERE user_id = ?", (ref_id,))
    conn.commit(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ INITIALIZE TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"SYSTEM READY.\nUSER: {name}\nACCESS: GRANTED", reply_markup=kb)

# --- API ---
@app.get("/api/user/{{uid}}")
async def get_user_api(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, ref_count FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    c.execute("SELECT name, points_genesis FROM users ORDER BY points_genesis DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1],2)} for x in c.fetchall()]
    conn.close()
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "top": top} if r else None

@app.post("/api/mine")
async def api_mine(request: Request):
    try:
        data = await request.json()
        uid, t = data.get("user_id"), data.get("token")
        gain = 0.01 if t == 'veo' else 0.05
        col = {"genesis":"points_genesis", "unity":"points_unity", "veo":"points_veo"}.get(t)
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute(f"UPDATE users SET {col} = {col} + ? WHERE user_id = ?", (gain, uid))
        conn.commit(); conn.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "err": str(e)}

# --- UI (THEME HACKER PERFORMANT) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {{ --neon: #00ff41; --bg: #0d0208; --card: #151515; }}
            body {{ background: var(--bg); color: var(--neon); font-family: 'Courier New', monospace; margin: 0; padding: 15px; text-transform: uppercase; }}
            .header {{ border-bottom: 2px solid var(--neon); padding-bottom: 10px; margin-bottom: 20px; font-weight: bold; font-size: 14px; display: flex; justify-content: space-between; }}
            .card {{ background: var(--card); border: 1px solid var(--neon); padding: 15px; margin-bottom: 15px; box-shadow: 0 0 10px rgba(0, 255, 65, 0.1); }}
            .val {{ font-size: 30px; font-weight: 900; margin: 10px 0; text-shadow: 0 0 5px var(--neon); }}
            .btn {{ width: 100%; padding: 15px; background: transparent; border: 1px solid var(--neon); color: var(--neon); font-weight: bold; cursor: pointer; transition: 0.2s; }}
            .btn:active {{ background: var(--neon); color: #000; }}
            .footer {{ position: fixed; bottom: 0; left: 0; right: 0; background: #000; display: flex; justify-content: space-around; padding: 15px; border-top: 2px solid var(--neon); }}
            .nav-item {{ font-size: 11px; opacity: 0.5; cursor: pointer; }}
            .nav-item.active {{ opacity: 1; text-decoration: underline; }}
            .status-log {{ font-size: 9px; color: #555; margin-top: 5px; }}
        </style>
    </head>
    <body>
        <div id="p-mine">
            <div class="header"><span>> OWPC_OS_V24</span> <span id="st">ONLINE</span></div>
            <div class="card">
                <div style="font-size:10px">TOKEN: GENESIS</div>
                <div class="val" id="gv">0.00</div>
                <button class="btn" onclick="mine('genesis')">EXECUTE_MINING</button>
            </div>
            <div class="card">
                <div style="font-size:10px">TOKEN: UNITY</div>
                <div class="val" id="uv">0.00</div>
                <button class="btn" onclick="mine('unity')">SYNC_NODES</button>
            </div>
            <div class="card">
                <div style="font-size:10px">TOKEN: VEO_AI</div>
                <div class="val" id="vv">0.00</div>
                <button class="btn" onclick="mine('veo')">COMPUTE_AI</button>
            </div>
            <div class="status-log" id="log">SYSTEM READY...</div>
        </div>

        <div id="p-top" style="display:none">
            <div class="header"><span>> GLOBAL_RANKING</span></div>
            <div id="top-l" class="card"></div>
            <button class="btn" onclick="share()">INVITE_USER</button>
        </div>

        <div class="footer">
            <div class="nav-item active" id="n-mine" onclick="show('mine')">[ MINER ]</div>
            <div class="nav-item" id="n-top" onclick="show('top')">[ TOP ]</div>
        </div>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;

            async function refresh() {{
                if(!uid) {{ document.getElementById('log').innerText = "ERROR: NO_USER_ID. RESTART BOT."; return; }}
                try {{
                    const r = await fetch('/api/user/' + uid);
                    const d = await r.json();
                    if(d) {{
                        document.getElementById('gv').innerText = d.g.toFixed(2);
                        document.getElementById('uv').innerText = d.u.toFixed(2);
                        document.getElementById('vv').innerText = d.v.toFixed(2);
                        let h = ""; d.top.forEach((u, i) => {{ h += `<div style="display:flex;justify-content:space-between;margin:5px 0"><span>${{i+1}}. ${{u.n}}</span><span>${{u.p}}</span></div>`; }});
                        document.getElementById('top-l').innerHTML = h;
                    }}
                }} catch(e) {{ document.getElementById('log').innerText = "ERR: " + e; }}
            }}

            async function mine(t) {{
                tg.HapticFeedback.impactOccurred('medium');
                document.getElementById('log').innerText = "MINING IN PROGRESS...";
                const res = await fetch('/api/mine', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ user_id: uid, token: t }})
                }});
                const result = await res.json();
                if(result.ok) {{ 
                    document.getElementById('log').innerText = "SUCCESS: +0.05 DATA_POINTS";
                    refresh(); 
                }} else {{
                    document.getElementById('log').innerText = "FAILED: SERVER_REJECTED";
                }}
            }}

            function show(p) {{
                document.getElementById('p-mine').style.display = (p=='mine'?'block':'none');
                document.getElementById('p-top').style.display = (p=='top'?'block':'none');
                document.getElementById('n-mine').classList.toggle('active', p=='mine');
                document.getElementById('n-top').classList.toggle('active', p=='top');
            }}

            function share() {{
                tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start=${{uid}}&text=JOIN_THE_NETWORK`);
            }}

            refresh();
            setInterval(refresh, 5000);
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
