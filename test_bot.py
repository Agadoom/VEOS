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
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 START MINING HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to the World Peace DePIN Network, {name}!\n\nYour mobile node is now active.", reply_markup=kb)

# --- API ---
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
    current_energy = min(MAX_ENERGY, r[6] + int(seconds_passed / 60) * REGEN_RATE)
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT SUM(p_genesis + p_unity + p_veo) FROM users")
    total_mined = c.fetchone()[0] or 0
    c.close(); conn.close()

    # Hardware & Price Data
    market_wpt = round(0.00045 + (random.random() * 0.00005), 6)
    machine_load = random.randint(75, 98) # Simulation de la charge machine

    return {
        "g": r[0], "u": r[1], "v": r[2], "rc": r[3], "name": r[5], 
        "energy": current_energy, "max_energy": MAX_ENERGY,
        "streak": r[8], "can_claim": (now - (r[4] or 0)) >= 86400,
        "global_users": total_users, "global_mined": round(total_mined, 2),
        "price_wpt": market_wpt, "machine_load": machine_load
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute(f"UPDATE users SET p_{t} = p_{t} + 0.05, energy = energy - 1, last_energy_update = %s WHERE user_id = %s", (int(time.time()), uid))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

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
        :root { --bg: #000; --gold: #FFD700; --blue: #007AFF; --text: #8E8E93; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; }
        
        .machine-status { background: #111; border: 1px solid #222; border-radius: 12px; padding: 10px; font-size: 10px; display: flex; justify-content: space-between; margin-bottom: 15px; }
        .status-dot { height: 8px; width: 8px; background: #34C759; border-radius: 50%; display: inline-block; margin-right: 5px; box-shadow: 0 0 8px #34C759; }

        .balance-card { text-align: center; padding: 30px; border-radius: 25px; background: linear-gradient(180deg, #111, #000); border: 1px solid #1a1a1a; margin-bottom: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.8); }
        .energy-bar-bg { background: #222; border-radius: 10px; height: 6px; margin: 15px 0; overflow: hidden; }
        .energy-bar-fill { background: var(--gold); height: 100%; width: 0%; transition: 0.3s; }

        .card { background: #111; padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 20px; border-radius: 12px; font-weight: 800; cursor: pointer; }
        .btn:disabled { opacity: 0.1; }
        
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(10px); padding: 15px 40px; border-radius: 40px; display: flex; gap: 40px; border: 1px solid #333; }
        .nav-item { font-size: 22px; opacity: 0.4; cursor: pointer; }
        .nav-item.active { opacity: 1; color: var(--gold); }
    </style>
</head>
<body>
    <div class="machine-status">
        <span><span class="status-dot"></span> NODE: ONLINE (OWPC-H1)</span>
        <span style="color:var(--text)">LOAD: <span id="m-load">0</span>%</span>
    </div>

    <div id="p-mine">
        <div class="balance-card">
            <small style="color:var(--text)">NETWORK REWARDS</small>
            <h1 id="tot" style="font-size:45px; margin:10px 0;">0.00</h1>
            <div class="energy-bar-bg"><div id="e-bar" class="energy-bar-fill"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:11px;">
                <span id="e-text" style="color:var(--gold)">⚡ 0/100</span>
                <span>$WPT: $<span id="m-price">0.00045</span></span>
            </div>
        </div>

        <div class="card"><div><b>Genesis Asset</b><br><small id="gv">0.00</small></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div><b>Unity Asset</b><br><small id="uv">0.00</small></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><b>Veo AI</b><br><small id="vv">0.00</small></div><button class="btn" onclick="mine('veo')" style="background:var(--blue); color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">$WPT PILLARS</h3>
        <div class="card"><div><b>World Peace Token</b></div><a href="https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA" target="_blank" class="btn" style="background:var(--gold)">FAST BUY</a></div>
        <div class="card"><div><b>Unity</b></div><a href="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA" target="_blank" class="btn">VIEW</a></div>
        <div class="card"><div><b>Veo AI</b></div><a href="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA" target="_blank" class="btn">VIEW</a></div>
        <div class="card"><div><b>Genesis</b></div><a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" target="_blank" class="btn">VIEW</a></div>
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

        async function refresh() {
            const r = await fetch(`${window.location.origin}/api/user/${uid}`);
            const d = await r.json();
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('tot').innerText = (d.g + d.u + d.v).toFixed(2);
            document.getElementById('e-bar').style.width = (d.energy / d.max_energy * 100) + "%";
            document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
            document.getElementById('m-load').innerText = d.machine_load;
            document.getElementById('m-price').innerText = d.price_wpt.toFixed(6);

            let r_html = "";
            d.top.forEach((u, i) => { r_html += `<div class="card"><div>${i+1}. ${u.n}</div><b>${u.p}</b></div>`; });
            document.getElementById('rank-list').innerHTML = r_html;
        }

        async function mine(t) {
            tg.HapticFeedback.impactOccurred('medium');
            await fetch(`${window.location.origin}/api/mine`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            refresh();
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
