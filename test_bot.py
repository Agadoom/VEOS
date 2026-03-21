import os, asyncio, uvicorn, logging, time, random
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
        cols = [
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"), 
            ("streak", "INTEGER DEFAULT 0"), 
            ("wallet_address", "TEXT"),
            ("ref_count", "INTEGER DEFAULT 0"),
            ("last_energy_update", "BIGINT")
        ]
        for col, dtype in cols:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit(); c.close(); conn.close()

# --- BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("INSERT INTO users (user_id, name, energy, last_energy_update) VALUES (%s, %s, 100, %s) ON CONFLICT (user_id) DO NOTHING", (uid, name, int(time.time())))
        conn.commit(); c.close(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"🚀 Welcome to OWPC Hub, {name}!", reply_markup=kb)

# --- API ROUTES ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, last_energy_update, staked_amount, streak, wallet_address FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    current_e = min(MAX_ENERGY, (r[5] or 0) + ((now - (r[6] or now)) // 60) * REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    multiplier = 1.0 + ((r[7] or 0) / 100) * 0.1 + (score / 1000)

    c.execute("SELECT SUM(COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users")
    jackpot = (c.fetchone()[0] or 0) * 0.1
    
    c.execute("SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as tot FROM users ORDER BY tot DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    
    c.close(); conn.close()
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[4],
        "energy": int(current_e), "score": round(score, 2), "multiplier": round(multiplier, 2),
        "jackpot": round(jackpot, 2), "top": top, "staked": r[7] or 0, "streak": r[8] or 0, "wallet": r[9] or ""
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t, is_comodo = data.get("user_id"), data.get("token"), data.get("is_comodo")
    conn = get_db_conn(); c = conn.cursor()
    gain = 0.05 * (10 if is_comodo else 1)
    c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+%s, energy=GREATEST(0, energy-1), last_energy_update=%s WHERE user_id=%s AND energy > 0", (gain, int(time.time()), uid))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/stake")
async def stake_api(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users WHERE user_id=%s", (uid,))
    bal = c.fetchone()[0] or 0
    if bal >= 100:
        c.execute("UPDATE users SET p_genesis=p_genesis-34, p_unity=p_unity-33, p_veo=p_veo-33, staked_amount=COALESCE(staked_amount,0)+100 WHERE user_id=%s", (uid,))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"error": "Need 100 Assets"})

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
        :root { --bg: #050505; --card: #121214; --gold: #FFD700; --blue: #007AFF; --purple: #A259FF; --green: #34C759; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; }
        .ticker { background: #111; margin: -15px -15px 15px -15px; padding: 10px; font-size: 11px; color: var(--gold); border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; }
        
        .balance-card { text-align: center; padding: 30px; background: radial-gradient(circle at top, #1a1a1a, #000); border-radius: 24px; border: 1px solid #333; margin-bottom: 15px; position: relative; }
        .energy-bar { background: #222; height: 8px; border-radius: 4px; margin: 15px 0; overflow: hidden; border: 1px solid #333; }
        #e-fill { background: var(--green); height: 100%; width: 0%; transition: 0.3s; }

        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: bold; cursor: pointer; }
        .btn:active { transform: scale(0.95); }
        .btn:disabled { opacity: 0.3; }

        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.95); padding: 12px 25px; border-radius: 40px; display: flex; gap: 25px; border: 1px solid #333; backdrop-filter: blur(10px); z-index: 1000; }
        .nav-i { font-size: 22px; opacity: 0.4; } .nav-i.active { opacity: 1; color: var(--gold); }
        
        .floating { position: absolute; color: var(--gold); font-weight: bold; animation: floatUp 0.6s ease-out forwards; pointer-events: none; }
        @keyframes floatUp { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(-50px); } }
    </style>
</head>
<body>
    <div class="ticker" id="tk">JACKPOT: 0.00 $WPT • NODE STATUS: ONLINE • REWARDS: 10%</div>

    <div id="p-mine">
        <div class="balance-card" id="main-box">
            <small style="color:#888">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:48px; margin:10px 0;">0.00</h1>
            <div id="u-mult" style="font-size:11px; color:var(--green)">Multiplier: x1.0</div>
            <div class="energy-bar"><div id="e-fill"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:11px;"><span id="ev">100/100 ⚡</span><span>OWPC TERMINAL</span></div>
        </div>
        <div class="card"><div>GENESIS<div id="gv" style="color:var(--gold)">0.00</div></div><button class="btn" onclick="mine(event, 'genesis')">MINE</button></div>
        <div class="card"><div>UNITY<div id="uv" style="color:var(--blue)">0.00</div></div><button class="btn" onclick="mine(event, 'unity')">SYNC</button></div>
        <div class="card"><div>VEO AI<div id="vv" style="color:var(--purple)">0.00</div></div><button class="btn" onclick="mine(event, 'veo')" style="background:var(--purple); color:#FFF">EXEC</button></div>
    </div>

    <div id="p-pill" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">$WPT PILLARS</h3>
        <div class="card"><b>WPT Token</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Unity Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Veo AI</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Genesis</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA')">GO</button></div>
    </div>

    <div id="p-lead" style="display:none"><h3 style="text-align:center">LEADERBOARD</h3><div id="rl"></div></div>

    <div id="p-stake" style="display:none">
        <h3 style="text-align:center">STAKING & NODES</h3>
        <div class="card"><div><b>Active Stake</b></div><b id="u-staked" style="color:var(--gold)">0</b></div>
        <div class="card"><div><b>Stake 100 Assets</b><br><small>+0.1x Multiplier</small></div><button class="btn" onclick="stake()">STAKE</button></div>
        <div class="card"><b>Invite Friends</b><button class="btn" onclick="share()">INVITE</button></div>
    </div>

    <div class="nav">
        <div onclick="sw('mine')" id="n-mine" class="nav-i active">🏠</div>
        <div onclick="sw('pill')" id="n-pill" class="nav-i">📊</div>
        <div onclick="sw('lead')" id="n-lead" class="nav-i">🏆</div>
        <div onclick="sw('stake')" id="n-stake" class="nav-i">⚙️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let isComodo = false, curE = 100;

        async function load() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('tot').innerText = d.score.toFixed(2);
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('u-mult').innerText = "Multiplier: x" + d.multiplier;
            document.getElementById('u-staked').innerText = d.staked;
            document.getElementById('tk').innerText = `JACKPOT: ${d.jackpot} $WPT • NODE STATUS: ONLINE • REWARDS: 10%`;
            curE = d.energy;
            document.getElementById('e-fill').style.width = curE + "%";
            document.getElementById('ev').innerText = curE + "/100 ⚡";
            
            let h=""; d.top.forEach((u,i)=>{ h+=`<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
            document.getElementById('rl').innerHTML = h;
        }

        async function mine(e, t) {
            if(curE <= 0) return;
            if(!isComodo && Math.random() < 0.01) startComodo();
            
            const f = document.createElement('div'); f.className='floating'; f.innerText='+0.05';
            f.style.left=e.pageX+'px'; f.style.top=e.pageY+'px'; document.body.appendChild(f);
            setTimeout(()=>f.remove(),600);

            curE--; updateUI();
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t, is_comodo:isComodo})});
            load(); tg.HapticFeedback.impactOccurred('light');
        }

        function updateUI() {
            document.getElementById('e-fill').style.width = curE + "%";
            document.getElementById('ev').innerText = curE + "/100 ⚡";
        }

        function startComodo() {
            isComodo = true; document.getElementById('main-box').style.borderColor = 'var(--gold)';
            setTimeout(() => { isComodo = false; document.getElementById('main-box').style.borderColor = '#333'; }, 15000);
        }

        async function stake() {
            const r = await fetch('/api/stake', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            if(r.ok) { confetti(); load(); } else { tg.showAlert("Need 100 assets!"); }
        }

        function share() { tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/owpcsbot?start=${uid}&text=🚀 Join my mining node!`); }
        function sw(p) { ['mine','pill','lead','stake'].forEach(i=>{document.getElementById('p-'+i).style.display=(i===p?'block':'none'); document.getElementById('n-'+i).classList.toggle('active',i===p);}); }
        
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
