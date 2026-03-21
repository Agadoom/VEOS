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

# --- BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("INSERT INTO users (user_id, name, energy) VALUES (%s, %s, 100) ON CONFLICT (user_id) DO NOTHING", (uid, name))
        conn.commit(); c.close(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC Hub, {name}!", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, energy, name FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    c.execute("SELECT SUM(COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users")
    jackpot = (c.fetchone()[0] or 0) * 0.1
    c.close(); conn.close()
    
    return {"g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "energy": r[3], "name": r[4], "jackpot": round(jackpot, 2)}

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    # On ajoute 0.05 par clic
    c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05, energy=GREATEST(0, energy-1) WHERE user_id=%s AND energy > 0", (uid,))
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
    <style>
        :root { --bg: #000; --gold: #FFD700; --card: #111; }
        body { background: var(--bg); color: #fff; font-family: sans-serif; margin: 0; overflow-x: hidden; }
        
        /* BANDE DÉFILANTE CORRIGÉE */
        .ticker-wrap { width: 100%; background: #111; padding: 10px 0; border-bottom: 1px solid var(--gold); overflow: hidden; }
        .ticker { display: inline-block; white-space: nowrap; animation: marquee 20s linear infinite; font-size: 12px; color: var(--gold); font-weight: bold; }
        @keyframes marquee { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        .container { padding: 20px; }
        .main-card { background: radial-gradient(circle, #1a1a1a 0%, #000 100%); border: 1px solid #333; border-radius: 20px; padding: 30px; text-align: center; margin-bottom: 20px; }
        .score { font-size: 50px; font-weight: bold; margin: 10px 0; }
        .energy-bar { background: #222; height: 10px; border-radius: 5px; margin: 15px 0; position: relative; }
        #e-fill { background: var(--gold); height: 100%; width: 100%; border-radius: 5px; transition: 0.3s; }
        
        .card { background: var(--card); border-radius: 15px; padding: 15px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }
        .btn { background: #fff; color: #000; border: none; padding: 12px 25px; border-radius: 10px; font-weight: bold; font-size: 14px; }
        .btn:active { transform: scale(0.9); background: var(--gold); }
        
        .floating { position: absolute; color: var(--gold); font-weight: bold; animation: up 0.5s ease-out forwards; pointer-events: none; }
        @keyframes up { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(-40px); } }
    </style>
</head>
<body>
    <div class="ticker-wrap"><div class="ticker" id="tk">INITIALIZING SENSORS... STANDBY... JACKPOT CALCULATION...</div></div>

    <div class="container">
        <div class="main-card">
            <small style="color: #888;">TOTAL ASSETS ($WPT)</small>
            <div class="score" id="tot">0.00</div>
            <div class="energy-bar"><div id="e-fill"></div></div>
            <div style="font-size: 12px; color: var(--gold);" id="ev">100 / 100 ⚡</div>
        </div>

        <div class="card">
            <div><b style="color:var(--gold)">GENESIS</b><br><small id="gv">0.00</small></div>
            <button class="btn" onclick="mine(event, 'genesis')">MINE</button>
        </div>
        <div class="card">
            <div><b>UNITY</b><br><small id="uv">0.00</small></div>
            <button class="btn" onclick="mine(event, 'unity')">MINE</button>
        </div>
        <div class="card">
            <div><b style="color:#A259FF">VEO AI</b><br><small id="vv">0.00</small></div>
            <button class="btn" onclick="mine(event, 'veo')">MINE</button>
        </div>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        const uid = tg.initDataUnsafe.user?.id || 0;
        let localScore = 0;
        let localEnergy = 100;

        async function updateData() {
            try {
                const r = await fetch(`/api/user/${uid}`);
                const d = await r.json();
                localScore = d.g + d.u + d.v;
                localEnergy = d.energy;
                
                document.getElementById('tot').innerText = localScore.toFixed(2);
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('e-fill').style.width = localEnergy + "%";
                document.getElementById('ev').innerText = localEnergy + " / 100 ⚡";
                document.getElementById('tk').innerText = `🔥 GLOBAL JACKPOT: ${d.jackpot} $WPT • STATUS: MINING ACTIVE • INVITE FRIENDS FOR 10% BONUS •`;
            } catch(e) {}
        }

        function mine(event, type) {
            if (localEnergy <= 0) {
                tg.HapticFeedback.notificationOccurred('error');
                return;
            }

            // Mise à jour visuelle instantanée (UI réactive)
            localScore += 0.05;
            localEnergy -= 1;
            document.getElementById('tot').innerText = localScore.toFixed(2);
            document.getElementById('e-fill').style.width = localEnergy + "%";
            document.getElementById('ev').innerText = localEnergy + " / 100 ⚡";

            // Effet flottant
            const f = document.createElement('div');
            f.className = 'floating';
            f.innerText = '+0.05';
            f.style.left = event.pageX + 'px';
            f.style.top = event.pageY + 'px';
            document.body.appendChild(f);
            setTimeout(() => f.remove(), 500);

            // Envoi au serveur en arrière-plan
            fetch('/api/mine', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: uid, token: type})
            });

            tg.HapticFeedback.impactOccurred('medium');
        }

        updateData();
        setInterval(updateData, 5000); // Sync toutes les 5s
        tg.expand();
    </script>
</body>
</html>
"""

async def main():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")).serve()

if __name__ == "__main__":
    asyncio.run(main())
