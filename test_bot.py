import os, asyncio, uvicorn, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
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
REGEN_RATE = 1 # 1 énergie par minute

# --- UTILS ---
def get_badge(score):
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
                c.execute("INSERT INTO users (user_id, name, referred_by, energy, last_energy_update) VALUES (%s, %s, %s, %s, %s)", 
                          (uid, name, referrer_id, MAX_ENERGY, now))
                if referrer_id:
                    c.execute("UPDATE users SET p_unity = p_unity + 1.0, ref_count = ref_count + 1 WHERE user_id = %s", (referrer_id,))
            conn.commit(); c.close(); conn.close()
        except Exception as e: logging.error(f"SQL Start Error: {e}")
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC HUB, {name}!", reply_markup=kb)

# --- API USER DATA ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn()
    if not conn: return JSONResponse(status_code=500, content={})
    c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_daily, name, energy, last_energy_update FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    seconds_passed = now - r[7]
    refill = int(seconds_passed / 60) * REGEN_RATE
    current_energy = min(MAX_ENERGY, r[6] + refill)
    
    if refill > 0:
        c.execute("UPDATE users SET energy = %s, last_energy_update = %s WHERE user_id = %s", (current_energy, now, uid))
        conn.commit()

    score = r[0] + r[1] + r[2]
    wait = max(0, 86400 - (now - (r[4] or 0)))
    
    c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 10")
    top = [{"n": x[0], "p": round(x[1], 2), "b": get_badge(x[1])} for x in c.fetchall()]
    
    c.close(); conn.close()
    return {
        "g": r[0], "u": r[1], "v": r[2], "rc": r[3], "name": r[5], 
        "energy": current_energy, "max_energy": MAX_ENERGY,
        "top": top, "next_daily": wait, "badge": get_badge(score)
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT energy FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    
    if res and res[0] >= 1:
        col = {"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}.get(t)
        c.execute(f"UPDATE users SET {col} = {col} + 0.05, energy = energy - 1, last_energy_update = %s WHERE user_id = %s", (int(time.time()), uid))
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
        :root { --bg: #000; --card: #111; --blue: #007AFF; --green: #34C759; --gold: #FFD700; --text: #8E8E93; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow: hidden; }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 20px; border: 1px solid #2c2c2e; }
        .avatar { width: 35px; height: 35px; background: var(--blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; }
        .energy-container { margin: 15px 0; background: #222; border-radius: 10px; height: 10px; overflow: hidden; }
        .energy-bar { background: linear-gradient(90deg, #FFD700, #FFA500); height: 100%; width: 0%; transition: width 0.3s; }
        .balance { text-align: center; padding: 20px; border-radius: 25px; background: #080808; margin-bottom: 15px; border: 1px solid #1a1a1a; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1C1C1E; }
        .btn { background: #FFF; color: #000; border: none; padding: 8px 15px; border-radius: 10px; font-weight: 700; }
        .btn:disabled { opacity: 0.3; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.9); backdrop-filter: blur(15px); padding: 10px 25px; border-radius: 35px; display: flex; gap: 30px; border: 1px solid #333; }
        .nav-item { font-size: 20px; opacity: 0.3; }
        .nav-item.active { opacity: 1; }
        .badge-tag { font-size: 10px; padding: 2px 6px; border-radius: 5px; background: #333; color: var(--gold); }
    </style>
</head>
<body>
    <div class="profile-bar">
        <div style="display:flex; align-items:center; gap:10px;"><div class="avatar" id="u-avatar">?</div>
            <div><div id="u-name" style="font-weight:700">...</div><div id="u-badge" class="badge-tag">Bronze</div></div>
        </div>
        <div style="text-align:right"><small style="color:var(--text); font-size:9px">REFS</small><div id="u-ref" style="color:var(--gold); font-weight:bold">0</div></div>
    </div>

    <div id="p-mine">
        <div class="balance"><span>TOTAL ASSETS</span><h1 id="tot" style="font-size:38px; margin:5px 0">0.00</h1></div>
        <div class="energy-container"><div id="e-bar" class="energy-bar"></div></div>
        <div id="e-text" style="text-align:center; font-size:10px; color:var(--gold); margin-bottom:15px;">⚡ 0 / 100</div>

        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn m-btn" onclick="mine('genesis')">CLAIM</button></div>
        <div class="card"><div><small>UNITY</small><div id="uv">0.00</div></div><button class="btn m-btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small style="color:var(--blue)">VEO AI</small><div id="vv">0.00</div></div><button class="btn m-btn" onclick="mine('veo')" style="background:var(--blue);color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-pillars" style="display:none; padding-top:10px;">
        <div class="card"><div><b>Genesis Token</b></div><a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" target="_blank" style="background:#FFF; color:#000; padding:8px 15px; border-radius:10px; font-weight:700; text-decoration:none;">OPEN</a></div>
        <div class="card"><div><b>Unity Token</b></div><a href="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA" target="_blank" style="background:#FFF; color:#000; padding:8px 15px; border-radius:10px; font-weight:700; text-decoration:none;">OPEN</a></div>
        <div class="card"><div><b>Veo AI Token</b></div><a href="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA" target="_blank" style="background:#FFF; color:#000; padding:8px 15px; border-radius:10px; font-weight:700; text-decoration:none;">OPEN</a></div>
        <button class="btn" style="width:100%; margin-top:20px;" onclick="copyRef()">Copy Referral Link</button>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">💎</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;
        const apiBase = window.location.origin;

        async function refresh() {
            if(!uid) return;
            const r = await fetch(`${apiBase}/api/user/${uid}`);
            const d = await r.json();
            document.getElementById('u-name').innerText = d.name;
            document.getElementById('u-badge').innerText = d.badge;
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('tot').innerText = (d.g + d.u + d.v).toFixed(2);
            document.getElementById('u-ref').innerText = d.rc;
            
            const ePercent = (d.energy / d.max_energy) * 100;
            document.getElementById('e-bar').style.width = ePercent + "%";
            document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
            document.querySelectorAll('.m-btn').forEach(b => b.disabled = d.energy < 1);

            let r_html = "";
            d.top.forEach((u, i) => { 
                r_html += `<div class="card"><div><span>${i+1}. ${u.n}</span><br><small style="color:#666">${u.b}</small></div><b>${u.p}</b></div>`; 
            });
            document.getElementById('rank-list').innerHTML = r_html;
        }

        async function mine(t) {
            tg.HapticFeedback.impactOccurred('light');
            const res = await fetch(`${apiBase}/api/mine`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { confetti({ particleCount: 15, spread: 20, origin: { y: 0.8 } }); refresh(); }
        }

        function show(p) {
            ['mine', 'pillars', 'leader'].forEach(id => {
                document.getElementById('p-'+id).style.display = (id===p ? 'block' : 'none');
                document.getElementById('n-'+id).classList.toggle('active', id===p);
            });
        }
        function copyRef() {
            navigator.clipboard.writeText(`https://t.me/owpcsbot?start=${uid}`);
            tg.showAlert("Link copied!");
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
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
