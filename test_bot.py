import os, asyncio, uvicorn, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from data_conx import get_db_conn

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
RAW_URL = os.getenv("WEBAPP_URL", "")
WEBAPP_URL = RAW_URL if RAW_URL.startswith("http") else f"https://{RAW_URL}"

logging.basicConfig(level=logging.INFO)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MAX_ENERGY = 100
REGEN_RATE = 1 # 1% d'énergie par minute

# --- REGEN LOGIC ---
def get_current_energy(db_energy, last_update):
    now = int(time.time())
    elapsed_minutes = (now - last_update) // 60
    new_energy = db_energy + (elapsed_minutes * REGEN_RATE)
    return min(MAX_ENERGY, int(new_energy))

# --- BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("INSERT INTO users (user_id, name, energy, last_energy_update) VALUES (%s, %s, 100, %s) ON CONFLICT (user_id) DO NOTHING", 
                  (uid, name, int(time.time())))
        conn.commit(); c.close(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome back, {name}!", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, energy, last_energy_update, name, ref_count FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    # Calcul de l'énergie actuelle avec le temps passé
    actual_e = get_current_energy(r[3], r[4])
    
    # Calcul du Jackpot Global (Somme de tous les points / 10)
    c.execute("SELECT SUM(COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users")
    jackpot = (c.fetchone()[0] or 0) * 0.1
    
    c.close(); conn.close()
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, 
        "energy": actual_e, "name": r[5], "rc": r[6] or 0, "jackpot": round(jackpot, 2)
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    
    # Vérifier l'énergie avant de miner
    c.execute("SELECT energy, last_energy_update FROM users WHERE user_id=%s", (uid,))
    res = c.fetchone()
    current_e = get_current_energy(res[0], res[1])
    
    if current_e > 0:
        # On déduis 1 d'énergie et on ajoute les points
        c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05, energy=%s, last_energy_update=%s WHERE user_id=%s", 
                  (current_e - 1, int(time.time()), uid))
        conn.commit()
        c.close(); conn.close()
        return {"ok": True}
    
    c.close(); conn.close()
    return JSONResponse(status_code=400, content={"error": "No energy"})

# --- UI ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #000; --gold: #FFD700; --card: #121214; }
        body { background: var(--bg); color: #fff; font-family: sans-serif; margin: 0; overflow-x: hidden; }
        
        .ticker-wrap { width: 100%; background: #111; padding: 12px 0; border-bottom: 1px solid #333; overflow: hidden; }
        .ticker { display: inline-block; white-space: nowrap; animation: marquee 15s linear infinite; color: var(--gold); font-weight: bold; font-size: 13px; }
        @keyframes marquee { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        .container { padding: 15px; }
        .main-card { background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; border-radius: 20px; padding: 25px; text-align: center; margin-bottom: 15px; }
        .energy-bar { background: #222; height: 10px; border-radius: 5px; margin: 15px 0; overflow: hidden; border: 1px solid #333; }
        #e-fill { background: linear-gradient(90deg, #34C759, var(--gold)); height: 100%; width: 0%; transition: 0.3s; }
        
        .card { background: var(--card); border-radius: 15px; padding: 15px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }
        .btn { background: #fff; color: #000; border: none; padding: 12px 22px; border-radius: 12px; font-weight: bold; }
        .btn:active { transform: scale(0.9); }
        
        .nav { position: fixed; bottom: 15px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.9); padding: 10px 25px; border-radius: 30px; display: flex; gap: 25px; border: 1px solid #333; backdrop-filter: blur(10px); }
        .nav-i { font-size: 22px; opacity: 0.4; } .nav-i.active { opacity: 1; color: var(--gold); }
    </style>
</head>
<body>
    <div class="ticker-wrap"><div class="ticker" id="tk">CONNECTING TO NODE... STANDBY...</div></div>

    <div class="container" id="p-mine">
        <div class="main-card">
            <small style="color: #888;">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size: 45px; margin: 10px 0;">0.00</h1>
            <div class="energy-bar"><div id="e-fill"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:12px;">
                <span id="ev" style="color: var(--gold);">100 / 100 ⚡</span>
                <span style="color: #555;">REGEN ACTIVE</span>
            </div>
        </div>

        <div class="card"><div><b style="color:var(--gold)">GENESIS</b><br><small id="gv">0.00</small></div><button class="btn" onclick="mine(event, 'genesis')">MINE</button></div>
        <div class="card"><div><b>UNITY</b><br><small id="uv">0.00</small></div><button class="btn" onclick="mine(event, 'unity')">MINE</button></div>
        <div class="card"><div><b style="color:#A259FF">VEO AI</b><br><small id="vv">0.00</small></div><button class="btn" onclick="mine(event, 'veo')">MINE</button></div>
    </div>

    <div class="container" id="p-pill" style="display:none">
        <h3 style="color:var(--gold)">PILLARS REWARDS</h3>
        <div class="card">WPT TOKEN<button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card">UNITY ASSET<button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card">VEO AI<button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card">GENESIS<button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA')">GO</button></div>
    </div>

    <div class="nav">
        <div onclick="sw('mine')" id="n-mine" class="nav-i active">🏠</div>
        <div onclick="sw('pill')" id="n-pill" class="nav-i">📊</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let lScore = 0, lEnergy = 100;

        async function load() {
            try {
                const r = await fetch(`/api/user/${uid}`); const d = await r.json();
                lScore = d.g + d.u + d.v; lEnergy = d.energy;
                document.getElementById('tot').innerText = lScore.toFixed(2);
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('e-fill').style.width = lEnergy + "%";
                document.getElementById('ev').innerText = lEnergy + " / 100 ⚡";
                document.getElementById('tk').innerText = `🔥 GLOBAL JACKPOT: ${d.jackpot} $WPT • STATUS: NODE ONLINE • ENERGY REGEN: 1%/MIN •`;
            } catch(e) {}
        }

        function mine(e, t) {
            if(lEnergy <= 0) { tg.HapticFeedback.notificationOccurred('error'); return; }
            lScore += 0.05; lEnergy -= 1;
            document.getElementById('tot').innerText = lScore.toFixed(2);
            document.getElementById('e-fill').style.width = lEnergy + "%";
            document.getElementById('ev').innerText = lEnergy + " / 100 ⚡";
            
            fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            tg.HapticFeedback.impactOccurred('medium');
        }

        function sw(p) { ['mine','pill'].forEach(id=>{ document.getElementById('p-'+id).style.display=(id===p?'block':'none'); document.getElementById('n-'+id).classList.toggle('active',id===p); }); }
        
        load(); setInterval(load, 10000); tg.expand();
    </script>
</body>
</html>
"""

async def main():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize(); await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")).serve()

if __name__ == "__main__":
    asyncio.run(main())
