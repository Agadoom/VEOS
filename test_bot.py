import os, asyncio, uvicorn, logging, time
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

# --- DB PATCH ---
def patch_db():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        try:
            c.execute("CREATE TABLE IF NOT EXISTS withdrawals (id SERIAL PRIMARY KEY, user_id BIGINT, amount DOUBLE PRECISION, wallet TEXT, status TEXT DEFAULT 'PENDING', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            conn.commit()
        except: conn.rollback()
        c.close(); conn.close()
        logging.info("✅ DB Sync OK")

# --- TELEGRAM BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("INSERT INTO users (user_id, name, energy) VALUES (%s, %s, 100) ON CONFLICT (user_id) DO NOTHING", (uid, name))
        conn.commit(); c.close(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ TERMINAL ACCESS", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC Network.", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, name, wallet_address FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    c.execute("SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as tot FROM users ORDER BY tot DESC LIMIT 8")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    c.execute("SELECT SUM(COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users")
    jackpot = (c.fetchone()[0] or 0) * 0.1
    c.close(); conn.close()
    return {"g":r[0] or 0, "u":r[1] or 0, "v":r[2] or 0, "name":r[4], "score":round(score,2), "wallet":r[5] or "", "top":top, "jackpot":round(jackpot,2)}

@app.post("/api/gift")
async def claim_gift(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET p_genesis = COALESCE(p_genesis,0) + 5 WHERE user_id = %s", (uid,))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05 WHERE user_id=%s", (uid,))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

@app.post("/api/wallet/save")
async def save_wallet(request: Request):
    data = await request.json(); uid, w = data.get("user_id"), data.get("wallet")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET wallet_address = %s WHERE user_id = %s", (w, uid))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

@app.post("/api/withdraw")
async def withdraw_api(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)), wallet_address FROM users WHERE user_id=%s", (uid,))
    res = c.fetchone()
    if res and res[0] >= 95 and res[1]:
        c.execute("UPDATE users SET p_genesis=0, p_unity=0, p_veo=0 WHERE user_id=%s", (uid,))
        c.execute("INSERT INTO withdrawals (user_id, amount, wallet) VALUES (%s, %s, %s)", (uid, res[0], res[1]))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"error": "Balance < 100 or No Wallet"})

# --- UI HTML ---
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
        body { background: var(--bg); color: #FFF; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 15px; overflow-x: hidden; }
        .ticker { background: rgba(255,255,255,0.03); margin: -15px -15px 15px -15px; padding: 10px; font-size: 11px; display: flex; justify-content: space-between; border-bottom: 1px solid #222; font-family: monospace; }
        .balance-main { text-align: center; padding: 35px 20px; background: radial-gradient(circle at top, #1a1a1a, #050505); border-radius: 25px; margin-bottom: 20px; border: 1px solid #333; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .card { background: var(--card); padding: 18px; border-radius: 16px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; transition: 0.3s; }
        .card:active { transform: scale(0.98); background: #18181b; }
        .btn { background: #FFF; color: #000; border: none; padding: 12px 20px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 13px; }
        .btn-g { background: linear-gradient(135deg, var(--gold), #B8860B); color: #000; box-shadow: 0 4px 15px rgba(255,215,0,0.2); }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); padding: 12px 25px; border-radius: 40px; display: flex; gap: 30px; border: 1px solid #333; backdrop-filter: blur(10px); z-index: 1000; }
        .nav-i { font-size: 24px; opacity: 0.3; transition: 0.3s; } .nav-i.active { opacity: 1; color: var(--gold); transform: translateY(-3px); }
        h1 { font-size: 50px; margin: 5px 0; font-weight: 900; letter-spacing: -2px; }
        input { background: #000; color: #FFF; border: 1px solid #333; padding: 12px; border-radius: 12px; width: 60%; }
    </style>
</head>
<body>
    <div class="ticker">
        <span style="color:#888">OWPC_NETWORK: <b id="tj" style="color:var(--gold)">0.00</b></span>
        <span id="node-status" style="color:var(--green)">● ONLINE</span>
    </div>

    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
        <div id="un" style="font-weight:bold; font-size:18px; color:var(--blue)">...</div>
        <button id="gift-btn" class="btn btn-g" onclick="handleGift()">🎁 GIFT</button>
    </div>

    <div id="p-mine">
        <div class="balance-main">
            <small style="color:#666; font-weight:bold; text-transform:uppercase; letter-spacing:1px;">Global Balance</small>
            <h1 id="tv">0.00</h1>
            <div style="font-size:12px; color:var(--green)">+ Multiplier Active</div>
        </div>
        <div class="card"><div>GENESIS<div id="gv" style="color:var(--gold); font-weight:bold">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div>UNITY<div id="uv" style="color:var(--blue); font-weight:bold">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div>VEO AI<div id="vv" style="color:var(--purple); font-weight:bold">0.00</div></div><button class="btn" onclick="mine('veo')" style="background:var(--purple); color:#FFF">EXECUTE</button></div>
    </div>

    <div id="p-stats" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">STAKING & PILLARS</h3>
        <div class="card"><b>OWPC Community</b><button class="btn" onclick="tg.openLink('https://t.me/blum')">JOIN</button></div>
        <div class="card"><b>X Follow</b><button class="btn" onclick="tg.openLink('https://twitter.com')">FOLLOW</button></div>
    </div>

    <div id="p-lead" style="display:none"><h3 style="text-align:center">TOP NODES</h3><div id="rl"></div></div>

    <div id="p-wall" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">VAULT</h3>
        <div class="card"><input type="text" id="wi" placeholder="TON Address"><button class="btn" onclick="saveW()" style="background:var(--green); color:#FFF">SAVE</button></div>
        <div class="balance-main" style="border-color:var(--blue)">
            <small>Withdrawable</small>
            <h2 id="wv" style="font-size:40px; margin:10px 0;">0.00</h2>
            <button class="btn" style="background:var(--blue); color:#FFF; width:100%;" onclick="reqW()">WITHDRAW</button>
        </div>
    </div>

    <div class="nav">
        <div onclick="sw('mine')" id="n-mine" class="nav-i active">🏠</div>
        <div onclick="sw('stats')" id="n-stats" class="nav-i">📊</div>
        <div onclick="sw('lead')" id="n-lead" class="nav-i">🏆</div>
        <div onclick="sw('wall')" id="n-wall" class="nav-i">💳</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        async function load() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('un').innerText = d.name.toUpperCase();
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('tv').innerText = d.score.toFixed(2);
            document.getElementById('wv').innerText = d.score.toFixed(2);
            document.getElementById('tj').innerText = d.jackpot.toFixed(2);
            if(d.wallet) document.getElementById('wi').value = d.wallet;
            let h=""; d.top.forEach((u,i)=>{ h+=`<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
            document.getElementById('rl').innerHTML = h;
        }

        function handleGift() {
            const now = Date.now();
            const last = localStorage.getItem('last_gift_' + uid);
            const cooldown = 12 * 60 * 60 * 1000; // 12h

            if (last && (now - last < cooldown)) {
                const remaining = Math.ceil((cooldown - (now - last)) / (60 * 60 * 1000));
                tg.showAlert("Cooldown active! Come back in " + remaining + " hours.");
            } else {
                fetch('/api/gift', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})})
                .then(() => {
                    localStorage.setItem('last_gift_' + uid, now);
                    confetti(); tg.showAlert("Gift claimed: +5 Genesis Assets!"); load();
                });
            }
        }

        function sw(p) { ['mine','stats','lead','wall'].forEach(i=>{document.getElementById('p-'+i).style.display=(i===p?'block':'none'); document.getElementById('n-'+i).classList.toggle('active',i===p);}); }
        async function mine(t) { await fetch('/api/mine',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,token:t})}); load(); tg.HapticFeedback.impactOccurred('medium'); }
        async function saveW() { await fetch('/api/wallet/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,wallet:document.getElementById('wi').value})}); tg.showAlert("Wallet Saved!"); }
        async function reqW() {
            const res = await fetch('/api/withdraw',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid})});
            if(res.ok){ confetti(); tg.showAlert("Success! Pending validation."); load(); } else { const e=await res.json(); tg.showAlert(e.error); }
        }
        load(); tg.expand();
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
