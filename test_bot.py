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
DB_PATH = os.path.join(DATA_DIR, "owpc_pro_v34.db")

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
    # Table pour l'historique des gains
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                  token TEXT, amount REAL, timestamp INTEGER)''')
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
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to the Hub, {name}!", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_daily FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    # Récupération de l'historique (5 derniers)
    c.execute("SELECT token, amount, timestamp FROM logs WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,))
    history = [{"t": x[0], "a": x[1], "ts": x[2]} for x in c.fetchall()]
    
    c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    conn.close()
    if not r: return None
    can_daily = (int(time.time()) - r[4]) > 86400
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "top": top, "can_daily": can_daily, "history": history}

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    col = {"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}.get(t)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET {col} = {col} + ? WHERE user_id = ?", (gain, uid))
    # Ajout au log
    c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (?, ?, ?, ?)", (uid, t, gain, int(time.time())))
    conn.commit(); conn.close()
    return {"ok": True}

@app.post("/api/daily/{uid}")
async def daily_api(uid: int):
    now = int(time.time())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT last_daily FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    if res and (now - res[0]) > 86400:
        c.execute("UPDATE users SET p_unity = p_unity + 1.0, last_daily = ? WHERE user_id = ?", (now, uid))
        c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (?, ?, ?, ?)", (uid, "DAILY", 1.0, now))
        conn.commit(); conn.close()
        return {"ok": True}
    conn.close()
    return {"ok": False}

# --- WEB UI ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return r"""
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
        .btn { background: #FFF; color: #000; border: none; padding: 10px 15px; border-radius: 10px; font-weight: 700; cursor: pointer; display: flex; align-items: center; justify-content: center; min-width: 80px; }
        .btn:disabled { opacity: 0.6; }
        .loader { width: 14px; height: 14px; border: 2px solid #000; border-bottom-color: transparent; border-radius: 50%; display: none; animation: rot 1s linear infinite; }
        @keyframes rot { to { transform: rotate(360deg); } }
        .history-box { margin-top: 20px; font-size: 13px; color: #8E8E93; }
        .history-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #1c1c1e; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.9); backdrop-filter: blur(10px); padding: 10px 30px; border-radius: 35px; display: flex; gap: 30px; border: 1px solid #333; z-index: 1000; }
        .nav-item { font-size: 22px; opacity: 0.4; cursor: pointer; }
        .nav-item.active { opacity: 1; transform: scale(1.1); }
        .daily-btn { width: 100%; background: var(--blue); color: #FFF; padding: 12px; border-radius: 12px; border: none; font-weight: 700; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div id="p-mine">
        <div class="header">OWPC HUB</div>
        <button id="daily-btn" class="daily-btn" onclick="claimDaily()">CLAIM DAILY REWARD (+1.0 Unity)</button>
        <div class="balance"><span>TOTAL ASSETS</span><h1 id="tot" style="font-size:40px; margin:5px 0">0.00</h1></div>
        
        <div class="card"><div><small>GENESIS</small><div id="gv">0.00</div></div><button class="btn" id="btn-genesis" onclick="mine('genesis')" style="background:var(--green)"><span id="tx-genesis">CLAIM</span><div class="loader" id="ld-genesis"></div></button></div>
        <div class="card"><div><small>UNITY</small><div id="uv">0.00</div></div><button class="btn" id="btn-unity" onclick="mine('unity')"><span id="tx-unity">SYNC</span><div class="loader" id="ld-unity"></div></button></div>
        <div class="card"><div><small>VEO AI</small><div id="vv">0.00</div></div><button class="btn" id="btn-veo" onclick="mine('veo')" style="background:var(--blue);color:#FFF"><span id="tx-veo">COMPUTE</span><div class="loader" id="ld-veo" style="border-color:#FFF; border-bottom-color:transparent"></div></button></div>

        <div class="history-box">
            <b>RECENTS GAINS</b>
            <div id="history-list"></div>
        </div>
    </div>

    <div id="p-tasks" style="display:none">
        <h2>REFERRALS</h2>
        <div class="card" style="flex-direction:column; align-items:flex-start; gap:10px">
            <button class="btn" style="width:100%" onclick="copyRef()">COPY REF LINK</button>
            <div style="font-size:12px; color:var(--green)">Referred: <span id="rc">0</span></div>
        </div>
        <h2>ECOSYSTEM</h2>
        <div class="card"><div>Genesis</div><a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" class="btn">OPEN</a></div>
        <div class="card"><div>Unity</div><a href="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA" class="btn">OPEN</a></div>
        <div class="card"><div>Veo AI</div><a href="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA" class="btn">OPEN</a></div>
    </div>
    <div id="p-ranks" style="display:none">
        <h2>TOP MINERS</h2>
        <div id="rank-list"></div>
    </div>

    <div class="nav">
        <div id="n-mine" onclick="show('mine')" class="nav-item active">🏠</div>
        <div id="n-tasks" onclick="show('tasks')" class="nav-item">👥</div>
        <div id="n-ranks" onclick="show('ranks')" class="nav-item">🏆</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;
        const clickSound = new Audio('https://www.soundjay.com/buttons/button-16.mp3');

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

            // Update History
            let h_html = "";
            d.history.forEach(h => {
                let timeStr = new Date(h.ts * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                h_html += `<div class="history-item"><span>${h.t.toUpperCase()}</span><span>+${h.a}</span><span>${timeStr}</span></div>`;
            });
            document.getElementById('history-list').innerHTML = h_html || "No recent activity";
            
            // Update Ranks
            let r_html = "";
            d.top.forEach((u, i) => { r_html += `<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
            document.getElementById('rank-list').innerHTML = r_html;
        }

        async function mine(t) {
            clickSound.play();
            tg.HapticFeedback.impactOccurred('light');
            document.getElementById('tx-'+t).style.display = 'none';
            document.getElementById('ld-'+t).style.display = 'block';
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            setTimeout(() => {
                document.getElementById('tx-'+t).style.display = 'block';
                document.getElementById('ld-'+t).style.display = 'none';
                refresh();
            }, 400);
        }

        async function claimDaily() {
            const r = await fetch('/api/daily/' + uid, {method:'POST'});
            if((await r.json()).ok) { confetti({ particleCount: 150 }); refresh(); }
        }

        function copyRef() {
            const link = "https://t.me/" + '""" + BOT_USERNAME + r"""' + "?start=ref_" + uid;
            const el = document.createElement('textarea'); el.value = link; document.body.appendChild(el);
            el.select(); document.execCommand('copy'); document.body.removeChild(el);
            tg.showAlert("Link copied!");
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

async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(PreCheckoutQueryHandler(lambda u,c: u.pre_checkout_query.answer(ok=True)))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
