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
REGEN_RATE = 1 # 1 energy / min

# --- UTILS ---
def get_badge(score, streak=0):
    if streak >= 7: return "🔥 Streak Master"
    if score >= 500: return "💎 Diamond"
    if score >= 150: return "🥇 Gold"
    if score >= 50:  return "🥈 Silver"
    return "🥉 Bronze"

# --- BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = None
    if context.args and context.args[0].isdigit():
        ref_id = int(context.args[0])

    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
        if not c.fetchone():
            now = int(time.time())
            c.execute("INSERT INTO users (user_id, name, referred_by, energy, last_energy_update, streak) VALUES (%s, %s, %s, %s, %s, 0)", 
                      (uid, name, ref_id, MAX_ENERGY, now))
            if ref_id:
                c.execute("UPDATE users SET p_unity = p_unity + 1.0, ref_count = ref_count + 1 WHERE user_id = %s", (ref_id,))
        conn.commit(); c.close(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 ENTER HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC Network!", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_streak_date, name, energy, last_energy_update, streak FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    current_e = min(MAX_ENERGY, r[6] + ((now - r[7]) // 60) * REGEN_RATE)
    score = r[0] + r[1] + r[2]

    c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 8")
    top = [{"n": x[0], "p": round(x[1], 2), "b": get_badge(x[1])} for x in c.fetchall()]
    
    c.execute("SELECT u.name, l.token FROM logs l JOIN users u ON l.user_id = u.user_id ORDER BY l.id DESC LIMIT 3")
    feed = [{"n": x[0], "t": x[1]} for x in c.fetchall()]

    c.close(); conn.close()
    return {
        "g": r[0], "u": r[1], "v": r[2], "rc": r[3], "name": r[5],
        "energy": current_e, "max_energy": MAX_ENERGY, "badge": get_badge(score, r[8]),
        "top": top, "feed": feed, "machine_load": random.randint(85, 99), "price_wpt": 0.00045
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    now = int(time.time())
    current_e = min(MAX_ENERGY, res[0] + ((now - res[1]) // 60) * REGEN_RATE)

    if current_e >= 1:
        c.execute(f"UPDATE users SET p_{t} = p_{t} + 0.05, energy = %s, last_energy_update = %s WHERE user_id = %s", (current_e - 1, now, uid))
        c.execute("INSERT INTO logs (user_id, token, timestamp) VALUES (%s, %s, %s)", (uid, t.upper(), now))
        conn.commit(); c.close(); conn.close()
        return {"ok": True}
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
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; }
        .machine-status { font-size: 9px; color: var(--text); margin-bottom: 10px; display: flex; justify-content: space-between; background: #111; padding: 8px; border-radius: 10px; }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #222; }
        .badge-tag { font-size: 10px; padding: 2px 8px; border-radius: 6px; background: #222; color: var(--gold); border: 1px solid #333; }
        .balance { text-align: center; padding: 25px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; }
        .energy-bar { background: #222; border-radius: 10px; height: 6px; margin: 12px 0; overflow: hidden; }
        .energy-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: 0.3s; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 11px; }
        .btn:disabled { opacity: 0.3; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 25px; border: 1px solid #333; }
        .nav-item { font-size: 20px; opacity: 0.4; }
        .nav-item.active { opacity: 1; color: var(--gold); }
    </style>
</head>
<body>
    <div class="machine-status"><span>● NODE: ONLINE</span><span>LOAD: <span id="m-load">0</span>%</span></div>
    
    <div class="profile-bar">
        <div style="display:flex; align-items:center; gap:10px;"><div id="u-name" style="font-weight:700">...</div><div id="u-badge" class="badge-tag">...</div></div>
        <div id="u-ref" style="font-weight:bold; font-size:12px; color:var(--gold)">0 REFS</div>
    </div>

    <div id="p-mine">
        <div class="balance">
            <small style="color:var(--text)">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:40px; margin:5px 0;">0.00</h1>
            <div class="energy-bar"><div id="e-bar" class="energy-fill"></div></div>
            <div id="e-text" style="font-size:11px; color:var(--gold);">⚡ 0 / 100</div>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn m-btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn m-btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small style="color:#A259FF">VEO AI</small><div id="vv">0.00</div></div><button class="btn m-btn" onclick="mine('veo')" style="background:#A259FF; color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">$WPT ECOSYSTEM</h3>
        <div class="card"><b>World Peace Token</b><a href="https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA" target="_blank" class="btn" style="background:var(--gold)">BUY</a></div>
        <div class="card"><b>Unity Asset</b><a href="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA" target="_blank" class="btn">VIEW</a></div>
        <div class="card"><b>Veo AI Asset</b><a href="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA" target="_blank" class="btn">VIEW</a></div>
        <div class="card"><b>Genesis Asset</b><a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" target="_blank" class="btn">VIEW</a></div>
        <button class="btn" style="width:100%; margin-top:10px; background:var(--blue); color:#FFF; padding:15px;" onclick="share()">🚀 INVITE FRIENDS</button>
    </div>

    <div id="p-mission" style="display:none">
        <h3 style="color:var(--gold)">MISSION</h3>
        <div class="card" onclick="window.open('https://t.me/OWPC_Co', '_blank')"><b>Community</b><span>💬</span></div>
        <div style="background:#111; padding:15px; border-radius:15px; border:1px solid #222; font-size:12px; line-height:1.6;">
            <b>Roadmap:</b><br>
            1. Alpha Mining & Community Launch (LIVE)<br>
            2. DePIN Hardware Sync (Q2 2026)<br>
            3. Mainnet & Listing (Q4 2026)
        </div>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('mission')" id="n-mission" class="nav-item">🗺️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        async function refresh() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('u-name').innerText = d.name;
            document.getElementById('u-badge').innerText = d.badge;
            document.getElementById('u-ref').innerText = d.rc + " REFS";
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('tot').innerText = (d.g+d.u+d.v).toFixed(2);
            document.getElementById('m-load').innerText = d.machine_load;
            document.getElementById('e-bar').style.width = (d.energy / d.max_energy * 100) + "%";
            document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
            document.querySelectorAll('.m-btn').forEach(b => b.disabled = (d.energy < 1));
            let r_html = ""; d.top.forEach((u, i) => { r_html += `<div class="card"><div>${i+1}. ${u.n}<br><small style="color:var(--gold)">${u.b}</small></div><b>${u.p}</b></div>`; });
            document.getElementById('rank-list').innerHTML = r_html;
        }
        async function mine(t) {
            tg.HapticFeedback.impactOccurred('medium');
            const res = await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { confetti({ particleCount:10, spread:20, origin:{y:0.8} }); refresh(); }
        }
        function share() {
            const url = `https://t.me/owpcsbot?start=${uid}`;
            tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=Join OWPC DePIN Hub! 🌍`);
        }
        function show(p) {
            ['mine', 'pillars', 'leader', 'mission'].forEach(id => {
                document.getElementById('p-'+id).style.display = (id===p?'block':'none');
                document.getElementById('n-'+id).classList.toggle('active', id===p);
            });
        }
        refresh(); setInterval(refresh, 8000);
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
