import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = os.getenv("BOT_USERNAME", "OWPCsbot")

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "owpc_pro_v29.db")

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

# --- BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    if context.args and context.args[0] == "donate":
        await update.message.reply_invoice(
            title="🚀 VEO BOOST", description="Add +10.00 VEO to your account!",
            payload="boost_veo", provider_token="", currency="XTR", prices=[LabeledPrice("Payer", 50)]
        )
        return
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # On met à jour le nom si l'utilisateur existe déjà pour le leaderboard
    c.execute("INSERT INTO users (user_id, name) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET name=excluded.name", (uid, name))
    conn.commit(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to the Hub, {name}.", reply_markup=kb)

async def success_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE users SET p_veo = p_veo + 10.0 WHERE user_id = ?", (uid,))
    conn.commit(); conn.close()
    await update.message.reply_text("✅ Payment Successful! +10.00 VEO added.")

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # Récupération données utilisateur
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    # Récupération Top 5 (basé sur le total des 3 piliers)
    c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    conn.close()
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "top": top} if r else None

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    col = {"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}.get(t)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET {col} = {col} + ? WHERE user_id = ?", (gain, uid))
    conn.commit(); conn.close()
    return {"ok": True}

# --- WEB UI ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    html_raw = r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #000; --card: #111; --blue: #007AFF; --green: #34C759; --gold: #FFD700; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 20px; padding-bottom: 90px; }
        .header { font-weight: 800; font-size: 22px; margin-bottom: 20px; color: var(--blue); text-align: center; }
        .balance { text-align: center; margin-bottom: 25px; border: 1px solid #222; padding: 25px; border-radius: 28px; background: linear-gradient(180deg, #0a0a0a, #000); }
        .card { background: var(--card); padding: 18px; border-radius: 20px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1C1C1E; }
        .btn { background: #FFF; color: #000; border: none; padding: 12px 20px; border-radius: 12px; font-weight: 700; cursor: pointer; }
        .nav { position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.95); backdrop-filter: blur(15px); padding: 12px 35px; border-radius: 35px; display: flex; gap: 40px; border: 1px solid #333; z-index: 1000; }
        .nav-item { font-size: 24px; opacity: 0.4; transition: 0.3s; cursor: pointer; }
        .nav-item.active { opacity: 1; transform: scale(1.1); }
        .rank-row { display: flex; justify-content: space-between; padding: 15px; border-bottom: 1px solid #1c1c1e; align-items: center; }
        .task-link { text-decoration: none; background: #222; color: #FFF; padding: 8px 15px; border-radius: 8px; font-size: 12px; font-weight: 600; border: 1px solid #444; }
    </style>
</head>
<body>
    <div id="p-mine">
        <div class="header">OWPC CORE</div>
        <div class="balance"><span style="color:#8E8E93; font-size:12px">TOTAL BALANCE</span><h1 id="tot" style="font-size:48px; margin:10px 0">0.00</h1></div>
        <div class="card"><div><small style="color:#8E8E93">GENESIS</small><div id="gv" style="font-size:20px; font-weight:700">0.00</div></div><button class="btn" style="background:var(--green)" onclick="mine('genesis')">CLAIM</button></div>
        <div class="card"><div><small style="color:#8E8E93">UNITY</small><div id="uv" style="font-size:20px; font-weight:700">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small style="color:#8E8E93">VEO AI</small><div id="vv" style="font-size:20px; font-weight:700">0.00</div></div><button class="btn" style="background:var(--blue);color:#FFF" onclick="mine('veo')">COMPUTE</button></div>
    </div>

    <div id="p-tasks" style="display:none">
        <h2 style="font-weight:800">ECOSYSTEM</h2>
        <div class="card"><div>Genesis Jetton<br><small style="color:#8E8E93">Memepad Trade</small></div><a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" class="task-link">OPEN</a></div>
        <div class="card"><div>Unity Core<br><small style="color:#8E8E93">Node Network</small></div><a href="https://t.me/blum/app?startapp=memepadjetton_UNITY_6vK2A-ref_6VRKyJ9MZA" class="task-link">OPEN</a></div>
        <div class="card"><div>Veo AI Quantum<br><small style="color:#8E8E93">AI Power</small></div><a href="https://t.me/blum/app?startapp=memepadjetton_VEO_7zL3B-ref_6VRKyJ9MZA" class="task-link">OPEN</a></div>
        <div class="card" style="border: 1px solid gold"><div>Boost +10 VEO<br><small style="color:gold">Stars Payment</small></div><div class="task-link" style="background:gold; color:#000; cursor:pointer" onclick="donate()">BUY ⭐</div></div>
    </div>

    <div id="p-ranks" style="display:none">
        <h2 style="font-weight:800">TOP MINERS</h2>
        <div id="rank-list" style="background:var(--card); border-radius:20px; border:1px solid #1C1C1E; overflow:hidden"></div>
    </div>

    <div class="nav">
        <div id="n-mine" onclick="show('mine')" class="nav-item active">🏠</div>
        <div id="n-tasks" onclick="show('tasks')" class="nav-item">📋</div>
        <div id="n-ranks" onclick="show('ranks')" class="nav-item">🏆</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;
        const botName = '""" + BOT_USERNAME + r"""';

        async function refresh() {
            if(!uid) return;
            try {
                const r = await fetch('/api/user/' + uid);
                const d = await r.json();
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = (d.g+d.u+d.v).toFixed(2);
                
                let h = "";
                d.top.forEach((u, i) => {
                    h += `<div class="rank-row">
                            <span>${i+1}. ${u.n}</span>
                            <span style="color:var(--blue); font-weight:700">${u.p}</span>
                          </div>`;
                });
                document.getElementById('rank-list').innerHTML = h;
            } catch(e) {}
        }
        async function mine(t) {
            tg.HapticFeedback.impactOccurred('medium');
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            refresh();
        }
        function donate() {
            tg.openTelegramLink('https://t.me/' + botName + '?start=donate');
            setTimeout(() => { tg.close(); }, 300);
        }
        function show(p) {
            ['mine','tasks','ranks'].forEach(id => {
                document.getElementById('p-'+id).style.display = (id==p?'block':'none');
                document.getElementById('n-'+id).classList.toggle('active', id==p);
            });
        }
        refresh(); setInterval(refresh, 5000);
    </script>
</body>
</html>
    """
    return html_raw

async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(PreCheckoutQueryHandler(lambda u,c: u.pre_checkout_query.answer(ok=True)))
    bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, success_payment))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
