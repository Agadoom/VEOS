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
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Lancer OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Bienvenue {name} sur le réseau OWPC.", reply_markup=kb)

async def donate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_invoice(title="Soutien", description="Don Stars", payload="don", provider_token="", currency="XTR", prices=[LabeledPrice("Don", 50)])

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

# --- UI (Correction des accolades terminée) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {{ --g: #00ff88; --u: #fff; --v: #00d9ff; --bg: #06090f; }}
            body {{ background: var(--bg); color: #fff; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 90px; }}
            .card {{ background: #111621; border-radius: 20px; padding: 18px; margin-bottom: 12px; border: 1px solid #1e2633; }}
            .label {{ font-size: 11px; color: #718096; text-transform: uppercase; }}
            .val {{ font-size: 28px; font-weight: 900; margin: 5px 0; font-family: monospace; }}
            .btn-mine {{ width: 100%; padding: 16px; border-radius: 14px; border: none; font-weight: 800; cursor: pointer; margin-top: 10px; }}
            .btn-g {{ background: var(--g); color: #000; }}
            .btn-u {{ background: var(--u); color: #000; }}
            .btn-v {{ background: var(--v); color: #000; }}
            .footer {{ position: fixed; bottom: 0; left: 0; right: 0; background: #0a0e17; display: flex; justify-content: space-around; padding: 15px; border-top: 1px solid #222; }}
            .nav-item {{ font-size: 11px; color: #4a5568; text-align: center; cursor: pointer; }}
            .nav-item.active {{ color: var(--g); }}
            .task-item {{ background: #1a202c; padding: 12px; border-radius: 12px; display: flex; justify-content: space-between; margin-bottom: 8px; }}
        </style>
    </head>
    <body>
        <div id="p-mine">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px">
                <span style="font-weight:bold; color:var(--v)">OWPC HUB</span>
                <span id="lvl" style="background:var(--g); color:#000; padding:3px 10px; border-radius:15px; font-size:12px">LVL 1</span>
            </div>
            <div class="card"><div class="label">Genesis</div><div class="val" id="gv" style="color:var(--g)">0.00</div><button class="btn-mine btn-g" onclick="mine('genesis')">MINER</button></div>
            <div class="card"><div class="label">Unity</div><div class="val" id="uv" style="color:var(--u)">0.00</div><button class="btn-mine btn-u" onclick="mine('unity')">RÉCOLTER</button></div>
            <div class="card"><div class="label">Veo AI</div><div class="val" id="vv" style="color:var(--v)">0.00</div><button class="btn-mine btn-v" onclick="mine('veo')">COMPUTER</button></div>
        </div>

        <div id="p-tasks" style="display:none">
            <h3>MISSIONS</h3>
            <div class="task-item" onclick="window.open('https://t.me/BlumCryptoBot')"><span>🌱 Join Blum</span><span>+5.0 G</span></div>
            <div class="task-item" onclick="tg.openTelegramLink('https://t.me/OWPC_Official')"><span>📢 Canal</span><span>+2.0 G</span></div>
            <div class="card" style="margin-top:20px"><button class="btn-mine" style="background:gold;color:#000" onclick="tg.showAlert('Taper /donate au bot')">DONNER STARS ⭐</button></div>
        </div>

        <div id="p-top" style="display:none">
            <h3>LEADERBOARD</h3>
            <div class="card" id="top-l"></div>
            <button class="btn-mine btn-g" onclick="share()">INVITER AMIS</button>
        </div>

        <div class="footer">
            <div class="nav-item active" id="n-mine" onclick="show('mine')">⛏️<br>Mines</div>
            <div class="nav-item" id="n-tasks" onclick="show('tasks')">📋<br>Tasks</div>
            <div class="nav-item" id="n-top" onclick="show('top')">🏆<br>Leader</div>
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
                    document.getElementById('lvl').innerText = "LVL " + d.lvl;
                    let h = ""; d.top.forEach((u, i) => {{ h += `<div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #222"><span>${{i+1}}. ${{u.n}}</span><span>${{u.p}}</span></div>`; }});
                    document.getElementById('top-l').innerHTML = h;
                }} catch(e) {{}}
            }}

            async function mine(t) {{
                tg.HapticFeedback.impactOccurred('medium');
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
                tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start=${{uid}}&text=Mine avec moi !`);
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
    bot.add_handler(CommandHandler("donate", donate_cmd))
    bot.add_handler(PreCheckoutQueryHandler(lambda u,c: u.pre_checkout_query.answer(ok=True)))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
