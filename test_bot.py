import os, sqlite3, asyncio, uvicorn, logging, time
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
DB_PATH = os.path.join(DATA_DIR, "owpc_pro_v32.db")

logging.basicConfig(level=logging.INFO)
app = FastAPI()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  p_genesis REAL DEFAULT 0, p_unity REAL DEFAULT 0, 
                  p_veo REAL DEFAULT 0, ref_count INTEGER DEFAULT 0,
                  last_daily INTEGER DEFAULT 0, referred_by INTEGER)''')
    conn.commit(); conn.close()

# --- BOT FUNCTIONS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_by = None
    if context.args and context.args[0].startswith("ref_"):
        try:
            ref_by = int(context.args[0].replace("ref_", ""))
            if ref_by == uid: ref_by = None
        except: pass

    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (uid, name, ref_by))
        if ref_by:
            c.execute("UPDATE users SET p_genesis = p_genesis + 5.0, ref_count = ref_count + 1 WHERE user_id = ?", (ref_by,))
    else:
        c.execute("UPDATE users SET name=? WHERE user_id=?", (name, uid))
    conn.commit(); conn.close()
    
    if context.args and context.args[0] == "donate":
        await update.message.reply_invoice(
            title="🚀 VEO BOOST", description="Add +10.00 VEO!",
            payload="boost_veo", provider_token="", currency="XTR", prices=[LabeledPrice("Payer", 50)]
        )
        return

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to the Hub, {name}!", reply_markup=kb)

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
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_daily FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    conn.close()
    if not r: return None
    can_daily = (int(time.time()) - r[4]) > 86400
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "top": top, "can_daily": can_daily}

@app.post("/api/daily/{uid}")
async def daily_api(uid: int):
    now = int(time.time())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT last_daily FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    if res and (now - res[0]) > 86400:
        c.execute("UPDATE users SET p_unity = p_unity + 1.0, last_daily = ? WHERE user_id = ?", (now, uid))
        conn.commit(); conn.close()
        return {"ok": True}
    conn.close()
    return {"ok": False}

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
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
    <style>
        :root { --bg: #000; --card: #111; --blue: #007AFF; --green: #34C759; --gold: #FFD700; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 90px; overflow-x: hidden; }
        .header { font-weight: 800; font-size: 20px; color: var(--blue); text-align: center; margin-bottom: 15px; }
        .balance { text-align: center; margin-bottom: 20px; border: 1px solid #222; padding: 20px; border-radius: 25px; background: #050505; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1C1C1E; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 15px; border-radius: 10px; font-weight: 700; cursor: pointer; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.9); backdrop-filter: blur(10px); padding: 10px 30px; border-radius: 35px; display: flex; gap: 30px; border: 1px solid #333; z-index: 1000; }
        .nav-item { font-size: 22px; opacity: 0.4; cursor: pointer; }
        .nav-item.active { opacity: 1; transform: scale(1.1); }
        .rank-row { display: flex; justify-content: space-between; padding: 12px; border-bottom: 1px solid #1c1c1e; }
        .daily-btn { width: 100%; background: var(--blue); color: #FFF; padding: 12px; border-radius: 12px; border: none; font-weight: 700; margin-bottom: 15px; transition: 0.3s; }
        .daily-btn:disabled { background: #222; color: #555; }
    </style>
</head>
<body>
    <div id="p-mine">
        <div class="header">OWPC HUB</div>
        <button id="daily-btn" class="daily-btn" onclick="claimDaily()">CLAIM DAILY REWARD (+1.0 Unity)</button>
        <div class="balance"><span>TOTAL ASSETS</span><h1 id="tot" style="font-size:40px; margin:5px 0">0.00</h1></div>
        <div class="card"><div><small>GENESIS</small><div id="gv">0.00</div></div><button class="btn" style="background:var(--green)" onclick="mine('genesis')">CLAIM</button></div>
        <div class="card"><div><small>UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small>VEO AI</small><div id="vv">0.00</div></div><button class="btn" style="background:var(--blue);color:#FFF" onclick="mine('veo')">COMPUTE</button></div>
    </div>
    <div id="p-tasks" style="display:none">
        <h2>REFERRALS</h2>
        <div class="card" style="flex-direction:column; align-items:flex-start; gap:10px">
            <div><b>Invite Friends</b><br><small style="color:#8E8E93">Get +5.00 Genesis per friend</small></div>
            <button class="btn" style="width:100%" onclick="copyRef()">COPY MY REF LINK</button>
            <div style="font-size:12px; color:var(--green)">Total Referred: <span id="rc">0</span></div>
        </div>
        <h2>ECOSYSTEM</h2>
        <div class="card"><div>Genesis<br><small>Blum Memepad</small></div><a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" class="btn" style="text-decoration:none">OPEN</a></div>
        <div class="card"><div>Unity<br><small>Node Network</small></div><a href="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA" class="btn" style="text-decoration:none">OPEN</a></div>
        <div class="card"><div>Veo AI<br><small>Quantum Power</small></div><a href="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA" class="btn" style="text-decoration:none">OPEN</a></div>
        <div class="card" style="border: 1px solid gold"><div>Boost +10 VEO<br><small style="color:gold">Stars Payment</small></div><div class="btn" style="background:gold; color:#000" onclick="donate()">BUY ⭐</div></div>
    </div>
    <div id="p-ranks" style="display:none">
        <h2>TOP MINERS</h2>
        <div id="rank-list" style="background:var(--card); border-radius:15px; overflow:hidden"></div>
    </div>
    <div class="nav">
        <div id="n-mine" onclick="show('mine')" class="nav-item active">🏠</div>
        <div id="n-tasks" onclick="show('tasks')" class="nav-item">👥</div>
        <div id="n-ranks" onclick="show('ranks')" class="nav-item">🏆</div>
    </div>
    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;
        const botName = '""" + BOT_USERNAME + r"""';

        function launchConfetti() {
            confetti({ particleCount: 150, spread: 70, origin: { y: 0.6 }, colors: ['#007AFF', '#34C759', '#FFD700'] });
        }

        async function refresh() {
            if(!uid) return;
            const r = await fetch('/api/user/' + uid);
            const d = await r.json();
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('tot').innerText = (d.g+d.u+d.v).toFixed(2);
            document.getElementById('rc').innerText = d.rc;
            document.getElementById('daily-btn').disabled = !d.can_daily;
            if(!d.can_daily) document.getElementById('daily-btn').innerText = "DAILY CLAIMED";
            let h = "";
            d.top.forEach((u, i) => { h += `<div class="rank-row"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
            document.getElementById('rank-list').innerHTML = h;
        }

        async function claimDaily() {
            const r = await fetch('/api/daily/' + uid, {method:'POST'});
            const d = await r.json();
            if(d.ok) { 
                launchConfetti();
                tg.HapticFeedback.notificationOccurred('success');
                refresh(); 
            }
        }

        function copyRef() {
            const link = "https://t.me/" + botName + "?start=ref_" + uid;
            const el = document.createElement('textarea'); el.value = link; document.body.appendChild(el);
            el.select(); document.execCommand('copy'); document.body.removeChild(el);
            tg.showAlert("Link copied!");
        }

        function donate() { tg.openTelegramLink('https://t.me/' + botName + '?start=donate'); setTimeout(() => { tg.close(); }, 300); }
        
        async function mine(t) {
            tg.HapticFeedback.impactOccurred('light');
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            refresh();
        }

        function show(p) {
            ['mine','tasks','ranks'].forEach(id => {
                document.getElementById('p-'+id).style.display = (id==p?'block':'none');
                document.getElementById('n-'+id).classList.toggle('active', id==p);
            });
        }
        refresh(); setInterval(refresh, 8000);
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

if __name__ == "__main__": asyncio.run(main())
