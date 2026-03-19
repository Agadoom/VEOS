import os, sqlite3, asyncio, uvicorn, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = os.getenv("BOT_USERNAME", "OWPCsbot")

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "owpc_pro_v37.db")

logging.basicConfig(level=logging.INFO)
app = FastAPI()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Ajout de total_clicks pour le profil
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  p_genesis REAL DEFAULT 0, p_unity REAL DEFAULT 0, 
                  p_veo REAL DEFAULT 0, ref_count INTEGER DEFAULT 0,
                  total_clicks INTEGER DEFAULT 0,
                  last_daily INTEGER DEFAULT 0, referred_by INTEGER)''')
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
    await update.message.reply_text(f"Welcome to the Ecosystem, {name}!", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_daily, total_clicks, name FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    c.execute("SELECT token, amount, timestamp FROM logs WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,))
    history = [{"t": x[0], "a": x[1], "ts": x[2]} for x in c.fetchall()]
    c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    conn.close()
    if not r: return None
    can_daily = (int(time.time()) - r[4]) > 86400
    return {
        "g": r[0], "u": r[1], "v": r[2], "rc": r[3], 
        "can_daily": can_daily, "clicks": r[5], "name": r[6],
        "history": history, "top": top
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    col = {"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}.get(t)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # Mise à jour du gain ET du nombre de clics
    c.execute(f"UPDATE users SET {col} = {col} + ?, total_clicks = total_clicks + 1 WHERE user_id = ?", (gain, uid))
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
        c.execute("UPDATE users SET p_unity = p_unity + 1.0, last_daily = ?, total_clicks = total_clicks + 1 WHERE user_id = ?", (now, uid))
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
        :root { --bg: #000; --card: #111; --blue: #007AFF; --green: #34C759; --gold: #FFD700; --text: #8E8E93; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 0; overflow-x: hidden; }
        
        /* User Profile Header */
        .profile-bar { background: #111; padding: 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #222; position: sticky; top: 0; z-index: 100; }
        .user-info { display: flex; align-items: center; gap: 10px; }
        .avatar { width: 35px; height: 35px; background: var(--blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; }
        .stats-top { display: flex; gap: 15px; font-size: 12px; }
        .stat-item { text-align: right; }
        .stat-item b { color: var(--gold); display: block; font-size: 14px; }

        .container { padding: 15px; padding-bottom: 90px; }
        .header { font-weight: 800; font-size: 22px; color: var(--blue); text-align: center; margin: 10px 0 20px 0; }
        .balance { text-align: center; margin-bottom: 20px; border: 1px solid #222; padding: 20px; border-radius: 25px; background: linear-gradient(145deg, #050505, #111); }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1C1C1E; position: relative; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 15px; border-radius: 10px; font-weight: 700; cursor: pointer; min-width: 85px; z-index: 2; transition: 0.2s; }
        .btn:active { transform: scale(0.95); }
        
        .cps-box { text-align: center; font-size: 11px; color: var(--gold); margin-bottom: 10px; font-weight: bold; }
        .section-title { font-size: 13px; font-weight: 700; color: var(--text); margin: 20px 0 10px 5px; text-transform: uppercase; }
        .history-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #1c1c1e; font-size: 13px; color: var(--text); }
        
        .floating-text { position: absolute; font-weight: bold; pointer-events: none; animation: floatUp 0.8s ease-out forwards; z-index: 10; font-size: 18px; }
        @keyframes floatUp { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(-50px); } }

        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.9); backdrop-filter: blur(15px); padding: 10px 30px; border-radius: 35px; display: flex; gap: 40px; border: 1px solid #333; z-index: 1000; }
        .nav-item { font-size: 24px; opacity: 0.3; cursor: pointer; }
        .nav-item.active { opacity: 1; transform: scale(1.2); }
        .pill-link { background: #1C1C1E; color: #FFF; text-decoration: none; padding: 8px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; border: 1px solid #333; }
    </style>
</head>
<body>
    <div class="profile-bar">
        <div class="user-info">
            <div class="avatar" id="u-init">?</div>
            <div style="font-size: 14px; font-weight: 600;" id="u-name">User</div>
        </div>
        <div class="stats-top">
            <div class="stat-item">CLICKS <b id="top-clicks">0</b></div>
            <div class="stat-item">TOTAL EARNED <b id="top-earned">0.00</b></div>
        </div>
    </div>

    <div class="container">
        <div id="p-mine">
            <div class="header">OWPC HUB</div>
            <button id="daily-btn" class="btn" style="width:100%; background:var(--blue); color:#FFF; margin-bottom:15px; height:45px" onclick="claimDaily()">CLAIM DAILY REWARD</button>
            
            <div class="balance"><span>WALLET BALANCE</span><h1 id="tot" style="font-size:42px; margin:5px 0">0.00</h1></div>
            <div class="cps-box">STABILITY: <span id="cps-val">0</span> CLICKS/S</div>

            <div class="section-title">Mining Units</div>
            <div class="card">
                <div><small style="color:var(--green)">GENESIS</small><div id="gv" style="font-size:18px; font-weight:700">0.00</div></div>
                <button class="btn" onclick="mine('genesis', event)" style="background:var(--green)">CLAIM</button>
            </div>
            <div class="card">
                <div><small style="color:#FFF">UNITY</small><div id="uv" style="font-size:18px; font-weight:700">0.00</div></div>
                <button class="btn" onclick="mine('unity', event)">SYNC</button>
            </div>
            <div class="card">
                <div><small style="color:var(--blue)">VEO AI</small><div id="vv" style="font-size:18px; font-weight:700">0.00</div></div>
                <button class="btn" onclick="mine('veo', event)" style="background:var(--blue);color:#FFF">COMPUTE</button>
            </div>

            <div class="section-title">Ecosystem Pillars</div>
            <div class="card"><div><b>Genesis</b></div><a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" class="pill-link">OPEN ↗</a></div>
            <div class="card"><div><b>Unity</b></div><a href="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA" class="pill-link">OPEN ↗</a></div>
            <div class="card"><div><b>Veo AI</b></div><a href="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA" class="pill-link">OPEN ↗</a></div>

            <div class="section-title">History</div>
            <div id="history-list"></div>
        </div>

        <div id="p-tasks" style="display:none">
            <div class="header">LEADERBOARD</div>
            <div class="card" style="flex-direction:column; align-items:center; gap:10px">
                <button class="btn" style="width:100%" onclick="copyRef()">COPY MY REF LINK</button>
                <div style="font-size:12px; color:var(--green)">Total Referred: <span id="rc">0</span></div>
            </div>
            <div id="rank-list"></div>
        </div>
    </div>

    <div class="nav">
        <div id="n-mine" onclick="show('mine')" class="nav-item active">🏠</div>
        <div id="n-tasks" onclick="show('tasks')" class="nav-item">🏆</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;
        let clickCount = 0;

        setInterval(() => { document.getElementById('cps-val').innerText = clickCount; clickCount = 0; }, 1000);

        function createFloatingText(e, text, color) {
            const el = document.createElement('div');
            el.className = 'floating-text';
            el.innerText = text;
            el.style.left = (e.clientX - 20) + 'px';
            el.style.top = (e.clientY - 20) + 'px';
            el.style.color = color;
            document.body.appendChild(el);
            setTimeout(() => el.remove(), 800);
        }

        async function refresh() {
            if(!uid) return;
            const r = await fetch('/api/user/' + uid);
            const d = await r.json();
            
            // Profil UI
            document.getElementById('u-name').innerText = d.name;
            document.getElementById('u-init').innerText = d.name[0].toUpperCase();
            document.getElementById('top-clicks').innerText = d.clicks;
            
            const total = (d.g + d.u + d.v).toFixed(2);
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('tot').innerText = total;
            document.getElementById('top-earned').innerText = total;
            
            document.getElementById('rc').innerText = d.rc;
            document.getElementById('daily-btn').disabled = !d.can_daily;
            if(!d.can_daily) document.getElementById('daily-btn').innerText = "DAILY CLAIMED";

            let h_html = "";
            d.history.forEach(h => {
                let timeStr = new Date(h.ts * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                h_html += `<div class="history-item"><span>${h.t.toUpperCase()}</span><b>+${h.a}</b><span>${timeStr}</span></div>`;
            });
            document.getElementById('history-list').innerHTML = h_html;
            
            let r_html = "";
            d.top.forEach((u, i) => { r_html += `<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
            document.getElementById('rank-list').innerHTML = r_html;
        }

        async function mine(t, e) {
            clickCount++;
            tg.HapticFeedback.impactOccurred('light');
            createFloatingText(e, t==='veo'?'+0.01':'+0.05', t==='veo'?'#007AFF':'#34C759');
            
            // Update UI instantanément pour la fluidité
            let clickEl = document.getElementById('top-clicks');
            clickEl.innerText = parseInt(clickEl.innerText) + 1;

            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            refresh();
        }

        async function claimDaily() {
            const r = await fetch('/api/daily/' + uid, {method:'POST'});
            if((await r.json()).ok) { confetti({ particleCount: 150 }); refresh(); }
        }

        function copyRef() {
            const link = "https://t.me/""" + BOT_USERNAME + r"""?start=ref_" + uid;
            const el = document.createElement('textarea'); el.value = link; document.body.appendChild(el);
            el.select(); document.execCommand('copy'); document.body.removeChild(el);
            tg.showAlert("Link copied!");
        }

        function show(p) {
            document.getElementById('p-mine').style.display = (p=='mine'?'block':'none');
            document.getElementById('p-tasks').style.display = (p=='tasks'?'block':'none');
            document.getElementById('n-mine').classList.toggle('active', p=='mine');
            document.getElementById('n-tasks').classList.toggle('active', p=='tasks');
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
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
