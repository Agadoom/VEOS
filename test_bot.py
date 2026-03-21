import os, asyncio, uvicorn, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from data_conx import init_db, get_db_conn

TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
RAW_URL = os.getenv("WEBAPP_URL", "")
WEBAPP_URL = RAW_URL if RAW_URL.startswith("http") else f"https://{RAW_URL}"

logging.basicConfig(level=logging.INFO)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MAX_ENERGY = 100
REGEN_RATE = 1 

def patch_db():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS withdrawals (
                id SERIAL PRIMARY KEY, user_id BIGINT, amount DOUBLE PRECISION, wallet TEXT, status TEXT DEFAULT 'PENDING', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.commit()
        except: conn.rollback()
        
        cols = [("staked_amount", "DOUBLE PRECISION DEFAULT 0"), ("streak", "INTEGER DEFAULT 0"), 
                ("ref_claimed", "INTEGER DEFAULT 0"), ("wallet_address", "TEXT")]
        for col, dtype in cols:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
                conn.commit()
            except: conn.rollback()
        c.close(); conn.close()

patch_db()

def get_badge_info(score):
    if score >= 500: return "💎 Diamond", 1000, "#00D1FF"
    if score >= 150: return "🥇 Gold", 500, "#FFD700"
    if score >= 50:  return "🥈 Silver", 150, "#C0C0C0"
    return "🥉 Bronze", 50, "#CD7F32"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id, name, referred_by, energy, last_energy_update) VALUES (%s, %s, %s, %s, %s)", 
                      (uid, name, ref_id if ref_id != uid else None, MAX_ENERGY, int(time.time())))
            if ref_id and ref_id != uid:
                c.execute("UPDATE users SET ref_count = COALESCE(ref_count,0) + 1 WHERE user_id = %s", (ref_id,))
        conn.commit(); c.close(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text("✨ Welcome to OWPC DePIN Hub.", reply_markup=kb)

@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, last_energy_update, streak, staked_amount, wallet_address, ref_claimed FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    now = int(time.time())
    curr_e = min(MAX_ENERGY, (r[5] or 0) + ((now - (r[6] or now)) // 60) * REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, next_g, b_col = get_badge_info(score)
    c.execute("SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as tot FROM users ORDER BY tot DESC LIMIT 8")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    c.execute("SELECT SUM(COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users")
    total_net = c.fetchone()[0] or 0
    c.close(); conn.close()
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[4],
        "energy": int(curr_e), "max_energy": MAX_ENERGY, "badge": badge, "badge_color": b_col,
        "top": top, "jackpot": round(total_net * 0.1, 2), "score": round(score, 2),
        "multiplier": round(1.0 + ((r[8] or 0) / 100) * 0.1 + (score / 1000), 2),
        "wallet": r[9] or "", "streak": r[7] or 0, "staked": r[8] or 0, "pending_refs": (r[3] or 0) - (r[10] or 0)
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05, energy=energy-1, last_energy_update=%s WHERE user_id=%s AND energy > 0", (int(time.time()), uid))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

# --- WEB UI AVEC TOUTES LES SECTIONS ---
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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --green: #34C759; --purple: #A259FF; --text: #8E8E93; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        .header-ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px; font-size: 9px; display: flex; justify-content: space-between; border-bottom: 1px solid #333; }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2c2c2e; }
        .badge-tag { font-size: 9px; padding: 2px 6px; border-radius: 6px; background: #222; border: 1px solid #333; }
        .balance { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; position: relative; }
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; }
        .energy-fill { background: var(--gold); height: 100%; width: 0%; transition: width 0.3s; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 11px; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(15px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 15px; border: 1px solid #333; z-index: 1000; }
        .nav-item { font-size: 20px; opacity: 0.4; } .nav-item.active { opacity: 1; color: var(--gold); }
        input { background: #000; color: #FFF; border: 1px solid #333; padding: 10px; border-radius: 10px; width: 60%; }
    </style>
</head>
<body>
    <div class="header-ticker">
        <span style="color:var(--gold)">REFS: <span id="u-ref-top">0</span></span>
        <span style="color:var(--green)">$WPT: $0.000450</span>
        <span style="color:var(--gold)">JACKPOT: <span id="jack-val">0</span></span>
    </div>
    
    <div class="profile-bar">
        <div><div id="u-name" style="font-weight:700; font-size:13px;">...</div><div id="u-badge" class="badge-tag">...</div></div>
        <button class="btn" style="background:var(--gold);" onclick="claimDaily()">🎁 GIFT</button>
    </div>

    <div id="p-mine">
        <div class="balance">
            <small style="color:var(--text)">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:45px; margin:8px 0;">0.00</h1>
            <div id="u-mult" style="font-size:10px; color:var(--green)">⚡ Multiplier: x1.0</div>
            <div class="energy-bar"><div id="e-bar" class="energy-fill"></div></div>
            <div id="e-text" style="font-size:11px; color:var(--gold);">⚡ 0 / 100</div>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small style="color:var(--purple)">VEO AI</small><div id="vv">0.00</div></div><button class="btn" onclick="mine('veo')" style="background:var(--purple); color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">$WPT PILLARS</h3>
        <div class="card"><b>WPT Token</b><button class="btn" style="background:var(--gold)" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">CLAIM</button></div>
        <div class="card"><b>Unity Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA')">CLAIM</button></div>
        <div class="card"><b>Veo AI Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA')">CLAIM</button></div>
        <button class="btn" style="width:100%; background:var(--blue); color:#FFF; padding:15px;" onclick="share()">🚀 INVITE FRIENDS</button>
    </div>

    <div id="p-leader" style="display:none">
        <h3 style="text-align:center;">GLOBAL RANKING</h3>
        <div id="rank-list"></div>
    </div>

    <div id="p-wallet" style="display:none">
        <h3 style="color:var(--gold); text-align:center;">VAULT & WITHDRAW</h3>
        <div class="card">
            <input type="text" id="w-input" placeholder="TON Address">
            <button class="btn" onclick="saveW()">SAVE</button>
        </div>
        <div class="balance">
            <small>Available</small>
            <h2 id="w-val">0.00</h2>
            <button class="btn" style="background:var(--green); color:#FFF; width:100%" onclick="reqW()">WITHDRAW (Min 100)</button>
        </div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('wallet')" id="n-wallet" class="nav-item">💳</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        async function refresh() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('u-name').innerText = d.name;
            document.getElementById('u-badge').innerText = d.badge;
            document.getElementById('u-badge').style.color = d.badge_color;
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('tot').innerText = d.score.toFixed(2);
            document.getElementById('w-val').innerText = d.score.toFixed(2);
            document.getElementById('u-mult').innerText = `⚡ Multiplier: x${d.multiplier}`;
            document.getElementById('e-bar').style.width = (d.energy/d.max_energy*100) + "%";
            document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
            document.getElementById('jack-val').innerText = d.jackpot;
            document.getElementById('u-ref-top').innerText = d.rc;
            if(d.wallet) document.getElementById('w-input').value = d.wallet;
            let h = ""; d.top.forEach((u,i)=>{ h+=`<div class="card"><div>${i+1}. ${u.n}</div><b>${u.p}</b></div>`; });
            document.getElementById('rank-list').innerHTML = h;
        }
        function show(p) { 
            ['mine','pillars','leader','wallet'].forEach(id=>{
                document.getElementById('p-'+id).style.display=(id===p?'block':'none');
                document.getElementById('n-'+id).classList.toggle('active',id===p);
            });
        }
        async function mine(t) { await fetch('/api/mine',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,token:t})}); refresh(); }
        async function saveW() { 
            const w = document.getElementById('w-input').value;
            await fetch('/api/wallet/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,wallet:w})});
            tg.showAlert("Wallet Saved!");
        }
        async function reqW() {
            const b = parseFloat(document.getElementById('tot').innerText);
            const r = await fetch('/api/withdraw',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,amount:b})});
            if(r.ok){ confetti(); tg.showAlert("Withdrawal Requested!"); refresh(); }
            else tg.showAlert("Error: Min 100 or Missing Wallet");
        }
        function share() { tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/owpcsbot?start=${uid}&text=🚀 Join my Node!`); }
        refresh(); tg.expand();
    </script>
</body>
</html>
"""

async def main():
    init_db()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize(); await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")).serve()

if __name__ == "__main__":
    asyncio.run(main())
