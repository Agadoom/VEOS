import os, asyncio, uvicorn, logging, time, random, datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from data_conx import init_db, get_db_conn

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
RAW_URL = os.getenv("WEBAPP_URL", "")
WEBAPP_URL = RAW_URL if RAW_URL.startswith("http") else f"https://{RAW_URL}"

logging.basicConfig(level=logging.INFO)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MAX_ENERGY = 100
REGEN_RATE = 1 

# --- AUTO-PATCH DB ---
def patch_db():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        # On s'assure que toutes les colonnes nécessaires existent
        tables = [
            ("withdrawals", "id SERIAL PRIMARY KEY, user_id BIGINT, amount DOUBLE PRECISION, wallet TEXT, status TEXT DEFAULT 'PENDING', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]
        for tname, schema in tables:
            try: c.execute(f"CREATE TABLE IF NOT EXISTS {tname} ({schema})")
            except: pass
            
        cols = [
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"), 
            ("streak", "INTEGER DEFAULT 0"), 
            ("wallet_address", "TEXT"),
            ("ref_claimed", "INTEGER DEFAULT 0")
        ]
        for col, dtype in cols:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit(); c.close(); conn.close()

# --- LOGIQUE TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("INSERT INTO users (user_id, name, energy, last_energy_update) VALUES (%s, %s, %s, %s) ON CONFLICT (user_id) DO NOTHING", 
                  (uid, name, MAX_ENERGY, int(time.time())))
        conn.commit(); c.close(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ACCESS HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"🚀 Welcome to OWPC Terminal, {name}.", reply_markup=kb)

# --- API ROUTES ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, last_energy_update, staked_amount, wallet_address FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    current_e = min(MAX_ENERGY, (r[5] or 0) + ((now - (r[6] or now)) // 60) * REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    
    c.execute("SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as tot FROM users ORDER BY tot DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    
    c.execute("SELECT SUM(COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users")
    jackpot = (c.fetchone()[0] or 0) * 0.1
    
    c.close(); conn.close()
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "name": r[4],
        "energy": int(current_e), "score": round(score, 2), "wallet": r[8] or "",
        "top": top, "jackpot": round(jackpot, 2), "staked": r[7] or 0
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t, mult = data.get("user_id"), data.get("token"), data.get("mult", 1)
    conn = get_db_conn(); c = conn.cursor()
    gain = 0.05 * mult
    c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+%s, energy=GREATEST(0, energy-1), last_energy_update=%s WHERE user_id=%s AND energy > 0", (gain, int(time.time()), uid))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/gift")
async def claim_gift(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET p_genesis = COALESCE(p_genesis,0) + 5 WHERE user_id = %s", (uid,))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/wallet/save")
async def save_wallet(request: Request):
    data = await request.json(); uid, w = data.get("user_id"), data.get("wallet")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET wallet_address = %s WHERE user_id = %s", (w, uid))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/withdraw")
async def withdraw_api(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)), wallet_address FROM users WHERE user_id=%s", (uid,))
    res = c.fetchone()
    if res and res[0] >= 100 and res[1]:
        c.execute("UPDATE users SET p_genesis=0, p_unity=0, p_veo=0 WHERE user_id=%s", (uid,))
        c.execute("INSERT INTO withdrawals (user_id, amount, wallet) VALUES (%s, %s, %s)", (uid, res[0], res[1]))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"error": "Min 100 Assets + Wallet Required"})

# --- INTERFACE ---
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
        :root { --bg: #050505; --card: #121214; --gold: #FFD700; --blue: #007AFF; --purple: #A259FF; --green: #34C759; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; overflow-x: hidden; }
        
        .ticker-wrap { background: #111; margin: -15px -15px 15px -15px; overflow: hidden; white-space: nowrap; border-bottom: 1px solid #222; padding: 10px 0; }
        .ticker { display: inline-block; animation: scroll 20s linear infinite; font-family: monospace; font-size: 11px; color: var(--gold); }
        @keyframes scroll { from { transform: translateX(100%); } to { transform: translateX(-100%); } }

        .balance-main { text-align: center; padding: 30px; background: radial-gradient(circle at top, #1a1a1a, #000); border-radius: 24px; border: 1px solid #333; margin-bottom: 15px; transition: 0.3s; }
        .comodo-glow { border-color: var(--gold); box-shadow: 0 0 25px rgba(255,215,0,0.5); transform: scale(1.02); }

        .energy-container { background: #222; height: 10px; border-radius: 5px; margin: 15px 0; overflow: hidden; border: 1px solid #333; }
        #e-fill { background: linear-gradient(90deg, var(--green), var(--gold)); width: 100%; height: 100%; transition: 0.3s; }

        .card { background: var(--card); padding: 15px; border-radius: 16px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: bold; cursor: pointer; }
        .btn:disabled { opacity: 0.3; filter: grayscale(1); }

        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.95); padding: 12px 25px; border-radius: 40px; display: flex; gap: 30px; border: 1px solid #333; backdrop-filter: blur(10px); }
        .nav-i { font-size: 24px; opacity: 0.3; transition: 0.3s; } .nav-i.active { opacity: 1; color: var(--gold); }
        
        #comodo-notif { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: var(--gold); color: #000; padding: 20px; border-radius: 20px; font-weight: 900; z-index: 2000; display: none; }
    </style>
</head>
<body>
    <div id="comodo-notif">🔥 COMODO X10 !!!</div>

    <div class="ticker-wrap"><div class="ticker" id="tk">OWPC TERMINAL ACTIVE • JACKPOT: 0.00 • SYSTEM STATUS: OPTIMIZED • </div></div>

    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
        <div id="un" style="font-weight:bold; color:var(--blue)">...</div>
        <button id="gift-btn" class="btn" style="background:var(--gold)" onclick="handleGift()">🎁 GIFT</button>
    </div>

    <div id="p-mine">
        <div class="balance-main" id="main-box">
            <small style="color:#888">AVAILABLE ASSETS</small>
            <h1 id="tv" style="font-size:45px; margin:10px 0;">0.00</h1>
            <div class="energy-container"><div id="e-fill"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:11px;">
                <span id="ev">100/100 ⚡</span>
                <span id="mult-label" style="color:var(--gold)">x1</span>
            </div>
            <button id="refill-btn" class="btn" style="display:none; width:100%; margin-top:15px; background:var(--blue); color:#FFF" onclick="tg.showAlert('Drink Energy Drink in Store!')">⚡ OUT OF ENERGY</button>
        </div>
        <div class="card"><div>GENESIS<div id="gv" style="color:var(--gold)">0.00</div></div><button class="btn mine-btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div>UNITY<div id="uv" style="color:var(--blue)">0.00</div></div><button class="btn mine-btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div>VEO AI<div id="vv" style="color:var(--purple)">0.00</div></div><button class="btn mine-btn" onclick="mine('veo')" style="background:var(--purple); color:#FFF">EXEC</button></div>
    </div>

    <div id="p-stats" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">PILLARS & MISSIONS</h3>
        <div class="card"><b>Join Hub</b><button class="btn" onclick="tg.openLink('https://t.me/owpc_co')">JOIN</button></div>
        <div class="card"><b>Follow X</b><button class="btn" onclick="tg.openLink('https://twitter.com')">FOLLOW</button></div>
    </div>

    <div id="p-lead" style="display:none"><h3 style="text-align:center">LEADERBOARD</h3><div id="rl"></div></div>

    <div id="p-wall" style="display:none">
        <h3 style="text-align:center">WALLET</h3>
        <div class="card"><input type="text" id="wi" placeholder="TON Address" style="background:#000; color:#FFF; border:1px solid #333; padding:10px; border-radius:10px; width:60%;"> <button class="btn" onclick="saveW()" style="background:var(--green); color:#FFF">SAVE</button></div>
        <div class="balance-main" style="border-color:var(--blue)">
            <h2 id="wv" style="font-size:35px;">0.00</h2>
            <button class="btn" style="width:100%; background:var(--blue); color:#FFF" onclick="reqW()">WITHDRAW</button>
        </div>
    </div>

    <div class="nav">
        <div onclick="sw('mine')" id="n-mine" class="nav-i active">🏠</div>
        <div onclick="sw('stats')" id="n-stats" class="nav-i">📊</div>
        <div onclick="sw('lead')" id="n-lead" class="nav-i">🏆</div>
        <div onclick="sw('wall')" id="n-wall" class="nav-i">💳</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let curE = 100, mult = 1, isComodo = false;

        async function load() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('un').innerText = d.name.toUpperCase();
            document.getElementById('tv').innerText = d.score.toFixed(2);
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('wv').innerText = d.score.toFixed(2);
            document.getElementById('tk').innerText = `OWPC TERMINAL ACTIVE • JACKPOT: ${d.jackpot} • SYSTEM STATUS: OPTIMIZED • `;
            curE = d.energy; updateUI();
            if(d.wallet) document.getElementById('wi').value = d.wallet;
            let h=""; d.top.forEach((u,i)=>{ h+=`<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
            document.getElementById('rl').innerHTML = h;
            checkGift();
        }

        function updateUI() {
            document.getElementById('e-fill').style.width = curE + "%";
            document.getElementById('ev').innerText = curE + "/100 ⚡";
            const btns = document.querySelectorAll('.mine-btn');
            btns.forEach(b => b.disabled = (curE <= 0));
            document.getElementById('refill-btn').style.display = (curE <= 0 ? 'block' : 'none');
        }

        async function mine(t) {
            if(curE <= 0) return;
            if(!isComodo && Math.random() < 0.01) startComodo();
            curE--; updateUI();
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t, mult: mult})});
            load(); tg.HapticFeedback.impactOccurred('light');
        }

        function startComodo() {
            isComodo = true; mult = 10;
            document.getElementById('comodo-notif').style.display = "block";
            document.getElementById('main-box').classList.add('comodo-glow');
            document.getElementById('mult-label').innerText = "x10 🔥";
            setTimeout(() => {
                isComodo = false; mult = 1;
                document.getElementById('comodo-notif').style.display = "none";
                document.getElementById('main-box').classList.remove('comodo-glow');
                document.getElementById('mult-label').innerText = "x1";
            }, 15000);
        }

        function checkGift() {
            const last = localStorage.getItem('gift_'+uid);
            const btn = document.getElementById('gift-btn');
            if(last && (Date.now() - last < 12*60*60*1000)) {
                btn.disabled = true;
                const hrs = Math.ceil((12*60*60*1000 - (Date.now() - last))/(1000*60*60));
                btn.innerText = hrs + "h";
            } else { btn.disabled = false; btn.innerText = "🎁 GIFT"; }
        }

        async function handleGift() {
            await fetch('/api/gift', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            localStorage.setItem('gift_'+uid, Date.now());
            confetti(); tg.showAlert("Gift: +5 Genesis Assets!"); load();
        }

        async function saveW() { await fetch('/api/wallet/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, wallet:document.getElementById('wi').value})}); tg.showAlert("Wallet Saved!"); }
        async function reqW() {
            const res = await fetch('/api/withdraw', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            if(res.ok){ confetti(); tg.showAlert("Withdrawal Requested!"); load(); } else { const e=await res.json(); tg.showAlert(e.error); }
        }

        function sw(p) { ['mine','stats','lead','wall'].forEach(i=>{document.getElementById('p-'+i).style.display=(i===p?'block':'none'); document.getElementById('n-'+i).classList.toggle('active',i===p);}); }
        load(); setInterval(load, 15000); tg.expand();
    </script>
</body>
</html>
"""

# --- MAIN RUNNER ---
async def main():
    patch_db() # Patch en premier
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start)) # 'start' est bien défini au-dessus
    
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")
    await uvicorn.Server(config).serve()

if __name__ == "__main__":
    asyncio.run(main())
