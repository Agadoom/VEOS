import os, asyncio, uvicorn, logging, time, random
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

# --- DATABASE SETUP ---
def patch_db():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        cols = [
            ("referred_by", "BIGINT"),
            ("ref_count", "INTEGER DEFAULT 0"),
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"),
            ("last_energy_update", "BIGINT")
        ]
        for col, dtype in cols:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit(); c.close(); conn.close()

# --- BOT LOGIC (REFERRAL) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id, name, energy, referred_by) VALUES (%s, %s, 100, %s)", (uid, name, ref_id))
            if ref_id:
                c.execute("UPDATE users SET ref_count = COALESCE(ref_count,0) + 1 WHERE user_id = %s", (ref_id,))
        conn.commit(); c.close(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 ENTER TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to the Hub, {name}!", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, energy, name, ref_count, staked_amount FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    c.execute("SELECT SUM(COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users")
    jackpot = (c.fetchone()[0] or 0) * 0.1
    
    c.execute("SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as tot FROM users ORDER BY tot DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    
    c.close(); conn.close()
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "energy": r[3], 
        "name": r[4], "rc": r[5] or 0, "staked": r[6] or 0, 
        "jackpot": round(jackpot, 2), "top": top
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05, energy=GREATEST(0, energy-1) WHERE user_id=%s AND energy > 0", (uid,))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

# --- UI INTERFACE ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #000; --gold: #FFD700; --card: #121214; --blue: #007AFF; --purple: #A259FF; }
        body { background: var(--bg); color: #fff; font-family: sans-serif; margin: 0; padding-bottom: 80px; overflow-x: hidden; }
        
        .ticker-wrap { width: 100%; background: #111; padding: 10px 0; border-bottom: 1px solid #333; overflow: hidden; position: sticky; top: 0; z-index: 100; }
        .ticker { display: inline-block; white-space: nowrap; animation: marquee 15s linear infinite; color: var(--gold); font-size: 12px; font-weight: bold; }
        @keyframes marquee { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        .container { padding: 15px; }
        .main-card { background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; border-radius: 20px; padding: 25px; text-align: center; margin-bottom: 15px; }
        .energy-bar { background: #222; height: 8px; border-radius: 4px; margin: 15px 0; overflow: hidden; }
        #e-fill { background: var(--gold); height: 100%; width: 100%; transition: 0.3s; }
        
        .card { background: var(--card); border-radius: 15px; padding: 15px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }
        .btn { background: #fff; color: #000; border: none; padding: 10px 20px; border-radius: 10px; font-weight: bold; }
        .btn:active { transform: scale(0.9); }

        .nav { position: fixed; bottom: 15px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.9); padding: 10px 20px; border-radius: 30px; display: flex; gap: 20px; border: 1px solid #333; backdrop-filter: blur(10px); }
        .nav-item { font-size: 20px; opacity: 0.4; cursor: pointer; }
        .nav-item.active { opacity: 1; color: var(--gold); }
        
        .floating { position: absolute; color: var(--gold); font-weight: bold; animation: floatUp 0.5s ease-out forwards; pointer-events: none; }
        @keyframes floatUp { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(-40px); } }
    </style>
</head>
<body>
    <div class="ticker-wrap"><div class="ticker" id="tk">SYNCING NODE... JACKPOT: 0.00 $WPT...</div></div>

    <div class="container" id="p-mine">
        <div class="main-card">
            <small style="color: #888;">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size: 40px; margin: 10px 0;">0.00</h1>
            <div class="energy-bar"><div id="e-fill"></div></div>
            <div style="font-size: 11px; color: var(--gold);" id="ev">100 / 100 ⚡</div>
        </div>
        <div class="card"><div><b style="color:var(--gold)">GENESIS</b><br><small id="gv">0.00</small></div><button class="btn" onclick="mine(event, 'genesis')">MINE</button></div>
        <div class="card"><div><b style="color:var(--blue)">UNITY</b><br><small id="uv">0.00</small></div><button class="btn" onclick="mine(event, 'unity')">MINE</button></div>
        <div class="card"><div><b style="color:var(--purple)">VEO AI</b><br><small id="vv">0.00</small></div><button class="btn" onclick="mine(event, 'veo')">MINE</button></div>
    </div>

    <div class="container" id="p-pill" style="display:none">
        <h3 style="color:var(--gold)">PILLARS</h3>
        <div class="card">WPT TOKEN<button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card">UNITY ASSET<button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card">VEO AI<button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card">GENESIS<button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA')">GO</button></div>
    </div>

    <div class="container" id="p-ref" style="display:none">
        <h3 style="color:var(--gold)">REFERRALS</h3>
        <div class="main-card">
            <h2 id="ref-count">0</h2>
            <small>Friends Invited</small><br><br>
            <button class="btn" style="width:100%; background:var(--gold)" onclick="share()">INVITE FRIENDS</button>
        </div>
        <div id="rl"></div>
    </div>

    <div class="nav">
        <div onclick="sw('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="sw('pill')" id="n-pill" class="nav-item">📊</div>
        <div onclick="sw('ref')" id="n-ref" class="nav-item">👥</div>
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
                document.getElementById('ref-count').innerText = d.rc;
                document.getElementById('e-fill').style.width = lEnergy + "%";
                document.getElementById('ev').innerText = lEnergy + " / 100 ⚡";
                document.getElementById('tk').innerText = `🔥 JACKPOT: ${d.jackpot} $WPT • STATUS: NODE ONLINE • MINING AT 100% CAPACITY •`;
                
                let h=""; d.top.forEach((u,i)=>{ h+=`<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
                document.getElementById('rl').innerHTML = h;
            } catch(e) {}
        }

        function mine(e, t) {
            if(lEnergy <= 0) return;
            lScore += 0.05; lEnergy -= 1;
            document.getElementById('tot').innerText = lScore.toFixed(2);
            document.getElementById('e-fill').style.width = lEnergy + "%";
            document.getElementById('ev').innerText = lEnergy + " / 100 ⚡";

            const f = document.createElement('div'); f.className='floating'; f.innerText='+0.05';
            f.style.left=e.pageX+'px'; f.style.top=e.pageY+'px'; document.body.appendChild(f);
            setTimeout(()=>f.remove(), 500);

            fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            tg.HapticFeedback.impactOccurred('medium');
        }

        function sw(p) { 
            ['mine','pill','ref'].forEach(id=>{
                document.getElementById('p-'+id).style.display=(id===p?'block':'none');
                document.getElementById('n-'+id).classList.toggle('active', id===p);
            });
        }

        function share() {
            tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/owpcsbot?start=${uid}&text=🚀 Join my mining node on OWPC!`);
        }

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
