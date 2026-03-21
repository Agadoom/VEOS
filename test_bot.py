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

# --- AUTO-PATCH DB (Toutes tes colonnes sont ici) ---
def patch_db():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        cols = [
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"), 
            ("streak", "INTEGER DEFAULT 0"), 
            ("wallet_address", "TEXT"),
            ("ref_claimed", "INTEGER DEFAULT 0"),
            ("last_energy_update", "BIGINT")
        ]
        for col, dtype in cols:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit(); c.close(); conn.close()

# --- UTILS (Tes Badges originaux) ---
def get_badge_info(score):
    if score >= 500: return "💎 Diamond", "#00D1FF"
    if score >= 150: return "🥇 Gold", "#FFD700"
    if score >= 50:  return "🥈 Silver", "#C0C0C0"
    return "🥉 Bronze", "#CD7F32"

# --- BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("INSERT INTO users (user_id, name, energy, last_energy_update, staked_amount) VALUES (%s, %s, %s, %s, 0) ON CONFLICT (user_id) DO NOTHING", 
                  (uid, name, MAX_ENERGY, int(time.time())))
        conn.commit(); c.close(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"✨ Welcome to OWPC DePIN Hub, {name}!", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, last_energy_update, staked_amount, wallet_address, streak FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    current_e = min(MAX_ENERGY, (r[5] or 0) + ((now - (r[6] or now)) // 60) * REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, b_color = get_badge_info(score)
    
    # Calcul du multiplicateur basé sur ton code (Stake + Score)
    multiplier = 1.0 + ((r[7] or 0) / 100) * 0.1 + (score / 1000)

    c.execute("SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as tot FROM users ORDER BY tot DESC LIMIT 8")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    
    c.close(); conn.close()
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "name": r[4], "rc": r[3] or 0,
        "energy": int(current_e), "score": round(score, 2), "multiplier": round(multiplier, 2),
        "badge": badge, "badge_color": b_color, "staked": r[7] or 0, "streak": r[9] or 0,
        "top": top, "wallet": r[8] or ""
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t, is_comodo = data.get("user_id"), data.get("token"), data.get("is_comodo", False)
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, staked_amount, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users WHERE user_id=%s", (uid,))
    res = c.fetchone()
    now = int(time.time())
    current_e = min(MAX_ENERGY, (res[0] or 0) + ((now - (res[1] or now)) // 60) * REGEN_RATE)
    
    if current_e >= 1:
        mult = (1.0 + ((res[2] or 0) / 100) * 0.1 + (res[3] / 1000)) * (10 if is_comodo else 1)
        c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+%s, energy=%s, last_energy_update=%s WHERE user_id=%s", (0.05 * mult, current_e - 1, now, uid))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"error": "No energy"})

@app.post("/api/daily")
async def daily_api(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET p_genesis = COALESCE(p_genesis,0) + 5, streak = COALESCE(streak,0) + 1 WHERE user_id = %s", (uid,))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

@app.post("/api/stake")
async def stake_api(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users WHERE user_id=%s", (uid,))
    total = c.fetchone()[0] or 0
    if total >= 100:
        c.execute("UPDATE users SET p_genesis=p_genesis-34, p_unity=p_unity-33, p_veo=p_veo-33, staked_amount=COALESCE(staked_amount,0)+100 WHERE user_id=%s", (uid,))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"error": "Need 100 Assets"})

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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --green: #34C759; --purple: #A259FF; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; }
        .ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px; font-size: 10px; display: flex; justify-content: space-between; border-bottom: 1px solid #333; }
        .profile { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #222; }
        .badge { font-size: 10px; padding: 3px 8px; border-radius: 6px; background: #222; }
        .balance-card { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #333; margin-bottom: 15px; position: relative; }
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; }
        #e-fill { background: var(--gold); height: 100%; width: 0%; transition: 0.3s; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; }
        .btn:disabled { opacity: 0.3; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 1000; }
        .nav-item { font-size: 20px; opacity: 0.4; } .nav-item.active { opacity: 1; color: var(--gold); }
        #comodo-ui { position: absolute; top: 10px; right: 10px; color: var(--gold); font-weight: bold; display: none; }
    </style>
</head>
<body>
    <div class="ticker">
        <span style="color:var(--gold)">REFS: <span id="u-refs">0</span></span>
        <span style="color:var(--green)">$WPT: ONLINE</span>
    </div>
    
    <div class="profile">
        <div><div id="u-name" style="font-weight:700;">...</div><div id="u-badge" class="badge">...</div></div>
        <button id="gift-btn" class="btn" style="background:var(--gold);" onclick="claimGift()">🎁 GIFT</button>
    </div>

    <div id="p-mine">
        <div class="balance-card" id="main-box">
            <div id="comodo-ui">🔥 X10 MODE</div>
            <small style="color:#888">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:45px; margin:10px 0;">0.00</h1>
            <div id="u-mult" style="font-size:11px; color:var(--green)">⚡ Multiplier: x1.0</div>
            <div class="energy-bar"><div id="e-fill"></div></div>
            <div id="e-text" style="font-size:11px; color:var(--gold);">⚡ 0 / 100</div>
        </div>
        <div class="card"><div>GENESIS<div id="gv">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div>UNITY<div id="uv">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div>VEO AI<div id="vv">0.00</div></div><button class="btn" onclick="mine('veo')" style="background:var(--purple); color:#FFF">EXEC</button></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">$WPT PILLARS</h3>
        <div class="card"><b>WPT Token</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Unity Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Veo AI Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Genesis Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA')">GO</button></div>
    </div>

    <div id="p-leader" style="display:none"><h3 style="text-align:center">TOP NODES</h3><div id="rank-list"></div></div>

    <div id="p-settings" style="display:none">
        <h3 style="color:var(--gold)">STAKING & ENERGY</h3>
        <div class="card"><div><b>Active Stake</b><br><small>Streak: <span id="u-streak">0</span> Days</small></div><div id="u-staked" style="color:var(--gold)">0</div></div>
        <div class="card"><div><b>Lock 100 Assets</b><br><small>+0.1x Boost</small></div><button class="btn" onclick="stake()">LOCK</button></div>
        <div class="card"><b>Community</b><button class="btn" onclick="tg.openLink('https://t.me/owpc_co')">JOIN</button></div>
    </div>

    <div class="nav">
        <div onclick="sw('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="sw('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="sw('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="sw('settings')" id="n-settings" class="nav-item">⚙️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let isComodo = false, multVal = 1;

        async function load() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('u-name').innerText = d.name;
            document.getElementById('u-badge').innerText = d.badge;
            document.getElementById('u-badge').style.color = d.badge_color;
            document.getElementById('u-refs').innerText = d.rc;
            document.getElementById('tot').innerText = d.score.toFixed(2);
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('u-mult').innerText = `⚡ Multiplier: x${d.multiplier}`;
            document.getElementById('e-fill').style.width = d.energy + "%";
            document.getElementById('e-text').innerText = `⚡ ${d.energy} / 100`;
            document.getElementById('u-streak').innerText = d.streak;
            document.getElementById('u-staked').innerText = d.staked;
            
            let h=""; d.top.forEach((u,i)=>{ h+=`<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
            document.getElementById('rank-list').innerHTML = h;
            checkGift();
        }

        async function mine(t) {
            if(!isComodo && Math.random() < 0.01) startComodo();
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t, is_comodo:isComodo})});
            load(); tg.HapticFeedback.impactOccurred('light');
        }

        function startComodo() {
            isComodo = true; document.getElementById('comodo-ui').style.display='block';
            document.getElementById('main-box').style.borderColor = 'var(--gold)';
            setTimeout(() => { isComodo = false; document.getElementById('comodo-ui').style.display='none'; document.getElementById('main-box').style.borderColor = '#333'; }, 15000);
        }

        function checkGift() {
            const last = localStorage.getItem('gift_'+uid);
            const btn = document.getElementById('gift-btn');
            if(last && (Date.now() - last < 12*60*60*1000)) {
                btn.disabled = true; btn.innerText = "⏳ Locked";
            } else { btn.disabled = false; btn.innerText = "🎁 GIFT"; }
        }

        async function claimGift() {
            await fetch('/api/daily', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            localStorage.setItem('gift_'+uid, Date.now());
            confetti(); load();
        }

        async function stake() {
            const r = await fetch('/api/stake', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            if(r.ok) { confetti(); load(); } else { tg.showAlert("Not enough assets!"); }
        }

        function sw(p) { ['mine','pillars','leader','settings'].forEach(i=>{document.getElementById('p-'+i).style.display=(i===p?'block':'none'); document.getElementById('n-'+i).classList.toggle('active',i===p);}); }
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
