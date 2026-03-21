import os, asyncio, uvicorn, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from data_conx import init_db, get_db_conn

# --- CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
RAW_URL = os.getenv("WEBAPP_URL", "")
WEBAPP_URL = RAW_URL if RAW_URL.startswith("http") else f"https://{RAW_URL}"

logging.basicConfig(level=logging.INFO)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- DATABASE PATCH (Correction Wallet & Tables) ---
def patch_db():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        try:
            # Table pour les retraits
            c.execute("""CREATE TABLE IF NOT EXISTS withdrawals (
                id SERIAL PRIMARY KEY, 
                user_id BIGINT, 
                amount DOUBLE PRECISION, 
                wallet TEXT, 
                status TEXT DEFAULT 'PENDING', 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.commit()
        except: conn.rollback()
        
        # Ajout des colonnes manquantes dans la table users
        cols = [("staked_amount", "DOUBLE PRECISION DEFAULT 0"), 
                ("wallet_address", "TEXT"), 
                ("ref_claimed", "INTEGER DEFAULT 0")]
        for col, dtype in cols:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
                conn.commit()
            except: conn.rollback()
        c.close(); conn.close()
        logging.info("✅ Database Synchronized Successfully.")

# --- FONCTION START (Telegram) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id, name, energy) VALUES (%s, %s, %s)", (uid, name, 100))
            conn.commit()
        c.close(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"🚀 Hello {name}!\nWelcome to OWPC DePIN Hub. Start mining and earn assets.", reply_markup=kb)

# --- API ROUTES ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, wallet_address FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    # Top 5 pour le leaderboard
    c.execute("SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as tot FROM users ORDER BY tot DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    
    c.close(); conn.close()
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[4],
        "energy": r[5] or 0, "score": round(score, 2), "wallet": r[6] or "", "top": top
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05 WHERE user_id=%s", (uid,))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/wallet/save")
async def save_wallet(request: Request):
    data = await request.json(); uid, w = data.get("user_id"), data.get("wallet")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET wallet_address = %s WHERE user_id = %s", (w, uid))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/withdraw")
async def withdraw_api(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)), wallet_address FROM users WHERE user_id=%s", (uid,))
    res = c.fetchone()
    
    # Seuil de sécurité à 95 pour le retrait
    if res and res[0] >= 95:
        if not res[1] or len(res[1]) < 5:
            return JSONResponse(status_code=400, content={"error": "SAVE WALLET FIRST!"})
        
        c.execute("UPDATE users SET p_genesis=0, p_unity=0, p_veo=0 WHERE user_id=%s", (uid,))
        c.execute("INSERT INTO withdrawals (user_id, amount, wallet) VALUES (%s, %s, %s)", (uid, res[0], res[1]))
        conn.commit(); c.close(); conn.close()
        return {"ok": True}
    
    c.close(); conn.close()
    return JSONResponse(status_code=400, content={"error": "Min 100 Assets Required"})

# --- INTERFACE WEB ---
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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --purple: #A259FF; --green: #34C759; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 80px; }
        .card { background: var(--card); padding: 15px; border-radius: 15px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 15px; border-radius: 10px; font-weight: bold; cursor: pointer; }
        .nav { position: fixed; bottom: 15px; left: 50%; transform: translateX(-50%); background: #111; padding: 10px 20px; border-radius: 30px; display: flex; gap: 20px; border: 1px solid #444; z-index:1000;}
        .nav-i { font-size: 20px; opacity: 0.5; cursor: pointer; } .nav-i.active { opacity: 1; color: var(--gold); }
        .balance-main { text-align: center; padding: 25px; background: radial-gradient(circle, #222, #000); border-radius: 20px; margin-bottom: 15px; border: 1px solid #333; }
        input { background: #000; color: #FFF; border: 1px solid #333; padding: 10px; border-radius: 10px; width: 60%; }
    </style>
</head>
<body>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
        <div id="un" style="font-weight:bold">Loading...</div>
        <button class="btn" style="background:var(--gold)" onclick="tg.showAlert('Daily Gift: +10 Unity!')">🎁 GIFT</button>
    </div>

    <div id="p-mine">
        <div class="balance-main">
            <small style="color:#888">AVAILABLE ASSETS</small>
            <h1 id="tv" style="font-size:45px; margin:10px 0;">0.00</h1>
            <div style="color:var(--green); font-size:12px;">⚡ Active Node: Online</div>
        </div>
        <div class="card"><div>GENESIS<div id="gv" style="color:var(--gold)">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div>UNITY<div id="uv" style="color:var(--blue)">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div>VEO AI<div id="vv" style="color:var(--purple)">0.00</div></div><button class="btn" onclick="mine('veo')" style="background:var(--purple); color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-stats" style="display:none">
        <h3 style="color:var(--gold); text-align:center;">MISSIONS</h3>
        <div class="card"><b>Join OWPC Telegram</b><button class="btn" onclick="tg.openLink('https://t.me/blum')">JOIN</button></div>
        <div class="card"><b>Follow on X</b><button class="btn" onclick="tg.openLink('https://twitter.com')">FOLLOW</button></div>
    </div>

    <div id="p-lead" style="display:none">
        <h3 style="text-align:center">TOP MINERS</h3>
        <div id="rl"></div>
    </div>

    <div id="p-wall" style="display:none">
        <h3 style="color:var(--gold); text-align:center;">WALLET & WITHDRAW</h3>
        <div class="card">
            <input type="text" id="wi" placeholder="TON Address">
            <button class="btn" onclick="saveW()" style="background:var(--green); color:#FFF">SAVE</button>
        </div>
        <div class="balance-main">
            <small>Balance</small>
            <h2 id="wv" style="font-size:35px;">0.00</h2>
            <button class="btn" style="background:var(--blue); color:#FFF; width:100%; padding:15px;" onclick="reqW()">WITHDRAW</button>
        </div>
        <p style="font-size:10px; color:#888; text-align:center;">Min: 100 Assets. Note: Click SAVE before Withdraw.</p>
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
            try {
                const r = await fetch(`/api/user/${uid}`); const d = await r.json();
                document.getElementById('un').innerText = d.name;
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tv').innerText = d.score.toFixed(2);
                document.getElementById('wv').innerText = d.score.toFixed(2);
                if(d.wallet) document.getElementById('wi').value = d.wallet;
                let h=""; d.top.forEach((u,i)=>{ h+=`<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
                document.getElementById('rl').innerHTML = h;
            } catch(e) { console.error(e); }
        }
        function sw(p) { 
            ['mine','stats','lead','wall'].forEach(i=>{
                document.getElementById('p-'+i).style.display=(i===p?'block':'none'); 
                document.getElementById('n-'+i).classList.toggle('active',i===p);
            }); 
        }
        async function mine(t) { await fetch('/api/mine',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,token:t})}); load(); tg.HapticFeedback.impactOccurred('light'); }
        async function saveW() { 
            const val = document.getElementById('wi').value;
            if(!val) return tg.showAlert("Enter an address");
            await fetch('/api/wallet/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,wallet:val})}); 
            tg.showAlert("Wallet Saved!"); 
        }
        async function reqW() {
            const res = await fetch('/api/withdraw',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid})});
            if(res.ok){ confetti(); tg.showAlert("Withdrawal Requested!"); load(); } 
            else { const e=await res.json(); tg.showAlert("Error: " + e.error); }
        }
        load(); tg.expand();
    </script>
</body>
</html>
"""

# --- MAIN RUNNER ---
async def main():
    patch_db() # 1. Prepare DB
    bot_app = ApplicationBuilder().token(TOKEN).build()
    
    # 2. Add Telegram handlers (Start is defined above)
    bot_app.add_handler(CommandHandler("start", start))
    
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    
    # 3. Start Web Server
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
