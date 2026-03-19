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
DB_PATH = os.path.join(DATA_DIR, "owpc_v24.db")

logging.basicConfig(level=logging.INFO)
app = FastAPI()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0, points_unity REAL DEFAULT 0, 
                  points_veo REAL DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0,
                  level INTEGER DEFAULT 1)''')
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
            c.execute("UPDATE users SET points_unity = points_unity + 10.0, ref_count = ref_count + 1 WHERE user_id = ?", (ref_id,))
    conn.commit(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ACCESS TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f">> PROTOCOL_CONNECTED: {name}\n>> STATUS: ONLINE", reply_markup=kb)

# --- API ---
@app.get("/api/user/{{uid}}")
async def get_user_api(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, ref_count, level FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    c.execute("SELECT name, points_genesis FROM users ORDER BY points_genesis DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1],2)} for x in c.fetchall()]
    conn.close()
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "lvl": r[4], "top": top} if r else None

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

# --- UI (DESIGN TERMINAL RETRO) ---
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
            body {{ background: var(--bg); color: var(--neon); font-family: 'Courier New', monospace; margin: 0; padding: 15px; overflow-x: hidden; }}
            
            /* Scanline Effect */
            body::before {{ content: " "; display: block; position: absolute; top: 0; left: 0; bottom: 0; right: 0; background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06)); z-index: 100; background-size: 100% 3px, 3px 100%; pointer-events: none; }}

            .header {{ border-bottom: 1px solid var(--neon); padding-bottom: 5px; margin-bottom: 20px; font-size: 12px; }}
            
            .card {{ border: 1px solid var(--neon); padding: 15px; margin-bottom: 15px; background: rgba(0, 255, 0, 0.02); position: relative; }}
            .label {{ font-size: 10px; opacity: 0.7; letter-spacing: 2px; }}
            .val {{ font-size: 24px; font-weight: bold; margin: 5px 0; }}
            
            .btn-terminal {{ width: 100%; padding: 12px; background: transparent; border: 1px solid var(--neon); color: var(--neon); font-family: 'Courier New'; font-weight: bold; cursor: pointer; margin-top: 5px; text-transform: uppercase; }}
            .btn-terminal:active {{ background: var(--neon); color: #000; }}
            
            .footer {{ position: fixed; bottom: 0; left: 0; right: 0; background: #000; display: flex; justify-content: space-around; padding: 12px; border-top: 1px solid var(--neon); z-index: 200; }}
            .nav-item {{ font-size: 10px; cursor: pointer; text-align: center; opacity: 0.5; }}
            .nav-item.active {{ opacity: 1; text-shadow: 0 0 8px var(--neon); }}
            
            .task-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px dashed var(--neon); font-size: 12px; }}
            .floating {{ position: absolute; animation: fly 0.8s forwards; font-weight: bold; }}
            @keyframes fly {{ 0%{{transform:translateY(0);opacity:1}} 100%{{transform:translateY(-40px);opacity:0}} }}
        </style>
    </head>
    <body>
        <div id="p-mine">
            <div class="header">>> OWPC_CORE_V24.2 / LEVEL: <span id="lvl">1</span></div>
            
            <div class="card">
                <div class="label">[ GENESIS_PROTOCOL ]</div>
                <div class="val" id="gv">0.00</div>
                <button class="btn-terminal" onclick="mine('genesis', this)">EXEC_EXTRACT</button>
            </div>

            <div class="card">
                <div class="label">[ UNITY_NODES ]</div>
                <div class="val" id="uv">0.00</div>
                <button class="btn-terminal" onclick="mine('unity', this)">SYNC_UNITY</button>
            </div>

            <div class="card">
                <div class="label">[ VEO_AI_QUANTUM ]</div>
                <div class="val" id="vv">0.00</div>
                <button class="btn-terminal" onclick="mine('veo', this)">COMPUTE_VEO</button>
            </div>
        </div>

        <div id="p-tasks" style="display:none">
            <div class="header">>> ACTIVE_MISSIONS</div>
            <div class="card">
                <div class="task-row" onclick="window.open('https://t.me/BlumCryptoBot')"><span>BLUM_JOIN</span><span>+5.00</span></div>
                <div class="task-row" onclick="tg.openTelegramLink('https://t.me/OWPC_Official')"><span>OFFICIAL_CHANNEL</span><span>+2.00</span></div>
                <div class="task-row" onclick="share()"><span>INVITE_FRIENDS</span><span>+10.00</span></div>
            </div>
            <button class="btn-terminal" style="border-color:gold; color:gold" onclick="tg.showAlert('Send /donate to bot')">SUPPORT_ stars</button>
        </div>

        <div id="p-top" style="display:none">
            <div class="header">>> TOP_RANKING</div>
            <div class="card" id="top-l"></div>
        </div>

        <div class="footer">
            <div class="nav-item active" id="n-mine" onclick="show('mine')">[ MINING ]</div>
            <div class="nav-item" id="n-tasks" onclick="show('tasks')">[ TASKS ]</div>
            <div class="nav-item" id="n-top" onclick="show('top')">[ RANK ]</div>
        </div>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;

            async function refresh() {{
                if(!uid) return;
                try {{
                    const r = await fetch('/api/user/' + uid);
                    const d = await r.json();
                    document.getElementById('gv').innerText = d.g.toFixed(2);
                    document.getElementById('uv').innerText = d.u.toFixed(2);
                    document.getElementById('vv').innerText = d.v.toFixed(2);
                    document.getElementById('lvl').innerText = d.lvl;
                    let h = ""; d.top.forEach((u, i) => {{ h += `<div class="task-row"><span>${{i+1}}. ${{u.n}}</span><span>${{u.p}}</span></div>`; }});
                    document.getElementById('top-l').innerHTML = h;
                }} catch(e) {{}}
            }}

            async function mine(t, btn) {{
                tg.HapticFeedback.impactOccurred('medium');
                let f = document.createElement('div'); f.className='floating'; f.innerText='+'+(t=='veo'?'0.01':'0.05'); f.style.left='50%'; btn.appendChild(f);
                setTimeout(()=>f.remove(), 800);

                await fetch('/api/mine', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{user_id:uid, token:t}}) }});
                refresh();
            }}

            function show(p) {{
                ['mine','tasks','top'].forEach(id => document.getElementById('p-'+id).style.display = 'none');
                ['mine','tasks','top'].forEach(id => document.getElementById('n-'+id).classList.remove('active'));
                document.getElementById('p-'+p).style.display = 'block';
                document.getElementById('n-'+p).classList.add('active');
            }}

            function share() {{
                tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start=${{uid}}&text=Join the OWPC Hack.`);
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
