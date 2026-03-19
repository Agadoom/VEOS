import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = "OWPCsbot"

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "owpc_final.db")

logging.basicConfig(level=logging.INFO)
app = FastAPI()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  p_genesis REAL DEFAULT 0, p_unity REAL DEFAULT 0, 
                  p_veo REAL DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

# --- BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (uid, name.replace("'",""), ref_id))
        if ref_id and ref_id != uid:
            c.execute("UPDATE users SET p_unity = p_unity + 10.0, ref_count = ref_count + 1 WHERE user_id = ?", (ref_id,))
    conn.commit(); conn.close()

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ACCESS MAIN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f">> WELCOME TO OWPC NETWORK\\n>> STATUS: ENCRYPTED\\n>> USER_ID: {uid}", reply_markup=kb)

async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_invoice(title="Support OWPC", description="Donate 50 Stars", payload="support", provider_token="", currency="XTR", prices=[LabeledPrice("Donation", 50)])

# --- API ---
@app.get("/api/user/{{uid}}")
async def get_user(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    c.execute("SELECT name, p_genesis FROM users ORDER BY p_genesis DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1],2)} for x in c.fetchall()]
    conn.close()
    return {{"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "top": top}} if r else None

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("uid"), data.get("type")
    gain = 0.01 if t == 'veo' else 0.05
    col = {{"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}}.get(t)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET {{col}} = {{col}} + ? WHERE user_id = ?", (gain, uid))
    conn.commit(); conn.close()
    return {{"ok": True}}

# --- WEB UI (THEME TERMINAL V3) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {{ --neon: #0f0; --bg: #000; --dim: #003300; }}
            body {{ background: var(--bg); color: var(--neon); font-family: 'Courier New', monospace; margin: 0; padding: 15px; padding-bottom: 80px; overflow-x: hidden; }}
            .header {{ border-bottom: 1px solid var(--neon); padding-bottom: 5px; margin-bottom: 15px; font-size: 11px; display: flex; justify-content: space-between; }}
            .card {{ border: 1px solid var(--neon); padding: 12px; margin-bottom: 10px; background: rgba(0, 255, 0, 0.03); box-shadow: inset 0 0 10px var(--dim); }}
            .label {{ font-size: 10px; text-transform: uppercase; opacity: 0.8; }}
            .val {{ font-size: 26px; font-weight: bold; margin: 5px 0; }}
            .btn {{ width: 100%; padding: 12px; background: transparent; border: 1px solid var(--neon); color: var(--neon); font-family: 'Courier New'; font-weight: bold; cursor: pointer; }}
            .btn:active {{ background: var(--neon); color: #000; }}
            .footer {{ position: fixed; bottom: 0; left: 0; right: 0; background: #000; display: flex; justify-content: space-around; padding: 12px; border-top: 1px solid var(--neon); }}
            .nav-item {{ font-size: 10px; cursor: pointer; opacity: 0.5; }}
            .nav-item.active {{ opacity: 1; text-shadow: 0 0 5px var(--neon); }}
            .task-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed var(--dim); font-size: 12px; }}
            #log {{ font-size: 9px; color: #006600; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div id="p-mine">
            <div class="header"><span>>> OWPC_CORE_V25</span><span id="stat">SCANNING...</span></div>
            <div class="card"><div class="label">OWPC_GENESIS</div><div class="val" id="gv">0.00</div><button class="btn" onclick="mine('genesis')">EXEC_EXTRACTION</button></div>
            <div class="card"><div class="label">OWPC_UNITY</div><div class="val" id="uv">0.00</div><button class="btn" onclick="mine('unity')">SYNC_NODES</button></div>
            <div class="card"><div class="label">OWPC_VEO_AI</div><div class="val" id="vv">0.00</div><button class="btn" onclick="mine('veo')">RUN_QUANTUM</button></div>
            <div id="log">READY.</div>
        </div>

        <div id="p-tasks" style="display:none">
            <div class="header">>> NETWORK_TASKS</div>
            <div class="card">
                <div class="task-row" onclick="window.open('https://t.me/BlumCryptoBot')"><span>JOIN_BLUM</span><span>+5.00G</span></div>
                <div class="task-row" onclick="tg.openTelegramLink('https://t.me/OWPC_Official')"><span>COMMUNITY_HUB</span><span>+2.00G</span></div>
                <div class="task-row" onclick="window.open('https://example.com/buy')"><span>BUY_OWPC_TOKENS</span><span>[LINK]</span></div>
            </div>
            <button class="btn" style="border-color:gold; color:gold" onclick="tg.showAlert('Send /donate in bot for Stars support')">DONATE_STARS ⭐</button>
        </div>

        <div id="p-top" style="display:none">
            <div class="header">>> GLOBAL_RANKING</div>
            <div class="card" id="top-l"></div>
            <button class="btn" onclick="share()">GENERATE_REF_LINK</button>
        </div>

        <div class="footer">
            <div class="nav-item active" id="n-mine" onclick="show('mine')">[ MINING ]</div>
            <div class="nav-item" id="n-tasks" onclick="show('tasks')">[ TASKS ]</div>
            <div class="nav-item" id="n-top" onclick="show('top')">[ RANKING ]</div>
        </div>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;

            async function refresh() {{
                if(!uid) return;
                try {{
                    const r = await fetch('/api/user/' + uid);
                    const d = await r.json();
                    if(d) {{
                        document.getElementById('gv').innerText = d.g.toFixed(2);
                        document.getElementById('uv').innerText = d.u.toFixed(2);
                        document.getElementById('vv').innerText = d.v.toFixed(2);
                        let h = ""; d.top.forEach((u, i) => {{ h += `<div class="task-row"><span>${{i+1}}. ${{u.n}}</span><span>${{u.p}}</span></div>`; }});
                        document.getElementById('top-l').innerHTML = h;
                        document.getElementById('stat').innerText = "LINK_OK";
                    }}
                }} catch(e) {{ document.getElementById('stat').innerText = "API_ERR"; }}
            }}

            async function mine(t) {{
                tg.HapticFeedback.impactOccurred('medium');
                await fetch('/api/mine', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{uid:uid, type:t}}) }});
                refresh();
            }}

            function show(p) {{
                ['mine','tasks','top'].forEach(id => document.getElementById('p-'+id).style.display = 'none');
                ['mine','tasks','top'].forEach(id => document.getElementById('n-'+id).classList.remove('active'));
                document.getElementById('p-'+p).style.display = 'block';
                document.getElementById('n-'+p).classList.add('active');
            }}

            function share() {{
                tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start=${{uid}}&text=Mine OWPC tokens with me!`);
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
    bot.add_handler(CommandHandler("donate", donate))
    bot.add_handler(PreCheckoutQueryHandler(lambda u,c: u.pre_checkout_query.answer(ok=True)))
    
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
