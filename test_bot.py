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

# --- DB PATCH ---
def patch_db():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        for col, dtype in [("referred_by", "BIGINT"), ("ref_count", "INTEGER DEFAULT 0"), ("last_energy_update", "BIGINT")]:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit(); c.close(); conn.close()

# --- BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id, name, energy, last_energy_update, referred_by) VALUES (%s, %s, %s, %s, %s)", 
                      (uid, name, MAX_ENERGY, int(time.time()), ref_id))
            if ref_id:
                c.execute("UPDATE users SET ref_count = COALESCE(ref_count,0) + 1 WHERE user_id = %s", (ref_id,))
        conn.commit(); c.close(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome {name}! Start mining OWPC assets.", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as score FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    c.execute("SELECT SUM(COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users")
    jackpot = (c.fetchone()[0] or 0) * 0.1
    
    c.execute("SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as tot FROM users ORDER BY tot DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    
    c.close(); conn.close()
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, 
        "name": r[4], "energy": r[5], "score": round(r[6], 2), "jackpot": round(jackpot, 2), "top": top
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t, comodo = data.get("user_id"), data.get("token"), data.get("is_comodo")
    conn = get_db_conn(); c = conn.cursor()
    gain = 0.05 * (10 if comodo else 1)
    c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+%s, energy=GREATEST(0, energy-1) WHERE user_id=%s AND energy > 0", (gain, uid))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

# --- HTML UI ---
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
        :root { --bg: #050505; --card: #121214; --gold: #FFD700; --blue: #007AFF; --purple: #A259FF; --green: #34C759; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; user-select: none; }
        
        .header { display: flex; justify-content: space-between; font-size: 12px; color: var(--gold); margin-bottom: 15px; padding: 10px; background: #111; border-radius: 10px; }
        .balance-card { text-align: center; padding: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border-radius: 24px; border: 1px solid #333; margin-bottom: 15px; position: relative; overflow: hidden; }
        
        .energy-bar { background: #222; height: 8px; border-radius: 4px; margin: 15px 0; border: 1px solid #333; }
        #e-fill { background: linear-gradient(90deg, var(--green), var(--gold)); height: 100%; width: 0%; transition: 0.2s; }

        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }
        .btn { background: #FFF; color: #000; border: none; padding: 12px 20px; border-radius: 12px; font-weight: 900; }
        .btn:active { transform: scale(0.95); }
        
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); padding: 12px 25px; border-radius: 40px; display: flex; gap: 25px; border: 1px solid #333; }
        .nav-i { font-size: 22px; opacity: 0.4; } .nav-i.active { opacity: 1; color: var(--gold); }

        .floating { position: absolute; color: var(--gold); font-weight: bold; animation: floatUp 0.6s ease-out forwards; pointer-events: none; }
        @keyframes floatUp { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(-50px); } }
    </style>
</head>
<body>
    <div class="header">
        <span>JACKPOT: <span id="jack-val">0</span></span>
        <span>REFS: <span id="ref-val">0</span></span>
    </div>

    <div id="p-mine">
        <div class="balance-card" id="main-box">
            <small style="color:#888">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:48px; margin:10px 0;">0.00</h1>
            <div class="energy-bar"><div id="e-fill"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:11px;"><span id="ev">100/100 ⚡</span><span id="mult-txt">x1</span></div>
        </div>

        <div class="card"><div>GENESIS<div id="gv" style="color:var(--gold)">0.00</div></div><button class="btn" onclick="mine(event, 'genesis')">MINE</button></div>
        <div class="card"><div>UNITY<div id="uv" style="color:var(--blue)">0.00</div></div><button class="btn" onclick="mine(event, 'unity')">SYNC</button></div>
        <div class="card"><div>VEO AI<div id="vv" style="color:var(--purple)">0.00</div></div><button class="btn" onclick="mine(event, 'veo')" style="background:var(--purple); color:#FFF">EXEC</button></div>
    </div>

    <div id="p-ref" style="display:none">
        <h3 style="text-align:center">REFERRAL PROGRAM</h3>
        <div class="card" style="flex-direction:column; gap:10px;">
            <div style="text-align:center">Earn 10% from your friends' mining!</div>
            <button class="btn" style="width:100%; background:var(--gold)" onclick="share()">INVITE FRIENDS</button>
        </div>
        <div id="rl"></div>
    </div>

    <div class="nav">
        <div onclick="sw('mine')" id="n-mine" class="nav-i active">🏠</div>
        <div onclick="sw('ref')" id="n-ref" class="nav-i">👥</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let isComodo = false, curE = 100;

        async function load() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('tot').innerText = d.score.toFixed(2);
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('jack-val').innerText = d.jackpot;
            document.getElementById('ref-val').innerText = d.rc;
            curE = d.energy;
            document.getElementById('e-fill').style.width = curE + "%";
            document.getElementById('ev').innerText = curE + "/100 ⚡";
        }

        async function mine(e, t) {
            if(curE <= 0) return;
            if(!isComodo && Math.random() < 0.01) startComodo();
            
            // Effect
            const f = document.createElement('div'); f.className='floating'; f.innerText='+'+(isComodo?0.5:0.05);
            f.style.left=e.pageX+'px'; f.style.top=e.pageY+'px'; document.body.appendChild(f);
            setTimeout(()=>f.remove(),600);

            curE--; 
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t, is_comodo:isComodo})});
            load(); tg.HapticFeedback.impactOccurred('light');
        }

        function startComodo() {
            isComodo = true; document.getElementById('main-box').style.borderColor = 'var(--gold)';
            document.getElementById('mult-txt').innerText = "x10 🔥";
            setTimeout(() => { isComodo = false; document.getElementById('main-box').style.borderColor = '#333'; document.getElementById('mult-txt').innerText = "x1"; }, 15000);
        }

        function share() { tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/owpcsbot?start=${uid}&text=Join my mining node!`); }
        function sw(p) { ['mine','ref'].forEach(i=>{document.getElementById('p-'+i).style.display=(i===p?'block':'none'); document.getElementById('n-'+i).classList.toggle('active',i===p);}); }
        load(); setInterval(load, 8000); tg.expand();
    </script>
</body>
</html>
"""

async def main():
    patch_db()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize(); await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")).serve()

if __name__ == "__main__":
    asyncio.run(main())
