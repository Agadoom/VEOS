import os, asyncio, uvicorn, logging, time, random, datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application
from telegram.error import Forbidden

from data_conx import init_db, get_db_conn

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 1414016840 
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
        for col, dtype in [("staked_amount", "DOUBLE PRECISION DEFAULT 0"), ("streak", "INTEGER DEFAULT 0"), ("last_streak_date", "TEXT"), ("wallet_address", "TEXT")]:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit(); c.close(); conn.close()

patch_db()

# --- UTILS ---
def get_badge(score, streak=0):
    if streak >= 7: return "🔥 Streak Master"
    if score >= 500: return "💎 Diamond"
    if score >= 150: return "🥇 Gold"
    if score >= 50:  return "🥈 Silver"
    return "🥉 Bronze"

# --- BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    if update.effective_chat.type in ['group', 'supergroup']: return 

    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    if ref_id == uid: ref_id = None

    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id, name, referred_by, energy, last_energy_update, staked_amount, streak) VALUES (%s, %s, %s, %s, %s, 0, 0)", 
                      (uid, name, ref_id, MAX_ENERGY, int(time.time())))
            if ref_id:
                c.execute("UPDATE users SET p_unity = COALESCE(p_unity,0) + 10.0, ref_count = COALESCE(ref_count,0) + 1 WHERE user_id = %s", (ref_id,))
        conn.commit(); c.close(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text("✨ Welcome to OWPC DePIN Hub.\nNode Synchronized.", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_streak_date, name, energy, last_energy_update, streak, staked_amount, wallet_address FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    last_upd = r[7] if r[7] else now
    current_e = min(MAX_ENERGY, (r[6] or 0) + ((now - last_upd) // 60) * REGEN_RATE)
    
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    today = datetime.date.today().isoformat()
    # can_claim est vrai si le dernier streak n'est pas aujourd'hui
    can_claim = (r[4] != today)

    c.execute("SELECT name, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) as total FROM users ORDER BY total DESC LIMIT 8")
    top = [{"n": x[0], "p": round(x[1], 2), "b": get_badge(x[1])} for x in c.fetchall()]
    
    c.execute("SELECT SUM(COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users")
    total_net = c.fetchone()[0] or 0
    c.close(); conn.close()

    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[5],
        "energy": int(current_e), "max_energy": MAX_ENERGY, "badge": get_badge(score, r[8] or 0),
        "top": top, "jackpot": round(total_net * 0.1, 2),
        "machine_load": random.randint(88, 99), "price_wpt": 0.00045,
        "multiplier": round(1.0 + ((r[9] or 0) / 100) * 0.1 + (score / 1000), 2),
        "can_claim": can_claim, "streak": r[8] or 0, "staked": r[9] or 0
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, staked_amount, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    if not res: return JSONResponse(status_code=404, content={"ok": False})
    now = int(time.time())
    current_e = min(MAX_ENERGY, (res[0] or 0) + ((now - (res[1] or now)) // 60) * REGEN_RATE)
    if current_e >= 1:
        mult = 1.0 + ((res[2] or 0) / 100) * 0.1 + ((res[3] or 0) / 1000)
        gain = 0.05 * mult
        c.execute(f"UPDATE users SET p_{t} = COALESCE(p_{t},0) + %s, energy = %s, last_energy_update = %s WHERE user_id = %s", (gain, current_e - 1, now, uid))
        conn.commit(); c.close(); conn.close()
        return {"ok": True}
    return JSONResponse(status_code=400, content={"ok": False})

@app.post("/api/daily")
async def daily_api(request: Request):
    data = await request.json(); uid = data.get("user_id"); today = datetime.date.today()
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT last_streak_date, streak FROM users WHERE user_id = %s", (uid,))
    r = c.fetchone()
    if not r or r[0] != today.isoformat():
        new_s = (r[1]+1) if r and r[0] == (today - datetime.timedelta(days=1)).isoformat() else 1
        c.execute("UPDATE users SET p_genesis=COALESCE(p_genesis,0)+5, streak=%s, last_streak_date=%s WHERE user_id=%s", (new_s, today.isoformat(), uid))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"ok": False})

@app.post("/api/stake")
async def stake_api(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users WHERE user_id = %s", (uid,))
    total = c.fetchone()[0] or 0
    if total >= 100:
        c.execute("UPDATE users SET p_genesis=p_genesis-34, p_unity=p_unity-33, p_veo=p_veo-33, staked_amount=COALESCE(staked_amount,0)+100 WHERE user_id=%s", (uid,))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"ok": False})

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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --text: #8E8E93; --green: #34C759; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        .header-ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px; font-size: 10px; display: flex; justify-content: space-between; border-bottom: 1px solid #333; }
        .machine-status { font-size: 9px; color: var(--text); margin-bottom: 12px; display: flex; justify-content: space-between; background: #111; padding: 8px; border-radius: 10px; border: 1px solid #222; align-items: center; }
        .status-led { height: 7px; width: 7px; background: var(--green); border-radius: 50%; display: inline-block; box-shadow: 0 0 8px var(--green); animation: pulse 1.5s infinite; margin-right:5px; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2c2c2e; gap: 10px; }
        .profile-info { display: flex; align-items: center; gap: 8px; flex: 1; overflow: hidden; }
        .badge-tag { font-size: 9px; padding: 2px 6px; border-radius: 6px; background: #222; color: var(--gold); border: 1px solid #333; }
        .u-name-text { font-weight: 700; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .balance { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; }
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; position: relative; border: 1px solid #333; }
        .energy-fill { background: linear-gradient(90deg, #FFD700, #FFA500); height: 100%; width: 0%; transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1); }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; position: relative; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 11px; transition: 0.2s; }
        .btn:active { transform: scale(0.95); opacity: 0.8; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 999; }
        .nav-item { font-size: 20px; opacity: 0.4; cursor: pointer; } .nav-item.active { opacity: 1; color: var(--gold); }
        
        .floating-text { position: absolute; color: var(--gold); font-weight: bold; pointer-events: none; animation: floatUp 0.8s ease-out forwards; font-size: 14px; }
        @keyframes floatUp { from { transform: translateY(0); opacity: 1; } to { transform: translateY(-40px); opacity: 0; } }
    </style>
</head>
<body>
    <div class="header-ticker"><span>$WPT: $<span id="m-price">0.00045</span></span><span style="color:var(--gold)">JACKPOT: <span id="jack-val">0</span> OWPC</span></div>
    <div class="machine-status"><span><span class="status-led"></span> NODE: ONLINE</span><span>LOAD: <span id="m-load">0</span>%</span></div>
    
    <div class="profile-bar">
        <div class="profile-info">
            <div id="u-name" class="u-name-text">...</div>
            <div id="u-badge" class="badge-tag">...</div>
        </div>
        <button id="daily-btn" class="btn" style="display:none; background:var(--gold); padding:8px 12px; box-shadow: 0 0 10px var(--gold);" onclick="claimDaily()">🎁 GIFT</button>
        <div id="u-ref" style="font-weight:bold; font-size:11px; color:var(--gold); white-space:nowrap;">0 REFS</div>
    </div>

    <div id="p-mine">
        <div class="balance">
            <small style="color:var(--text)">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:45px; margin:8px 0;">0.00</h1>
            <div id="u-mult" style="font-size:10px; color:var(--green)">⚡ Multiplier: x1.0</div>
            <div class="energy-bar"><div id="e-bar" class="energy-fill"></div></div>
            <div id="e-text" style="font-size:11px; color:var(--gold);">⚡ 0 / 100</div>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn m-btn" onclick="mine(event, 'genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn m-btn" onclick="mine(event, 'unity')">SYNC</button></div>
        <div class="card"><div><small style="color:#A259FF">VEO AI</small><div id="vv">0.00</div></div><button class="btn m-btn" onclick="mine(event, 'veo')" style="background:#A259FF; color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-mission" style="display:none">
        <h3 style="color:var(--gold)">STAKING & NODES</h3>
        <div class="card"><div><b>Active Nodes</b><br><small>Streak: <span id="u-streak">0</span> Days</small></div><div id="staked-val" style="color:var(--gold)">0 Staked</div></div>
        <div class="card" style="border-color:var(--gold)">
            <div><b>Stake 100 Assets</b><br><small>+0.1x Multiplier</small></div>
            <button class="btn" id="stake-btn" onclick="stake()">LOCK</button>
        </div>
        <button class="btn" style="width:100%; margin-top:15px; background:var(--blue); color:#FFF; padding:15px;" onclick="share()">🚀 INVITE FRIENDS</button>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">$WPT PILLARS</h3>
        <div class="card"><b>World Peace Token</b><a href="https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA" target="_blank" class="btn" style="background:var(--gold)">CLAIM</a></div>
        <div class="card"><b>Unity Asset</b><a href="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA" target="_blank" class="btn">CLAIM</a></div>
        <div class="card"><b>Veo AI Asset</b><a href="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA" target="_blank" class="btn">CLAIM</a></div>
        <div class="card"><b>Genesis Asset</b><a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" target="_blank" class="btn">CLAIM</a></div>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('mission')" id="n-mission" class="nav-item">⚙️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        const uid = tg.initDataUnsafe.user?.id || 0;

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}`); const d = await r.json();
                document.getElementById('u-name').innerText = d.name;
                document.getElementById('u-badge').innerText = d.badge;
                document.getElementById('u-ref').innerText = d.rc + " REFS";
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = (d.g+d.u+d.v).toFixed(2);
                document.getElementById('e-bar').style.width = (d.energy/d.max_energy*100) + "%";
                document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
                document.getElementById('u-mult').innerText = `⚡ Multiplier: x${d.multiplier}`;
                document.getElementById('u-streak').innerText = d.streak;
                document.getElementById('staked-val').innerText = d.staked + " Staked";
                document.getElementById('jack-val').innerText = d.jackpot;
                
                // Si can_claim est vrai, on affiche le bouton cadeau
                document.getElementById('daily-btn').style.display = d.can_claim ? 'block' : 'none';
                
                document.getElementById('stake-btn').disabled = ((d.g+d.u+d.v) < 100);
                let r_html = ""; d.top.forEach((u, i) => { r_html += `<div class="card"><div>${i+1}. ${u.n}<br><small style="color:var(--gold)">${u.b}</small></div><b>${u.p}</b></div>`; });
                document.getElementById('rank-list').innerHTML = r_html;
                document.getElementById('m-load').innerText = d.machine_load;
            } catch(e) {}
        }

        async function mine(e, t) {
            const rect = e.target.getBoundingClientRect();
            const txt = document.createElement('div'); txt.className = 'floating-text';
            txt.innerText = '+0.05'; txt.style.left = (rect.left + 20) + 'px'; txt.style.top = rect.top + 'px';
            document.body.appendChild(txt); setTimeout(() => txt.remove(), 800);
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            refresh(); tg.HapticFeedback.impactOccurred('light');
        }

        // FONCTION CADEAU CORRIGÉE
        async function claimDaily() {
            tg.HapticFeedback.notificationOccurred('success');
            // Animation immédiate pour le feedback utilisateur
            confetti({
                particleCount: 150,
                spread: 70,
                origin: { y: 0.6 },
                colors: ['#FFD700', '#ffffff']
            });
            
            try {
                const res = await fetch('/api/daily', {
                    method:'POST', 
                    headers:{'Content-Type':'application/json'}, 
                    body:JSON.stringify({user_id:uid})
                });
                if(res.ok) {
                    refresh(); // Met à jour les scores et cache le bouton
                }
            } catch(err) {
                console.error("Erreur claim", err);
            }
        }

        async function stake() {
            const res = await fetch('/api/stake', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            if(res.ok) { confetti(); refresh(); }
        }

        function share() {
            const url = `https://t.me/owpcsbot?start=${uid}`;
            confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
            setTimeout(() => { tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=🚀 Join my OWPC Node!`); }, 500);
        }

        function show(p) { ['mine','pillars','leader','mission'].forEach(id=>{document.getElementById('p-'+id).style.display=(id===p?'block':'none'); document.getElementById('n-'+id).classList.toggle('active',id===p);}); }
        refresh(); setInterval(refresh, 5000);
    </script>
</body>
</html>
"""

async def main():
    init_db(); bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize(); await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
