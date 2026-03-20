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
        for col, dtype in [("staked_amount", "DOUBLE PRECISION DEFAULT 0"), ("ref_claimed", "INTEGER DEFAULT 0"), ("auto_rate", "DOUBLE PRECISION DEFAULT 0.01")]:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit(); c.close(); conn.close()

patch_db()

# --- UTILS ---
def get_badge_info(score):
    if score >= 500: return "💎 Diamond", 1000, "#00D1FF"
    if score >= 150: return "🥇 Gold", 500, "#FFD700"
    if score >= 50:  return "🥈 Silver", 150, "#C0C0C0"
    return "🥉 Bronze", 50, "#CD7F32"

# --- BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id, name, referred_by, energy, last_energy_update, staked_amount) VALUES (%s, %s, %s, %s, %s, 0)", 
                      (uid, name, ref_id if ref_id != uid else None, MAX_ENERGY, int(time.time())))
            if ref_id and ref_id != uid:
                c.execute("UPDATE users SET ref_count = COALESCE(ref_count,0) + 1 WHERE user_id = %s", (ref_id,))
        conn.commit(); c.close(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 START NODE", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC DePIN Hub, {name}!", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn()
    if not conn: return JSONResponse(status_code=500, content={"error": "DB Connection failed"})
    c = conn.cursor()
    try:
        c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, last_energy_update, staked_amount, ref_claimed, auto_rate FROM users WHERE user_id=%s", (uid,))
        r = c.fetchone()
        if not r: return JSONResponse(status_code=404, content={"error": "User not found"})
        
        # Sécurité : On remplace les None par des valeurs par défaut
        g, u, v = r[0] or 0.0, r[1] or 0.0, r[2] or 0.0
        rc, name = r[3] or 0, r[4] or "Unknown"
        energy, last_upd = r[5] or 100, r[6] or int(time.time())
        staked, claimed = r[7] or 0.0, r[8] or 0
        auto_rate = r[9] or 0.01

        now = int(time.time())
        current_e = min(MAX_ENERGY, energy + ((now - last_upd) // 60) * REGEN_RATE)
        score = round(g + u + v, 2)
        badge, next_goal, b_color = get_badge_info(score)

        c.execute("SELECT name, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) as total FROM users ORDER BY total DESC LIMIT 5")
        top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
        
        c.execute("SELECT SUM(COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users")
        total_net = c.fetchone()[0] or 0
        
        return {
            "g": g, "u": u, "v": v, "rc": rc, "name": name,
            "energy": int(current_e), "max_energy": MAX_ENERGY, "badge": badge, "next_goal": next_goal, "badge_color": b_color,
            "top": top, "jackpot": round(total_net * 0.1, 2), "score": score,
            "multiplier": round(1.0 + (staked / 100) * 0.1 + (score / 1000), 2),
            "staked": staked, "pending_refs": max(0, rc - claimed), "auto_rate": auto_rate
        }
    except Exception as e:
        logging.error(f"Error in get_user: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        c.close(); conn.close()


@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t, combo = data.get("user_id"), data.get("token"), data.get("combo", False)
    gain = 0.12 if combo else 0.06
    conn = get_db_conn(); c = conn.cursor()
    c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+%s, energy=energy-1, last_energy_update=%s WHERE user_id=%s AND energy > 0", (gain, int(time.time()), uid))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

@app.post("/api/stake")
async def stake_api(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET p_genesis=p_genesis-34, p_unity=p_unity-33, p_veo=p_veo-33, staked_amount=staked_amount+100 WHERE user_id=%s AND (p_genesis+p_unity+p_veo) >= 100", (uid,))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

@app.post("/api/boost/energy")
async def boost_energy(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET p_genesis=p_genesis-17, p_unity=p_unity-17, p_veo=p_veo-16, energy=%s WHERE user_id=%s AND (p_genesis+p_unity+p_veo) >= 50", (MAX_ENERGY, uid))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

@app.post("/api/daily")
async def daily_api(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET p_genesis = COALESCE(p_genesis,0) + 5 WHERE user_id = %s", (uid,))
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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --green: #34C759; --purple: #A259FF; --red: #FF3B30; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow: hidden; visibility: hidden; }
        
        .header-ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px; font-size: 9px; display: flex; justify-content: space-between; border-bottom: 1px solid #333; }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2c2c2e; }
        .badge-tag { font-size: 9px; padding: 2px 6px; border-radius: 6px; background: #222; border: 1px solid #333; margin-top:4px; display:inline-block; }
        
        .balance { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; position: relative; }
        #combo-ui { position: absolute; top: 10px; left: 10px; color: var(--red); font-weight: bold; font-size: 14px; display: none; }
        
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; }
        .energy-fill { background: var(--gold); height: 100%; width: 0%; transition: width 0.3s; }
        
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 11px; }
        .btn:disabled { opacity: 0.4; }
        
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(15px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 100; }
        .nav-item { font-size: 20px; opacity: 0.4; } .nav-item.active { opacity: 1; color: var(--gold); }
        .floating-text { position: absolute; color: var(--gold); font-weight: bold; pointer-events: none; animation: floatUp 0.6s ease-out forwards; }
        @keyframes floatUp { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(-40px); } }
    </style>
</head>
<body>
    <div class="header-ticker">
        <span style="color:var(--gold)">REFS: <span id="u-ref-top">0</span></span>
        <span style="color:var(--green)">$WPT: $0.000450</span>
        <span style="color:var(--gold)">JACKPOT: <span id="jack-val">0</span></span>
    </div>
    
    <div class="profile-bar">
        <div>
            <div id="u-name" style="font-weight:700;">Loading...</div>
            <div id="u-badge" class="badge-tag">...</div>
        </div>
        <button id="daily-btn" class="btn" style="background:var(--gold);" onclick="claimDaily()">🎁 GIFT</button>
    </div>

    <div id="p-mine">
        <div class="balance">
            <div id="combo-ui">🔥 COMBO x2</div>
            <small style="color:#8E8E93">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:45px; margin:8px 0;">0.00</h1>
            <div id="u-mult" style="font-size:10px; color:var(--green)">Multiplier: x1.0</div>
            <div class="energy-bar"><div id="e-bar" class="energy-fill"></div></div>
            <div id="e-text" style="font-size:11px; color:var(--gold);">⚡ 0 / 100</div>
        </div>
        <div class="card"><div>GENESIS<div id="gv">0.00</div></div><button class="btn" onclick="mine(event, 'genesis')">MINE</button></div>
        <div class="card"><div>UNITY<div id="uv">0.00</div></div><button class="btn" onclick="mine(event, 'unity')">SYNC</button></div>
        <div class="card"><div>VEO AI<div id="vv">0.00</div></div><button class="btn" onclick="mine(event, 'veo')" style="background:var(--purple); color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div id="p-mission" style="display:none">
        <h3 style="color:var(--gold)">MISSIONS & BOOSTS</h3>
        <div class="card"><div><b>Lock 100 Assets</b><br><small>+0.1x Perm. Multiplier</small></div><button class="btn" id="stake-btn" onclick="stake()">LOCK</button></div>
        <div class="card"><div><b>Energy Drink ⚡</b><br><small>Cost: 50 Assets</small></div><button class="btn" id="drink-btn" onclick="buyDrink()">BUY</button></div>
        <div class="card"><div><b>Community</b><br><small>@owpc_co</small></div><button class="btn" onclick="tg.openLink('https://t.me/owpc_co')">JOIN</button></div>
        <div class="card"><div><b>X Twitter</b><br><small>DeepTradeX</small></div><button class="btn" onclick="tg.openLink('https://x.com/DeepTradeX')">FOLLOW</button></div>
        <button class="btn" style="width:100%; margin-top:10px; background:var(--blue); color:#FFF;" onclick="share()">🚀 INVITE FRIENDS</button>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('mission')" id="n-mission" class="nav-item">⚙️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let lastClick = 0, comboCount = 0, comboActive = false, autoRate = 0.01;

        async function refresh() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            if(!d.name) return;
            document.getElementById('u-name').innerText = d.name;
            document.getElementById('u-badge').innerText = d.badge;
            document.getElementById('u-badge').style.color = d.badge_color;
            document.getElementById('u-ref-top').innerText = d.rc; 
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('tot').innerText = d.score;
            document.getElementById('u-mult').innerText = `Multiplier: x${d.multiplier}`;
            document.getElementById('jack-val').innerText = d.jackpot;
            document.getElementById('e-bar').style.width = (d.energy/d.max_energy*100) + "%";
            document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
            autoRate = d.auto_rate;

            document.getElementById('drink-btn').disabled = (d.score < 50);
            document.getElementById('stake-btn').disabled = (d.score < 100);

            let r_html = ""; d.top.forEach((u, i) => { r_html += `<div class="card"><div>${i+1}. ${u.n}</div><b>${u.p}</b></div>`; });
            document.getElementById('rank-list').innerHTML = r_html;
            updateGiftTimer();
            document.body.style.visibility = "visible";
        }

        function mine(e, t) {
            const now = Date.now();
            if(now - lastClick < 400) { comboCount++; if(comboCount > 5) { comboActive = true; document.getElementById('combo-ui').style.display = 'block'; } }
            else { comboCount = 0; comboActive = false; document.getElementById('combo-ui').style.display = 'none'; }
            lastClick = now;

            const rect = e.target.getBoundingClientRect();
            const txt = document.createElement('div'); txt.className = 'floating-text';
            txt.innerText = comboActive ? '+0.12🔥' : '+0.06';
            txt.style.left = rect.left + 'px'; txt.style.top = rect.top + 'px';
            document.body.appendChild(txt); setTimeout(() => txt.remove(), 600);

            fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t, combo:comboActive})});
            tg.HapticFeedback.impactOccurred(comboActive ? 'medium' : 'light');
            refresh();
        }

        // Auto-Mining Visuel
        setInterval(() => {
            let el = document.getElementById('tot');
            if(el) { let cur = parseFloat(el.innerText); el.innerText = (cur + (autoRate/3600)).toFixed(4); }
        }, 1000);

        function updateGiftTimer() {
            const last = localStorage.getItem('lock_' + uid);
            const btn = document.getElementById('daily-btn');
            if (last) {
                const remaining = (12*3600*1000) - (Date.now() - parseInt(last));
                if (remaining > 0) {
                    const h = Math.floor(remaining / 3600000), m = Math.floor((remaining % 3600000) / 60000);
                    btn.disabled = true; btn.innerText = `⏳ ${h}h ${m}m`; return;
                }
            }
            btn.disabled = false; btn.innerText = "🎁 GIFT";
        }

        async function claimDaily() {
            const r = await fetch('/api/daily', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            if(r.ok) { localStorage.setItem('lock_'+uid, Date.now()); confetti(); refresh(); }
        }

        async function stake() { await fetch('/api/stake', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})}); confetti(); refresh(); }
        async function buyDrink() { await fetch('/api/boost/energy', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})}); confetti(); refresh(); }
        
        function share() { tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/owpcsbot?start=${uid}&text=🚀 Join my DePIN Node!`); }
        function show(p) { ['mine','leader','mission'].forEach(id=>{document.getElementById('p-'+id).style.display=(id===p?'block':'none'); document.getElementById('n-'+id).classList.toggle('active',id===p);}); }
        
        refresh(); setInterval(updateGiftTimer, 60000);
        tg.expand();
    </script>
</body>
</html>
"""

async def main():
    global bot_app
    init_db()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize(); await bot_app.start()
    await bot_app.bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")).serve()

if __name__ == "__main__":
    asyncio.run(main())
