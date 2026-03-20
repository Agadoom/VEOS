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

bot_app = None 
MAX_ENERGY = 100
REGEN_RATE = 1 
STREAK_REWARDS = [0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0]

# --- UTILS ---
def get_badge(score, streak=0):
    if streak >= 7: return "🔥 Streak Master"
    if score >= 500: return "💎 Diamond"
    if score >= 150: return "🥇 Gold"
    if score >= 50:  return "🥈 Silver"
    return "🥉 Bronze"

# --- BOT FUNCTIONS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    referrer_id = None
    if context.args:
        try:
            arg = int(context.args[0])
            referrer_id = arg if arg != uid else None
        except: pass

    conn = get_db_conn()
    if conn:
        try:
            c = conn.cursor()
            c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
            if not c.fetchone():
                now = int(time.time())
                c.execute("INSERT INTO users (user_id, name, referred_by, energy, last_energy_update, streak) VALUES (%s, %s, %s, %s, %s, 0)", 
                          (uid, name, referrer_id, MAX_ENERGY, now))
                if referrer_id:
                    c.execute("UPDATE users SET p_unity = p_unity + 1.0, ref_count = ref_count + 1 WHERE user_id = %s", (referrer_id,))
            conn.commit(); c.close(); conn.close()
        except Exception as e: logging.error(f"SQL Start Error: {e}")
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 ENTER OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to the World Peace Hub, {name}!\n\nManage your $WPT assets and join the global movement.", reply_markup=kb)

# --- API USER DATA ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn()
    if not conn: return JSONResponse(status_code=500, content={})
    c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_streak_date, name, energy, last_energy_update, streak FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    seconds_passed = now - r[7]
    refill = int(seconds_passed / 60) * REGEN_RATE
    current_energy = min(MAX_ENERGY, r[6] + refill)
    
    if refill > 0:
        c.execute("UPDATE users SET energy = %s, last_energy_update = %s WHERE user_id = %s", (current_energy, now, uid))
        conn.commit()

    last_claim = r[4] or 0
    can_claim = (now - last_claim) >= 86400
    is_broken = (now - last_claim) >= 172800
    
    current_streak = r[8] if not is_broken else 0
    if is_broken and r[8] > 0:
        c.execute("UPDATE users SET streak = 0 WHERE user_id = %s", (uid,))
        conn.commit()

    score = r[0] + r[1] + r[2]
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT SUM(p_genesis + p_unity + p_veo) FROM users")
    total_mined = c.fetchone()[0] or 0

    c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 10")
    top = [{"n": x[0], "p": round(x[1], 2), "b": get_badge(x[1])} for x in c.fetchall()]
    
    c.close(); conn.close()

    # Prix simulé + Jackpot Dynamique
    market_wpt = round(0.00045 + (random.random() * 0.00005), 6)
    jackpot_pool = round(total_mined * 0.1, 2) # 10% de la mine globale va au jackpot virtuel

    return {
        "g": r[0], "u": r[1], "v": r[2], "rc": r[3], "name": r[5], 
        "energy": current_energy, "max_energy": MAX_ENERGY,
        "top": top, "badge": get_badge(score, current_streak),
        "streak": current_streak, "can_claim": can_claim,
        "global_users": total_users, "global_mined": round(total_mined, 2),
        "price_wpt": market_wpt, "jackpot": jackpot_pool
    }

@app.post("/api/daily")
async def claim_daily(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT last_streak_date, streak FROM users WHERE user_id = %s", (uid,))
    r = c.fetchone()
    now = int(time.time())
    if r and (now - (r[0] or 0)) >= 86400:
        new_streak = (r[1] % 7) + 1
        reward = STREAK_REWARDS[new_streak-1]
        c.execute("UPDATE users SET p_genesis = p_genesis + %s, streak = %s, last_streak_date = %s WHERE user_id = %s", (reward, new_streak, now, uid))
        conn.commit(); c.close(); conn.close()
        return {"ok": True, "reward": reward, "streak": new_streak}
    c.close(); conn.close()
    return {"ok": False}

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    if res and res[0] >= 1:
        col = {"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}.get(t)
        now = int(time.time())
        c.execute(f"UPDATE users SET {col} = {col} + 0.05, energy = energy - 1, last_energy_update = %s WHERE user_id = %s", (now, uid))
        conn.commit(); c.close(); conn.close()
        return {"ok": True}
    c.close(); conn.close()
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
        :root { --bg: #050505; --card: #111; --blue: #007AFF; --green: #34C759; --gold: #FFD700; --text: #8E8E93; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        
        .header-ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px; font-size: 11px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; }
        .jackpot-badge { background: linear-gradient(90deg, #FFD700, #FFA500); color: #000; padding: 2px 8px; border-radius: 10px; font-weight: bold; font-size: 10px; }

        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2c2c2e; }
        .energy-container { margin: 10px 0; background: #222; border-radius: 10px; height: 6px; overflow: hidden; }
        .energy-bar { background: linear-gradient(90deg, #FFD700, #FFA500); height: 100%; width: 0%; transition: width 0.3s; }
        
        .balance { text-align: center; padding: 30px 20px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); margin-bottom: 15px; border: 1px solid #222; position: relative; overflow: hidden; }
        .balance::after { content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: conic-gradient(from 0deg, transparent, rgba(255,215,0,0.03), transparent); animation: rotate 10s linear infinite; pointer-events: none; }
        @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

        .stats-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .stat-item { background: #111; padding: 12px; border-radius: 15px; border: 1px solid #1c1c1e; text-align: center; }
        .stat-item small { color: var(--text); font-size: 9px; display: block; margin-bottom: 4px; }

        .card { background: var(--card); padding: 12px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1C1C1E; transition: 0.2s; }
        .card:active { background: #1a1a1a; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 12px; }
        .btn:disabled { opacity: 0.1; }
        
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.85); backdrop-filter: blur(20px); padding: 12px 30px; border-radius: 40px; display: flex; gap: 35px; border: 1px solid #333; z-index: 999; }
        .nav-item { font-size: 22px; opacity: 0.4; }
        .nav-item.active { opacity: 1; transform: scale(1.2); color: var(--gold); }
    </style>
</head>
<body>
    <div class="header-ticker">
        <div>$WPT: <span id="m-price" style="color:var(--gold)">0.000450</span></div>
        <div class="jackpot-badge">JACKPOT: <span id="jack-val">0</span> OWPC</div>
    </div>

    <div class="profile-bar">
        <div style="display:flex; align-items:center; gap:10px;">
            <div id="u-name" style="font-weight:700">...</div><div id="u-badge" style="font-size:10px; color:var(--gold)">Bronze</div>
        </div>
        <div id="u-ref" style="font-weight:bold; font-size:12px;">0 REFS</div>
    </div>

    <div id="p-mine">
        <div id="streak-ui" style="display:none; background:linear-gradient(90deg, #FFD700, #FFA500); color:#000; padding:12px; border-radius:15px; text-align:center; margin-bottom:15px; font-weight:bold; cursor:pointer;" onclick="claimDaily()">
            🎁 CLAIM DAY <span id="stk-txt">1</span> BONUS !
        </div>

        <div class="balance">
            <small style="color:var(--text); letter-spacing: 1px;">TOTAL BALANCE</small>
            <h1 id="tot" style="font-size:42px; margin:8px 0; font-weight:900;">0.00</h1>
            <div class="energy-container"><div id="e-bar" class="energy-bar"></div></div>
            <div style="display:flex; justify-content:space-between; margin-top:5px;">
                <span id="e-text" style="font-size:10px; color:var(--gold);">⚡ 0 / 100</span>
                <span style="font-size:10px; color:var(--text);">Minage x1.0</span>
            </div>
        </div>

        <div class="stats-row">
            <div class="stat-item"><small>COMMUNITY</small><b id="g-users">0</b></div>
            <div class="stat-item"><small>BURNED/MINED</small><b id="g-mined">0.00</b></div>
        </div>

        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv" style="font-weight:700">0.00</div></div><button class="btn m-btn" onclick="mine('genesis')">CLAIM</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv" style="font-weight:700">0.00</div></div><button class="btn m-btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small style="color:#A259FF">VEO AI</small><div id="vv" style="font-weight:700">0.00</div></div><button class="btn m-btn" onclick="mine('veo')" style="background:#A259FF; color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-pillars" style="display:none; padding-top:10px;">
        <div style="text-align:center; margin-bottom:20px;">
            <h3 style="margin:0; color:var(--gold)">OFFICIAL PILLARS</h3>
            <p style="font-size:11px; color:var(--text)">Trade and track WPT ecosystem</p>
        </div>
        
        <div class="card" style="border: 1px solid var(--gold); background: rgba(255,215,0,0.05);">
            <div><b>World Peace Token</b><br><small style="color:var(--gold)">Main Trading Pair ($WPT)</small></div>
            <a href="https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA" target="_blank" class="btn" style="background:var(--gold)">FAST BUY</a>
        </div>
        
        <div class="card"><div><b>Unity Asset</b><br><small>Blum Memepad</small></div><a href="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA" target="_blank" class="btn">VIEW</a></div>
        <div class="card"><div><b>Veo AI Asset</b><br><small>Blum Memepad</small></div><a href="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA" target="_blank" class="btn">VIEW</a></div>
        <div class="card"><div><b>Genesis Asset</b><br><small>Blum Memepad</small></div><a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" target="_blank" class="btn">VIEW</a></div>
        
        <button class="btn" style="width:100%; margin-top:20px; background:var(--blue); color:#FFF; padding:15px;" onclick="shareInvite()">🚀 INVITE FRIENDS & EARN</button>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;
        const apiBase = window.location.origin;

        async function refresh() {
            if(!uid) return;
            try {
                const r = await fetch(`${apiBase}/api/user/${uid}`);
                const d = await r.json();
                
                document.getElementById('u-name').innerText = d.name;
                document.getElementById('u-badge').innerText = d.badge;
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = (d.g + d.u + d.v).toFixed(2);
                document.getElementById('u-ref').innerText = `${d.rc} REFS`;
                document.getElementById('e-bar').style.width = (d.energy / d.max_energy * 100) + "%";
                document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
                
                document.getElementById('g-mined').innerText = d.global_mined;
                document.getElementById('g-users').innerText = d.global_users;
                document.getElementById('m-price').innerText = d.price_wpt.toFixed(6);
                document.getElementById('jack-val').innerText = d.jackpot;

                document.querySelectorAll('.m-btn').forEach(b => b.disabled = d.energy < 1);
                document.getElementById('streak-ui').style.display = d.can_claim ? 'block' : 'none';
                document.getElementById('stk-txt').innerText = (d.streak + 1);

                let r_html = "";
                d.top.forEach((u, i) => { r_html += `<div class="card"><div>${i+1}. ${u.n}<br><small>${u.b}</small></div><b>${u.p}</b></div>`; });
                document.getElementById('rank-list').innerHTML = r_html;
            } catch(e) {}
        }

        async function claimDaily() {
            tg.HapticFeedback.notificationOccurred('success');
            const res = await fetch(`${apiBase}/api/daily`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            const data = await res.json();
            if(data.ok) { 
                confetti({ particleCount: 150, spread: 70, origin: { y: 0.6 } }); 
                tg.showAlert(`Congrats! Streak Bonus claimed.`); 
                refresh(); 
            }
        }

        async function mine(t) {
            tg.HapticFeedback.impactOccurred('medium');
            const res = await fetch(`${apiBase}/api/mine`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { 
                confetti({ particleCount: 5, spread: 20, origin: { y: 0.8 }, colors: ['#FFD700'] });
                refresh(); 
            }
        }

        function shareInvite() {
            const url = `https://t.me/owpcsbot?start=${uid}`;
            const text = "🌍 Join the World Peace Hub! Track $WPT, mine assets and win the daily jackpot! 🚀";
            tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`);
        }

        function show(p) {
            ['mine', 'pillars', 'leader'].forEach(id => {
                document.getElementById('p-'+id).style.display = (id===p ? 'block' : 'none');
                document.getElementById('n-'+id).classList.toggle('active', id===p);
            });
        }
        refresh(); setInterval(refresh, 5000);
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
