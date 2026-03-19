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
DB_PATH = os.path.join(DATA_DIR, "owpc_pro_v27.db")

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
    
    # Gestion du don direct via lien profond
    if context.args and context.args[0] == "donate":
        await update.message.reply_invoice(
            title="🚀 VEO BOOST",
            description="Add +10.00 VEO to your account!",
            payload="boost_veo",
            provider_token="", # Vide pour Telegram Stars
            currency="XTR",
            prices=[LabeledPrice("Payer", 50)]
        )
        return

    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    conn.commit(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome back to the Ecosystem.", reply_markup=kb)

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

# --- UI RÉALISTE (STYLE CRYPTO APP MODERN) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {{ --bg: #000000; --card: #121212; --blue: #007AFF; --green: #34C759; --accent: #AF52DE; }}
            body {{ background: var(--bg); color: #FFF; font-family: 'Inter', sans-serif; margin: 0; padding: 20px; }}
            
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }}
            .logo {{ font-size: 20px; font-weight: 800; letter-spacing: -0.5px; }}
            
            .main-balance {{ text-align: center; margin-bottom: 40px; }}
            .main-balance span {{ font-size: 14px; color: #8E8E93; }}
            .main-balance h1 {{ font-size: 48px; margin: 5px 0; font-weight: 800; }}

            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 30px; }}
            .stat-card {{ background: var(--card); padding: 15px; border-radius: 20px; border: 1px solid #1C1C1E; }}
            .stat-card .label {{ font-size: 11px; color: #8E8E93; font-weight: 600; text-transform: uppercase; }}
            .stat-card .val {{ font-size: 20px; font-weight: 700; margin-top: 5px; }}

            .action-card {{ background: var(--card); border-radius: 24px; padding: 20px; margin-bottom: 15px; border: 1px solid #1C1C1E; }}
            .btn-action {{ width: 100%; padding: 14px; border-radius: 12px; border: none; font-weight: 700; font-size: 15px; cursor: pointer; transition: 0.2s; }}
            .btn-genesis {{ background: var(--green); color: #000; }}
            .btn-unity {{ background: #FFF; color: #000; }}
            .btn-veo {{ background: var(--blue); color: #FFF; }}

            .nav {{ position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); background: rgba(28, 28, 30, 0.8); backdrop-filter: blur(20px); border-radius: 30px; display: flex; padding: 8px 25px; gap: 30px; border: 1px solid #38383A; }}
            .nav-item {{ font-size: 22px; cursor: pointer; opacity: 0.5; transition: 0.3s; }}
            .nav-item.active {{ opacity: 1; }}

            .task-item {{ background: var(--card); padding: 15px; border-radius: 18px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border: 1px solid #1C1C1E; }}
            .task-info h4 {{ margin: 0; font-size: 14px; }}
            .task-info p {{ margin: 0; font-size: 11px; color: #8E8E93; }}
            .task-link {{ background: #2C2C2E; color: #FFF; padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div id="p-home">
            <div class="header"><div class="logo">OWPC HUB</div><div style="background:var(--blue); padding:4px 10px; border-radius:10px; font-size:10px">VERIFIED</div></div>
            
            <div class="main-balance">
                <span>TOTAL ASSETS</span>
                <h1 id="total-val">0.00</h1>
            </div>

            <div class="grid">
                <div class="stat-card"><div class="label">Ref. Count</div><div class="val" id="rc">0</div></div>
                <div class="stat-card"><div class="label">Network</div><div class="val" style="color:var(--green)">Online</div></div>
            </div>

            <div class="action-card">
                <div style="display:flex; justify-content:space-between; margin-bottom:15px">
                    <div><div class="label">Genesis Protocol</div><div class="val" id="gv">0.00</div></div>
                    <button class="btn-action btn-genesis" style="width:auto" onclick="mine('genesis')">CLAIM</button>
                </div>
            </div>

            <div class="action-card">
                <div style="display:flex; justify-content:space-between; margin-bottom:15px">
                    <div><div class="label">Unity Core</div><div class="val" id="uv">0.00</div></div>
                    <button class="btn-action btn-unity" style="width:auto" onclick="mine('unity')">SYNC</button>
                </div>
            </div>

            <div class="action-card">
                <div style="display:flex; justify-content:space-between; margin-bottom:15px">
                    <div><div class="label">Veo AI Quantum</div><div class="val" id="vv">0.00</div></div>
                    <button class="btn-action btn-veo" style="width:auto" onclick="mine('veo')">COMPUTE</button>
                </div>
            </div>
        </div>

        <div id="p-tasks" style="display:none">
            <h2 style="font-size:24px; font-weight:800">Ecosystem Tasks</h2>
            <div class="task-item">
                <div class="task-info"><h4>Genesis Jetton</h4><p>Buy & Trade on Memepad</p></div>
                <a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" class="task-link">OPEN</a>
            </div>
            <div class="task-item">
                <div class="task-info"><h4>Official Channel</h4><p>Join for updates</p></div>
                <a href="https://t.me/OWPC_Official" class="task-link">JOIN</a>
            </div>
            <div class="task-item" style="border-color:gold">
                <div class="task-info"><h4>Boost Account</h4><p>Get +10.0 VEO with Stars</p></div>
                <div class="task-link" style="background:gold; color:#000" onclick="donate()">BUY ⭐</div>
            </div>
        </div>

        <div class="nav">
            <div id="n-home" onclick="show('home')" class="nav-item active">🏠</div>
            <div id="n-tasks" onclick="show('tasks')" class="nav-item">📋</div>
            <div onclick="tg.close()" class="nav-item">✕</div>
        </div>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            tg.backgroundColor = "#000000";
            tg.headerColor = "#000000";
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
                        document.getElementById('rc').innerText = d.rc;
                        document.getElementById('total-val').innerText = (d.g + d.u + d.v).toFixed(2);
                    }}
                }} catch(e) {{}}
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
                // Redirection directe vers le bot avec paramètre de don et fermeture de la WebApp
                tg.openTelegramLink('https://t.me/' + '{BOT_USERNAME}' + '?start=donate');
                setTimeout(() => {{ tg.close(); }}, 100);
            }

            function show(p) {{
                document.getElementById('p-home').style.display = (p=='home'?'block':'none');
                document.getElementById('p-tasks').style.display = (p=='tasks'?'block':'none');
                document.getElementById('n-home').classList.toggle('active', p=='home');
                document.getElementById('n-tasks').classList.toggle('active', p=='tasks');
            }}

            refresh(); setInterval(refresh, 4000);
        </script>
    </body>
    </html>
    """

async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(PreCheckoutQueryHandler(lambda u,c: u.pre_checkout_query.answer(ok=True)))
    
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
