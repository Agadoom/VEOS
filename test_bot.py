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
            ("ref_claimed", "INTEGER DEFAULT 0"),
            ("auto_mine_rate", "DOUBLE PRECISION DEFAULT 0.01") # Nouvelle stat
        ]
        for col, dtype in cols:
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
    await update.message.reply_text(f"Welcome {name}! Your DePIN Node is ready.", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, last_energy_update, staked_amount, ref_claimed, auto_mine_rate FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    # Calcul Energy + Auto-Mining Passif depuis la dernière visite
    seconds_passed = now - (r[6] or now)
    passive_gain = (seconds_passed / 3600) * (r[9] or 0.01) # Gain par heure
    
    current_e = min(MAX_ENERGY, (r[5] or 0) + (seconds_passed // 60) * REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, next_goal, b_color = get_badge_info(score)

    c.execute("SELECT name, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) as total FROM users ORDER BY total DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    
    c.execute("SELECT SUM(COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users")
    total_net = c.fetchone()[0] or 0
    c.close(); conn.close()

    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[4],
        "energy": int(current_e), "max_energy": MAX_ENERGY, "badge": badge, "next_goal": next_goal, "badge_color": b_color,
        "top": top, "jackpot": round(total_net * 0.1, 2), "score": round(score, 2),
        "multiplier": round(1.0 + ((r[7] or 0) / 100) * 0.1, 2),
        "staked": r[7] or 0, "pending_refs": max(0, (r[3] or 0) - (r[8] or 0)),
        "auto_rate": r[9] or 0.01
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, staked_amount FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    now = int(time.time()); current_e = min(MAX_ENERGY, (res[0] or 0) + ((now - (res[1] or now)) // 60) * REGEN_RATE)
    if current_e >= 1:
        mult = 1.0 + ((res[2] or 0) / 100) * 0.1
        c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+%s, energy=%s, last_energy_update=%s WHERE user_id=%s", (0.05*mult, current_e-1, now, uid))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"ok": False})

# (Autres routes API: stake, boost, daily restent identiques au précédent code)
# ... [Conserver les fonctions api/stake, api/boost/energy, api/daily du code précédent] ...

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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --text: #8E8E93; --green: #34C759; --purple: #A259FF; }
        body { background: var(--bg); color: #FFF; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        
        /* HEADER BAR */
        .header-ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px; font-size: 10px; display: flex; justify-content: space-between; border-bottom: 1px solid #333; font-weight: bold; }
        
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2c2c2e; }
        .badge-tag { font-size: 10px; padding: 3px 8px; border-radius: 6px; background: #222; border: 1px solid #333; margin-top: 4px; display: inline-block; }
        
        /* MAIN BOARD */
        .balance { text-align: center; padding: 35px 20px; border-radius: 30px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; position: relative; overflow: hidden; }
        .energy-bar { background: #222; border-radius: 10px; height: 10px; margin: 15px 0; overflow: hidden; border: 1px solid #333; }
        .energy-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.3s; }
        
        .card { background: var(--card); padding: 18px; border-radius: 20px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; transition: 0.2s; }
        .card:active { transform: scale(0.98); background: #181818; }
        
        .btn { background: #FFF; color: #000; border: none; padding: 12px 20px; border-radius: 14px; font-weight: 800; cursor: pointer; font-size: 12px; text-transform: uppercase; }
        .btn:disabled { opacity: 0.4; }
        
        /* COMBO FIRE EFFECT */
        #combo-ui { position: absolute; top: 10px; left: 10px; color: #FF4500; font-weight: 900; font-size: 18px; display: none; text-shadow: 0 0 10px #FF4500; animation: shake 0.2s infinite; }
        @keyframes shake { 0% { transform: rotate(0deg); } 50% { transform: rotate(5deg); } 100% { transform: rotate(0deg); } }

        /* NAV */
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.95); backdrop-filter: blur(15px); padding: 15px 30px; border-radius: 50px; display: flex; gap: 25px; border: 1px solid #333; z-index: 1000; }
        .nav-item { font-size: 22px; opacity: 0.3; transition: 0.3s; cursor: pointer; } 
        .nav-item.active { opacity: 1; color: var(--gold); transform: scale(1.2); }

        .floating-text { position: absolute; color: var(--gold); font-weight: bold; pointer-events: none; animation: floatUp 0.6s ease-out forwards; z-index: 100; }
        @keyframes floatUp { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(-50px); } }
    </style>
</head>
<body>
    <div class="header-ticker">
        <span style="color:var(--gold)">👥 REFS: <span id="u-ref-top">0</span></span>
        <span style="color:var(--green)">$WPT: $0.000450</span>
        <span style="color:var(--gold)">🏆 JACKPOT: <span id="jack-val">0</span></span>
    </div>
    
    <div class="profile-bar">
        <div>
            <div id="u-name" style="font-weight:700; font-size:14px;">...</div>
            <div id="u-badge" class="badge-tag">...</div>
        </div>
        <button id="daily-btn" class="btn" style="background:var(--gold);" onclick="claimDaily()">🎁 GIFT</button>
    </div>

    <div id="p-mine">
        <div class="balance">
            <div id="combo-ui">🔥 COMBO x2</div>
            <small style="color:var(--text); letter-spacing: 1px;">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:50px; margin:10px 0; font-variant-numeric: tabular-nums;">0.00</h1>
            <div id="auto-mining-info" style="font-size:10px; color:var(--green); margin-bottom:10px;">⚡ Auto-Mining: <span id="auto-rate">0.01</span>/hr</div>
            <div class="energy-bar"><div id="e-bar" class="energy-fill"></div></div>
            <div id="e-text" style="font-size:12px; color:var(--gold); font-weight:bold;">⚡ 0 / 100</div>
        </div>
        
        <div class="card">
            <div><small style="color:var(--green)">GENESIS</small><div id="gv" style="font-weight:bold; font-size:18px;">0.00</div></div>
            <button class="btn" onclick="mine(event, 'genesis')">MINE</button>
        </div>
        <div class="card">
            <div><small style="color:var(--blue)">UNITY</small><div id="uv" style="font-weight:bold; font-size:18px;">0.00</div></div>
            <button class="btn" onclick="mine(event, 'unity')">SYNC</button>
        </div>
        <div class="card">
            <div><small style="color:var(--purple)">VEO AI</small><div id="vv" style="font-weight:bold; font-size:18px;">0.00</div></div>
            <button class="btn" onclick="mine(event, 'veo')" style="background:var(--purple); color:#FFF">COMPUTE</button>
        </div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('mission')" id="n-mission" class="nav-item">⚙️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; 
        const uid = tg.initDataUnsafe.user?.id || 0;
        let lastClick = 0;
        let comboCount = 0;
        let comboActive = false;

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
            document.getElementById('auto-rate').innerText = d.auto_rate;
            document.getElementById('e-bar').style.width = (d.energy/d.max_energy*100) + "%";
            document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
            document.getElementById('jack-val').innerText = d.jackpot;
            
            // On peut ajouter ici le remplissage automatique visuel toutes les secondes pour l'UX
        }

        function mine(e, t) {
            const now = Date.now();
            // Gestion du Combo
            if (now - lastClick < 400) {
                comboCount++;
                if (comboCount > 5) {
                    comboActive = true;
                    document.getElementById('combo-ui').style.display = 'block';
                }
            } else {
                comboCount = 0;
                comboActive = false;
                document.getElementById('combo-ui').style.display = 'none';
            }
            lastClick = now;

            // Effet visuel
            const rect = e.target.getBoundingClientRect();
            const txt = document.createElement('div');
            txt.className = 'floating-text';
            txt.innerText = comboActive ? '+0.12🔥' : '+0.06';
            txt.style.left = (e.clientX || rect.left) + 'px';
            txt.style.top = (e.clientY || rect.top) + 'px';
            document.body.appendChild(txt);
            setTimeout(() => txt.remove(), 600);

            fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t, combo:comboActive})});
            
            tg.HapticFeedback.impactOccurred(comboActive ? 'medium' : 'light');
            refresh();
        }

        // Simuler l'Auto-Mining visuellement
        setInterval(() => {
            let current = parseFloat(document.getElementById('tot').innerText);
            let rate = parseFloat(document.getElementById('auto-rate').innerText) / 3600;
            document.getElementById('tot').innerText = (current + rate).toFixed(4);
        }, 1000);

        function show(p) { 
            ['mine','pillars','leader','mission'].forEach(id=>{
                const el = document.getElementById('p-'+id);
                if(el) el.style.display=(id===p?'block':'none');
                document.getElementById('n-'+id).classList.toggle('active',id===p);
            }); 
        }

        refresh();
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
