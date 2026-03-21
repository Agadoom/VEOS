import os, asyncio, uvicorn, logging, time
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

# --- DB SYNC ---
def patch_db():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        try:
            c.execute("CREATE TABLE IF NOT EXISTS withdrawals (id SERIAL PRIMARY KEY, user_id BIGINT, amount DOUBLE PRECISION, wallet TEXT, status TEXT DEFAULT 'PENDING', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            conn.commit()
        except: conn.rollback()
        c.close(); conn.close()

# --- BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("INSERT INTO users (user_id, name, energy) VALUES (%s, %s, 100) ON CONFLICT (user_id) DO NOTHING", (uid, name))
        conn.commit(); c.close(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ACCESS TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC Network Nodes.", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, name, wallet_address, energy FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    
    c.execute("SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as tot FROM users ORDER BY tot DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    
    c.execute("SELECT SUM(COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users")
    jackpot = (c.fetchone()[0] or 0) * 0.1
    
    c.close(); conn.close()
    return {"g":r[0] or 0, "u":r[1] or 0, "v":r[2] or 0, "name":r[3], "score":round(score,2), "wallet":r[4] or "", "energy": r[5] or 100, "top":top, "jackpot":round(jackpot,2)}

@app.post("/api/gift")
async def claim_gift(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET p_genesis = COALESCE(p_genesis,0) + 5 WHERE user_id = %s", (uid,))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05, energy=GREATEST(0, energy-1) WHERE user_id=%s", (uid,))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

# --- UI ---
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
        body { background: var(--bg); color: #FFF; font-family: 'Inter', sans-serif; margin: 0; padding: 15px; overflow: hidden; }
        
        /* Ticker Animation */
        .ticker-wrap { background: #111; margin: -15px -15px 15px -15px; overflow: hidden; white-space: nowrap; border-bottom: 1px solid #222; padding: 8px 0; }
        .ticker { display: inline-block; animation: scroll 20s linear infinite; font-family: monospace; font-size: 12px; color: var(--gold); }
        @keyframes scroll { from { transform: translateX(100%); } to { transform: translateX(-100%); } }

        .balance-main { text-align: center; padding: 30px 10px; background: radial-gradient(circle at top, #1a1a1a, #050505); border-radius: 24px; border: 1px solid #333; margin-bottom: 15px; position: relative; overflow: hidden; }
        .card { background: var(--card); padding: 16px; border-radius: 16px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }
        
        /* Energy Bar */
        .energy-container { background: #222; height: 8px; border-radius: 10px; margin: 10px 0; overflow: hidden; border: 1px solid #333; }
        #energy-fill { background: linear-gradient(90deg, var(--gold), #FFA500); width: 100%; height: 100%; transition: 0.3s; }

        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: bold; cursor: pointer; }
        .btn:disabled { background: #333; color: #666; cursor: not-allowed; }
        .btn-g { background: var(--gold); }

        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.95); padding: 12px 25px; border-radius: 40px; display: flex; gap: 30px; border: 1px solid #333; backdrop-filter: blur(10px); }
        .nav-i { font-size: 24px; opacity: 0.3; } .nav-i.active { opacity: 1; color: var(--gold); }
    </style>
</head>
<body>
    <div class="ticker-wrap"><div class="ticker" id="tk">OWPC NETWORK ACTIVE • GLOBAL JACKPOT: 0.00 • NODE STATUS: OPTIMIZED • </div></div>

    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
        <div id="un" style="font-weight:bold; color:var(--blue)">...</div>
        <button id="gift-btn" class="btn btn-g" onclick="handleGift()">🎁 GIFT</button>
    </div>

    <div id="p-mine">
        <div class="balance-main">
            <small style="color:#666">TOTAL ASSETS</small>
            <h1 id="tv" style="font-size:45px; margin:5px 0;">0.00</h1>
            <div class="energy-container"><div id="energy-fill"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:10px; color:#888;"><span>⚡ ENERGY</span><span id="ev">100/100</span></div>
        </div>
        <div class="card"><div>GENESIS<div id="gv" style="color:var(--gold)">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div>UNITY<div id="uv" style="color:var(--blue)">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div>VEO AI<div id="vv" style="color:var(--purple)">0.00</div></div><button class="btn" onclick="mine('veo')" style="background:var(--purple); color:#FFF">EXECUTE</button></div>
    </div>

    <div id="p-stats" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">PILLARS & MISSIONS</h3>
        <div class="card"><b>Join Channel</b><button class="btn" onclick="tg.openLink('https://t.me/example')">JOIN</button></div>
        <div class="card"><b>Follow X</b><button class="btn" onclick="tg.openLink('https://twitter.com')">FOLLOW</button></div>
    </div>

    <div id="p-lead" style="display:none"><h3 style="text-align:center">LEADERBOARD</h3><div id="rl"></div></div>

    <div id="p-wall" style="display:none">
        <h3 style="text-align:center">WALLET</h3>
        <div class="card"><input type="text" id="wi" placeholder="TON Address" style="background:#000; color:#FFF; border:1px solid #333; padding:10px; border-radius:10px; width:60%;"></div>
        <button class="btn" style="width:100%; background:var(--blue); color:#FFF" onclick="tg.showAlert('Coming Soon')">WITHDRAW</button>
    </div>

    <div class="nav">
        <div onclick="sw('mine')" id="n-mine" class="nav-i active">🏠</div>
        <div onclick="sw('stats')" id="n-stats" class="nav-i">📊</div>
        <div onclick="sw('lead')" id="n-lead" class="nav-i">🏆</div>
        <div onclick="sw('wall')" id="n-wall" class="nav-i">💳</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        
        function updateGiftButton() {
            const last = localStorage.getItem('last_gift_' + uid);
            const btn = document.getElementById('gift-btn');
            if (last) {
                const diff = Date.now() - parseInt(last);
                const cooldown = 12 * 60 * 60 * 1000;
                if (diff < cooldown) {
                    btn.disabled = true;
                    const rem = Math.ceil((cooldown - diff) / (60 * 60 * 1000));
                    btn.innerText = rem + "h Left";
                    return;
                }
            }
            btn.disabled = false;
            btn.innerText = "🎁 GIFT";
        }

        async function load() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('un').innerText = d.name.toUpperCase();
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('tv').innerText = d.score.toFixed(2);
            document.getElementById('tk').innerText = `OWPC NETWORK ACTIVE • GLOBAL JACKPOT: ${d.jackpot} • NODE STATUS: OPTIMIZED • `;
            document.getElementById('energy-fill').style.width = d.energy + "%";
            document.getElementById('ev').innerText = d.energy + "/100";
            updateGiftButton();
            let h=""; d.top.forEach((u,i)=>{ h+=`<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
            document.getElementById('rl').innerHTML = h;
        }

        async function handleGift() {
            await fetch('/api/gift', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            localStorage.setItem('last_gift_' + uid, Date.now());
            confetti();
            tg.showAlert("Claimed +5 Genesis Assets!");
            load();
        }

        async function mine(t) {
            await fetch('/api/mine',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,token:t})});
            load(); tg.HapticFeedback.impactOccurred('light');
        }

        function sw(p) { ['mine','stats','lead','wall'].forEach(i=>{document.getElementById('p-'+i).style.display=(i===p?'block':'none'); document.getElementById('n-'+i).classList.toggle('active',i===p);}); }
        load(); setInterval(load, 10000); tg.expand();
    </script>
</body>
</html>
"""

async def main():
    patch_db()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize(); await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")).serve()

if __name__ == "__main__":
    asyncio.run(main())
