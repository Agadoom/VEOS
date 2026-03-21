import os, asyncio, uvicorn, logging, random
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

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, name, energy FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    c.execute("SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as tot FROM users ORDER BY tot DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    c.close(); conn.close()
    return {"g":r[0], "u":r[1], "v":r[2], "name":r[3], "score":round(score,2), "energy": r[4] or 0, "top":top}

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t, mult = data.get("user_id"), data.get("token"), data.get("mult", 1)
    conn = get_db_conn(); c = conn.cursor()
    # On baisse l'énergie de 1 et on ajoute les points avec le multiplicateur
    gain = 0.05 * mult
    c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+%s, energy=GREATEST(0, energy-1) WHERE user_id=%s AND energy > 0", (gain, uid))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/refill")
async def refill_api(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET energy=100 WHERE user_id=%s", (uid,))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

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
        :root { --bg: #050505; --card: #121214; --gold: #FFD700; --blue: #007AFF; --purple: #A259FF; --green: #34C759; --red: #FF3B30; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; overflow: hidden; user-select: none; }
        
        .ticker-wrap { background: #111; margin: -15px -15px 15px -15px; overflow: hidden; white-space: nowrap; border-bottom: 1px solid #222; padding: 8px 0; }
        .ticker { display: inline-block; animation: scroll 25s linear infinite; font-family: monospace; font-size: 11px; color: var(--gold); }
        @keyframes scroll { from { transform: translateX(100%); } to { transform: translateX(-100%); } }

        .balance-main { text-align: center; padding: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border-radius: 24px; border: 1px solid #333; margin-bottom: 15px; transition: 0.3s; }
        .comodo-active { border-color: var(--gold); box-shadow: 0 0 20px rgba(255,215,0,0.4); }

        .energy-bar { background: #222; height: 10px; border-radius: 5px; margin: 10px 0; border: 1px solid #333; position: relative; }
        #energy-fill { background: linear-gradient(90deg, var(--green), var(--gold)); width: 100%; height: 100%; border-radius: 5px; transition: 0.3s; }
        
        .card { background: var(--card); padding: 15px; border-radius: 16px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: bold; }
        .btn:disabled { opacity: 0.3; }

        #comodo-alert { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: var(--gold); color: #000; padding: 20px; border-radius: 20px; font-weight: 900; z-index: 2000; display: none; animation: pulse 0.5s infinite; }
        @keyframes pulse { 0% { transform: translate(-50%, -50%) scale(1); } 50% { transform: translate(-50%, -50%) scale(1.1); } 100% { transform: translate(-50%, -50%) scale(1); } }
        
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); padding: 12px 25px; border-radius: 40px; display: flex; gap: 30px; border: 1px solid #333; }
        .nav-i { font-size: 24px; opacity: 0.3; } .nav-i.active { opacity: 1; color: var(--gold); }
    </style>
</head>
<body>
    <div id="comodo-alert">🔥 COMODO X10 ACTIVE !!!</div>

    <div class="ticker-wrap"><div class="ticker">DEPIN TERMINAL ONLINE • SYSTEM STATUS: SECURE • AUTO-MINING ENABLED • </div></div>

    <div id="p-mine">
        <div class="balance-main" id="main-box">
            <small id="status-label" style="color:#888">ASSETS BALANCE</small>
            <h1 id="tv" style="font-size:48px; margin:10px 0;">0.00</h1>
            
            <div class="energy-bar"><div id="energy-fill"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:11px;">
                <span id="ev">100/100 ⚡</span>
                <span id="mult-ui" style="color:var(--gold); font-weight:bold;">x1</span>
            </div>
            
            <button id="drink-btn" class="btn" style="display:none; width:100%; margin-top:15px; background:var(--blue); color:#FFF;" onclick="buyDrink()">🥤 DRINK ENERGY (REFILL)</button>
        </div>

        <div class="card"><div>GENESIS<div id="gv" style="color:var(--gold)">0.00</div></div><button class="btn mine-btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div>UNITY<div id="uv" style="color:var(--blue)">0.00</div></div><button class="btn mine-btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div>VEO AI<div id="vv" style="color:var(--purple)">0.00</div></div><button class="btn mine-btn" onclick="mine('veo')" style="background:var(--purple); color:#FFF">EXEC</button></div>
    </div>

    <div id="p-stats" style="display:none; text-align:center;"><h3>PILLARS</h3><div class="card">Join Channel <button class="btn">GO</button></div></div>
    <div id="p-lead" style="display:none"><h3>LEADERBOARD</h3><div id="rl"></div></div>

    <div class="nav">
        <div onclick="sw('mine')" id="n-mine" class="nav-i active">🏠</div>
        <div onclick="sw('stats')" id="n-stats" class="nav-i">📊</div>
        <div onclick="sw('lead')" id="n-lead" class="nav-i">🏆</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let currentEnergy = 100;
        let multiplier = 1;
        let isComodo = false;

        async function load() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('tv').innerText = d.score.toFixed(2);
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            currentEnergy = d.energy;
            updateEnergyUI();
            
            let h=""; d.top.forEach((u,i)=>{ h+=`<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
            document.getElementById('rl').innerHTML = h;
        }

        function updateEnergyUI() {
            document.getElementById('energy-fill').style.width = currentEnergy + "%";
            document.getElementById('ev').innerText = currentEnergy + "/100 ⚡";
            
            const btns = document.querySelectorAll('.mine-btn');
            const drink = document.getElementById('drink-btn');
            
            if(currentEnergy <= 0) {
                btns.forEach(b => b.disabled = true);
                drink.style.display = "block";
            } else {
                btns.forEach(b => b.disabled = false);
                drink.style.display = "none";
            }
        }

        async function mine(t) {
            if(currentEnergy <= 0) return;
            
            // Random Comodo Trigger (1% de chance par clic)
            if(!isComodo && Math.random() < 0.01) { startComodo(); }

            currentEnergy -= 1;
            updateEnergyUI();

            await fetch('/api/mine', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({user_id:uid, token:t, mult: multiplier})
            });
            load();
            tg.HapticFeedback.impactOccurred('light');
        }

        function startComodo() {
            isComodo = true; multiplier = 10;
            document.getElementById('comodo-alert').style.display = "block";
            document.getElementById('main-box').classList.add('comodo-active');
            document.getElementById('mult-ui').innerText = "x10 🔥";
            
            setTimeout(() => {
                isComodo = false; multiplier = 1;
                document.getElementById('comodo-alert').style.display = "none";
                document.getElementById('main-box').classList.remove('comodo-active');
                document.getElementById('mult-ui').innerText = "x1";
            }, 15000); // Dure 15 secondes
        }

        async function buyDrink() {
            await fetch('/api/refill', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            currentEnergy = 100;
            updateEnergyUI();
            tg.showAlert("Energy Refilled! Let's go!");
        }

        function sw(p) { ['mine','stats','lead'].forEach(i=>{document.getElementById('p-'+i).style.display=(i===p?'block':'none'); document.getElementById('n-'+i).classList.toggle('active',i===p);}); }
        
        load(); tg.expand();
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
