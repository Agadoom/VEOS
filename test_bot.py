import os, asyncio, uvicorn, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- IMPORT DE TON MODULE DATA_CONX ---
from data_conx import init_db, get_db_conn

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# CORS obligatoire pour les communications WebApp <-> API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bot_app = None 

# --- BOT FUNCTIONS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = get_db_conn()
    if conn:
        try:
            c = conn.cursor()
            c.execute("INSERT INTO users (user_id, name) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET name = EXCLUDED.name", (uid, name))
            conn.commit()
            c.close(); conn.close()
            logging.info(f"✅ User {name} ({uid}) prêt dans Postgres.")
        except Exception as e:
            logging.error(f"❌ Erreur SQL Start: {e}")
    
    url = WEBAPP_URL.rstrip('/') # Nettoyage du slash final
    final_url = url if url.startswith("http") else f"https://{url}"
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=final_url))]])
    await update.message.reply_text(f"Welcome {name}!\nYour account is active. Click below to start mining.", reply_markup=kb)

# --- API ENDPOINTS ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn()
    if not conn: return JSONResponse(status_code=500, content={"error": "DB Offline"})
    c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_daily, total_clicks, name FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r:
        c.close(); conn.close()
        return JSONResponse(status_code=404, content={"error": "User not found"})
    c.execute("SELECT token, amount, timestamp FROM logs WHERE user_id=%s ORDER BY id DESC LIMIT 5", (uid,))
    history = [{"t": x[0], "a": x[1], "ts": x[2]} for x in c.fetchall()]
    c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    c.close(); conn.close()
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "history": history, "clicks": r[5], "name": r[6], "top": top}

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    col = {"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}.get(t)
    conn = get_db_conn()
    if conn and col and uid:
        c = conn.cursor()
        c.execute(f"UPDATE users SET {col} = {col} + 0.05, total_clicks = total_clicks + 1 WHERE user_id = %s", (uid,))
        c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (%s, %s, 0.05, %s)", (uid, t.upper(), int(time.time())))
        conn.commit(); c.close(); conn.close()
        return {"ok": True}
    return {"ok": False}

# --- WEB UI (JavaScript Corrigé) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #000; --card: #111; --blue: #007AFF; --green: #34C759; --gold: #FFD700; --text: #8E8E93; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 90px; }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #161618; border-radius: 15px; margin-bottom: 20px; border: 1px solid #2c2c2e; }
        .user-info { display: flex; align-items: center; gap: 10px; }
        .avatar { width: 35px; height: 35px; background: var(--blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; }
        .balance { text-align: center; border: 1px solid #222; padding: 20px; border-radius: 25px; background: linear-gradient(145deg, #050505, #111); margin-bottom: 10px; }
        .energy-container { width: 100%; height: 8px; background: #222; border-radius: 4px; margin: 10px 0; overflow: hidden; }
        .energy-fill { height: 100%; background: linear-gradient(90deg, var(--gold), #FFA500); width: 100%; transition: width 0.2s; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1C1C1E; }
        .btn { background: #FFF; color: #000; border: none; padding: 8px 15px; border-radius: 10px; font-weight: 700; cursor: pointer; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.9); backdrop-filter: blur(15px); padding: 10px 30px; border-radius: 35px; display: flex; gap: 40px; border: 1px solid #333; }
        .nav-item { font-size: 22px; opacity: 0.3; }
        .nav-item.active { opacity: 1; }
        .history-item { display: flex; justify-content: space-between; font-size: 12px; color: var(--text); padding: 5px 0; border-bottom: 1px solid #1c1c1e; }
    </style>
</head>
<body>
    <div class="profile-bar">
        <div class="user-info"><div class="avatar" id="u-avatar">?</div><div style="font-size: 13px; font-weight: 700;" id="u-name">Loading...</div></div>
        <div style="text-align:right"><small style="color:var(--text); font-size:9px">TOTAL CLICKS</small><div id="u-clicks" style="color:var(--gold); font-weight:bold">0</div></div>
    </div>

    <div id="p-mine">
        <div class="balance"><span>TOTAL ASSETS</span><h1 id="tot" style="font-size:38px; margin:5px 0">0.00</h1></div>
        <div style="display:flex; justify-content:space-between; font-size:10px; color:var(--gold)"><span>⚡ ENERGY</span><span id="energy-text">100/100</span></div>
        <div class="energy-container"><div id="energy-fill" class="energy-fill"></div></div>
        <div class="section-title">Mining Units</div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv" style="font-size:16px; font-weight:700">0.00</div></div><button class="btn" onclick="mine('genesis')">CLAIM</button></div>
        <div class="card"><div><small style="color:#FFF">UNITY</small><div id="uv" style="font-size:16px; font-weight:700">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small style="color:var(--blue)">VEO AI</small><div id="vv" style="font-size:16px; font-weight:700">0.00</div></div><button class="btn" onclick="mine('veo')" style="background:var(--blue);color:#FFF">COMPUTE</button></div>
        <div class="section-title">History</div>
        <div id="history-list"></div>
    </div>
    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div class="nav"><div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div><div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div></div>

    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;
        const apiBase = window.location.origin; // Sécurité URL absolue
        let energy = 100;

        async function refresh() {
            if(!uid) return;
            try {
                const r = await fetch(`${apiBase}/api/user/${uid}`);
                if(!r.ok) return;
                const d = await r.json();
                document.getElementById('u-name').innerText = d.name;
                document.getElementById('u-avatar').innerText = d.name[0].toUpperCase();
                document.getElementById('u-clicks').innerText = d.clicks;
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = (d.g + d.u + d.v).toFixed(2);
                
                let h_html = "";
                d.history.forEach(h => { h_html += `<div class="history-item"><span>${h.t}</span><b>+${h.a}</b></div>`; });
                document.getElementById('history-list').innerHTML = h_html;
            } catch(e) { console.error(e); }
        }

        async function mine(t) {
            if(energy <= 0 || !uid) return;
            energy--; updateUI();
            tg.HapticFeedback.impactOccurred('light');
            await fetch(`${apiBase}/api/mine`, {
                method:'POST', 
                headers:{'Content-Type':'application/json'}, 
                body:JSON.stringify({user_id:uid, token:t})
            });
            refresh();
        }

        function updateUI() {
            document.getElementById('energy-text').innerText = energy + "/100";
            document.getElementById('energy-fill').style.width = energy + "%";
        }
        function show(p) {
            document.getElementById('p-mine').style.display = p=='mine'?'block':'none';
            document.getElementById('p-leader').style.display = p=='leader'?'block':'none';
            document.getElementById('n-mine').classList.toggle('active', p=='mine');
            document.getElementById('n-leader').classList.toggle('active', p=='leader');
        }
        setInterval(() => { if(energy < 100) { energy++; updateUI(); } }, 2000);
        refresh();
    </script>
</body>
</html>
    """

async def main():
    global bot_app
    init_db()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT)
    await uvicorn.Server(config).serve()

if __name__ == "__main__":
    asyncio.run(main())
