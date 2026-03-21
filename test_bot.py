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

# --- DATABASE PATCH ---
def patch_db():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        cols = [
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"), 
            ("streak", "INTEGER DEFAULT 0"), 
            ("wallet_address", "TEXT"),
            ("last_energy_update", "BIGINT")
        ]
        for col, dtype in cols:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit(); c.close(); conn.close()

# --- BADGE LOGIC ---
def get_badge(score):
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
        c.execute("INSERT INTO users (user_id, name, energy, last_energy_update) VALUES (%s, %s, %s, %s) ON CONFLICT (user_id) DO NOTHING", 
                  (uid, name, MAX_ENERGY, int(time.time())))
        conn.commit(); c.close(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ENTER HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to the OWPC Ecosystem.", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, last_energy_update, staked_amount, streak FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    current_e = min(MAX_ENERGY, (r[5] or 0) + ((now - (r[6] or now)) // 60) * REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, b_color = get_badge(score)
    multiplier = 1.0 + ((r[7] or 0) / 100) * 0.1 + (score / 1000)

    # Global Jackpot (10% de tous les points générés)
    c.execute("SELECT SUM(COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users")
    total_net = c.fetchone()[0] or 0
    
    # Leaderboard
    c.execute("SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as tot FROM users ORDER BY tot DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    
    c.close(); conn.close()
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "name": r[4], "rc": r[3] or 0,
        "energy": int(current_e), "score": round(score, 2), "multiplier": round(multiplier, 2),
        "badge": badge, "badge_color": b_color, "jackpot": round(total_net * 0.1, 2),
        "top": top, "staked": r[7] or 0, "streak": r[8] or 0
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t, comodo = data.get("user_id"), data.get("token"), data.get("is_comodo")
    conn = get_db_conn(); c = conn.cursor()
    # Bonus Comodo x10 si actif
    gain = 0.05 * (10 if comodo else 1)
    c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+%s, energy=GREATEST(0, energy-1), last_energy_update=%s WHERE user_id=%s AND energy > 0", (gain, int(time.time()), uid))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/gift")
async def gift_api(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET p_genesis = COALESCE(p_genesis,0) + 5, streak = COALESCE(streak,0) + 1 WHERE user_id = %s", (uid,))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

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
        body { background: var(--bg); color: #FFF; font-family: 'Courier New', monospace; margin: 0; padding: 15px; padding-bottom: 90px; }
        
        .ticker-header { background: #111; margin: -15px -15px 15px -15px; padding: 10px; border-bottom: 1px solid #333; font-size: 11px; white-space: nowrap; overflow: hidden; }
        .ticker-move { display: inline-block; animation: scroll 15s linear infinite; color: var(--gold); }
        @keyframes scroll { from { transform: translateX(100%); } to { transform: translateX(-100%); } }

        .balance-box { text-align: center; padding: 30px; background: radial-gradient(circle at top, #1a1a1a, #000); border-radius: 24px; border: 1px solid #333; margin-bottom: 15px; position: relative; }
        .comodo-active { border-color: var(--gold); box-shadow: 0 0 20px var(--gold); }
        
        .energy-bar { background: #222; height: 8px; border-radius: 4px; margin: 15px 0; overflow: hidden; }
        #e-fill { background: linear-gradient(90deg, var(--green), var(--gold)); height: 100%; width: 0%; transition: 0.3s; }

        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 900; }
        .btn:disabled { opacity: 0.3; }

        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); padding: 12px 25px; border-radius: 40px; display: flex; gap: 25px; border: 1px solid #333; backdrop-filter: blur(10px); }
        .nav-i { font-size: 22px; opacity: 0.4; } .nav-i.active { opacity: 1; color: var(--gold); }
    </style>
</head>
<body>
    <div class="ticker-header"><div class="ticker-move" id="tk">JACKPOT: 0.00 $WPT • STATUS: NODE CONNECTED • REWARDS: ACTIVE</div></div>

    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
        <div><b id="u-name">...</b><br><small id="u-badge" style="font-size:10px;">🥉 Bronze</small></div>
        <button id="gift-btn" class="btn" style="background:var(--gold)" onclick="doGift()">🎁 GIFT</button>
    </div>

    <div id="p-mine">
        <div class="balance-box" id="main-box">
            <div id="comodo-txt" style="display:none; color:var(--gold); font-weight:bold; font-size:12px;">🔥 COMODO X10 ACTIVE</div>
            <small style="color:#888">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:48px; margin:10px 0;">0.00</h1>
            <div id="u-mult" style="font-size:11px; color:var(--green)">Multiplier: x1.0</div>
            <div class="energy-bar"><div id="e-fill"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:10px;"><span id="ev">100/100 ⚡</span><span>$WPT HUB</span></div>
        </div>
        <div class="card"><div>GENESIS<div id="gv" style="color:var(--gold)">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div>UNITY<div id="uv" style="color:var(--blue)">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div>VEO AI<div id="vv" style="color:var(--purple)">0.00</div></div><button class="btn" onclick="mine('veo')" style="background:var(--purple); color:#FFF">EXEC</button></div>
    </div>

    <div id="p-pill" style="display:none">
        <h3 style="color:var(--gold)">PILLARS REWARDS</h3>
        <div class="card"><b>WPT Token</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">CLAIM</button></div>
        <div class="card"><b>Unity Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA')">CLAIM</button></div>
        <div class="card"><b>Veo AI</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA')">CLAIM</button></div>
    </div>

    <div id="p-lead" style="display:none"><h3>TOP NODES</h3><div id="rl"></div></div>

    <div class="nav">
        <div onclick="sw('mine')" id="n-mine" class="nav-i active">🏠</div>
        <div onclick="sw('pill')" id="n-pill" class="nav-i">📊</div>
        <div onclick="sw('lead')" id="n-lead" class="nav-i">🏆</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let isComodo = false, curE = 100;

        async function load() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('u-name').innerText = d.name.toUpperCase();
            document.getElementById('tot').innerText = d.score.toFixed(2);
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('u-mult').innerText = "Multiplier: x" + d.multiplier;
            document.getElementById('u-badge').innerText = d.badge;
            document.getElementById('u-badge').style.color = d.badge_color;
            document.getElementById('tk').innerText = `JACKPOT: ${d.jackpot} $WPT • STATUS: NODE CONNECTED • REWARDS: ACTIVE`;
            curE = d.energy;
            document.getElementById('e-fill').style.width = curE + "%";
            document.getElementById('ev').innerText = curE + "/100 ⚡";
            
            let h=""; d.top.forEach((u,i)=>{ h+=`<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
            document.getElementById('rl').innerHTML = h;
            checkGift();
        }

        async function mine(t) {
            if(curE <= 0) return;
            if(!isComodo && Math.random() < 0.01) startComodo();
            curE--; 
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t, is_comodo:isComodo})});
            load(); tg.HapticFeedback.impactOccurred('light');
        }

        function startComodo() {
            isComodo = true; 
            document.getElementById('main-box').classList.add('comodo-active');
            document.getElementById('comodo-txt').style.display = 'block';
            setTimeout(() => {
                isComodo = false;
                document.getElementById('main-box').classList.remove('comodo-active');
                document.getElementById('comodo-txt').style.display = 'none';
            }, 15000);
        }

        function checkGift() {
            const last = localStorage.getItem('gift_'+uid);
            const btn = document.getElementById('gift-btn');
            if(last && (Date.now() - last < 12*60*60*1000)) {
                btn.disabled = true; btn.innerText = "⏳ 12h";
            } else { btn.disabled = false; btn.innerText = "🎁 GIFT"; }
        }

        async function doGift() {
            await fetch('/api/gift', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            localStorage.setItem('gift_'+uid, Date.now());
            confetti(); load();
        }

        function sw(p) { ['mine','pill','lead'].forEach(i=>{document.getElementById('p-'+i).style.display=(i===p?'block':'none'); document.getElementById('n-'+i).classList.toggle('active',i===p);}); }
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
