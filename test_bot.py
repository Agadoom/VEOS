import os, asyncio, uvicorn, logging, time, random, datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application
from telegram.error import Forbidden

from data_conx import init_db, get_db_conn

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 1414016840 
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
        try:
            c = conn.cursor()
            # On s'assure que toutes les colonnes de progression sont là
            cols = [
                ("staked_amount", "DOUBLE PRECISION DEFAULT 0"),
                ("streak", "INTEGER DEFAULT 0"),
                ("last_streak_date", "TEXT"),
                ("missions_done", "TEXT DEFAULT ''"),
                ("wallet_address", "TEXT DEFAULT ''") # Nouvelle colonne pour le Wallet
            ]
            for col, dtype in cols:
                try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
                except: pass
            conn.commit(); c.close(); conn.close()
        except Exception as e: logging.error(f"Patch error: {e}")

patch_db()

# --- UTILS ---
def get_badge(score, streak=0):
    if streak >= 7: return "🔥 Streak Master"
    if score >= 500: return "💎 Diamond"
    if score >= 150: return "🥇 Gold"
    if score >= 50:  return "🥈 Silver"
    return "🥉 Bronze"

# --- BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    if update.effective_chat.type in ['group', 'supergroup']: return 

    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    if ref_id == uid: ref_id = None

    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
        if not c.fetchone():
            c.execute("""INSERT INTO users (user_id, name, referred_by, energy, last_energy_update, 
                         staked_amount, streak, missions_done) VALUES (%s, %s, %s, %s, %s, 0, 0, '')""", 
                      (uid, name, ref_id, MAX_ENERGY, int(time.time())))
            if ref_id:
                c.execute("UPDATE users SET p_unity = COALESCE(p_unity,0) + 10.0, ref_count = COALESCE(ref_count,0) + 1 WHERE user_id = %s", (ref_id,))
        conn.commit(); c.close(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text("✨ Welcome to OWPC DePIN Hub.\nNode Synchronized.", reply_markup=kb)

# --- API (TON CODE OPÉRATIONNEL + WALLET) ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    try:
        # Tentative de lecture complète
        c.execute("""SELECT p_genesis, p_unity, p_veo, ref_count, last_streak_date, name, 
                     energy, last_energy_update, streak, staked_amount, 
                     COALESCE(missions_done, ''), COALESCE(wallet_address, '') 
                     FROM users WHERE user_id=%s""", (uid,))
        r = c.fetchone()
    except Exception as e:
        # SI CA PLANTE : On fait un SELECT de secours sur les colonnes de base
        logging.warning(f"Fallback activé : {e}")
        c.execute("""SELECT p_genesis, p_unity, p_veo, ref_count, last_streak_date, name, 
                     energy, last_energy_update, streak, staked_amount FROM users WHERE user_id=%s""", (uid,))
        res_basic = c.fetchone()
        if not res_basic: return JSONResponse(status_code=404, content={})
        # On complète manuellement les colonnes manquantes pour le JS
        r = list(res_basic) + ["", ""] # Ajoute missions vide et wallet vide

    now = int(time.time())
    last_upd = r[7] if r[7] else now
    current_e = min(MAX_ENERGY, (r[6] or 0) + ((now - last_upd) // 60) * REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    today = datetime.date.today().isoformat()
    
    # Top 8
    c.execute("SELECT name, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) as total FROM users ORDER BY total DESC LIMIT 8")
    top = [{"n": x[0], "p": round(x[1], 2), "b": get_badge(x[1])} for x in c.fetchall()]
    
    c.close(); conn.close()

    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[5],
        "energy": int(current_e), "max_energy": MAX_ENERGY, "badge": get_badge(score, r[8] or 0),
        "top": top, "jackpot": 0, # Calcul simplifié pour éviter erreur
        "machine_load": random.randint(88, 99), "price_wpt": 0.00045,
        "multiplier": round(1.0 + ((r[9] or 0) / 100) * 0.1 + (score / 1000), 2),
        "can_claim": (r[4] != today), "streak": r[8] or 0, "staked": r[9] or 0,
        "missions": r[10].split(",") if r[10] else [],
        "wallet": r[11] if len(r) > 11 else ""
    }


@app.post("/api/wallet")
async def save_wallet(request: Request):
    data = await request.json(); uid, addr = data.get("user_id"), data.get("address")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET wallet_address = %s WHERE user_id = %s", (addr, uid))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

# [GARDER ICI : mine_api, daily_api, stake_api, mission_api des versions précédentes...]
@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, staked_amount, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    now = int(time.time()); current_e = min(MAX_ENERGY, (res[0] or 0) + ((now - (res[1] or now)) // 60) * REGEN_RATE)
    if current_e >= 1:
        mult = 1.0 + ((res[2] or 0) / 100) * 0.1 + ((res[3] or 0) / 1000)
        gain = 0.05 * mult
        c.execute(f"UPDATE users SET p_{t} = COALESCE(p_{t},0) + %s, energy = %s, last_energy_update = %s WHERE user_id = %s", (gain, current_e - 1, now, uid))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"ok": False})

@app.post("/api/mission")
async def mission_api(request: Request):
    data = await request.json(); uid, mid = data.get("user_id"), data.get("mission_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT missions_done FROM users WHERE user_id=%s", (uid,))
    res = c.fetchone()
    done = res[0].split(",") if res[0] else []
    if mid not in done:
        done.append(mid)
        c.execute("UPDATE users SET p_genesis=COALESCE(p_genesis,0)+20, missions_done=%s WHERE user_id=%s", (",".join(done), uid))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"ok": False})

@app.post("/api/daily")
async def daily_api(request: Request):
    data = await request.json(); uid = data.get("user_id"); today = datetime.date.today()
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT last_streak_date, streak FROM users WHERE user_id = %s", (uid,))
    r = c.fetchone()
    if r[0] != today.isoformat():
        new_s = (r[1]+1) if r[0] == (today - datetime.timedelta(days=1)).isoformat() else 1
        c.execute("UPDATE users SET p_genesis=COALESCE(p_genesis,0)+5, streak=%s, last_streak_date=%s WHERE user_id=%s", (new_s, today.isoformat(), uid))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"ok": False})

@app.post("/api/stake")
async def stake_api(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users WHERE user_id = %s", (uid,))
    total = c.fetchone()[0] or 0
    if total >= 100:
        c.execute("UPDATE users SET p_genesis=p_genesis-34, p_unity=p_unity-33, p_veo=p_veo-33, staked_amount=COALESCE(staked_amount,0)+100 WHERE user_id=%s", (uid,))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    return JSONResponse(status_code=400, content={"ok": False})

# --- WEB UI ---
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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --text: #8E8E93; --green: #34C759; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        .header-ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px; font-size: 10px; display: flex; justify-content: space-between; border-bottom: 1px solid #333; }
        .machine-status { font-size: 9px; color: var(--text); margin-bottom: 12px; display: flex; justify-content: space-between; background: #111; padding: 8px; border-radius: 10px; border: 1px solid #222; align-items: center; }
        .status-led { height: 7px; width: 7px; background: var(--green); border-radius: 50%; display: inline-block; box-shadow: 0 0 8px var(--green); animation: pulse 1.5s infinite; margin-right:5px; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2c2c2e; gap: 10px; }
        .profile-info { display: flex; align-items: center; gap: 8px; flex: 1; overflow: hidden; }
        .badge-tag { font-size: 9px; padding: 2px 6px; border-radius: 6px; background: #222; color: var(--gold); border: 1px solid #333; }
        .balance { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; }
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; position: relative; border: 1px solid #333; }
        .energy-fill { background: linear-gradient(90deg, #FFD700, #FFA500); height: 100%; width: 0%; transition: width 0.5s ease; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 11px; }
        .btn:disabled { opacity: 0.2; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 999; }
        .nav-item { font-size: 20px; opacity: 0.4; cursor: pointer; } .nav-item.active { opacity: 1; color: var(--gold); }
        input { background: #111; border: 1px solid #333; color: #fff; padding: 12px; border-radius: 10px; width: 100%; box-sizing: border-box; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="header-ticker"><span>$WPT: $<span id="m-price">0.00045</span></span><span style="color:var(--gold)">JACKPOT: <span id="jack-val">0</span> OWPC</span></div>
    <div class="machine-status"><span><span class="status-led"></span> NODE: ONLINE</span><span>LOAD: <span id="m-load">0</span>%</span></div>
    
    <div class="profile-bar">
        <div class="profile-info"><div id="u-name" style="font-weight:700; font-size:13px;">...</div><div id="u-badge" class="badge-tag">...</div></div>
        <button id="daily-btn" class="btn" style="display:none; background:var(--gold)" onclick="claimDaily()">🎁 GIFT</button>
        <div id="u-ref" style="font-weight:bold; font-size:11px; color:var(--gold);">0 REFS</div>
    </div>

    <div id="p-mine">
        <div class="balance">
            <small style="color:var(--text)">TOTAL ASSETS</small><h1 id="tot" style="font-size:45px; margin:8px 0;">0.00</h1>
            <div id="u-mult" style="font-size:10px; color:var(--green)">⚡ Multiplier: x1.0</div>
            <div class="energy-bar"><div id="e-bar" class="energy-fill"></div></div>
            <div id="e-text" style="font-size:11px; color:var(--gold);">⚡ 0 / 100</div>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn m-btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn m-btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small style="color:#A259FF">VEO AI</small><div id="vv">0.00</div></div><button class="btn m-btn" onclick="mine('veo')" style="background:#A259FF; color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">$WPT PILLARS</h3>
        <div class="card"><b>World Peace Token</b><button class="btn" onclick="window.open('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">CLAIM</button></div>
        <button class="btn" style="width:100%; margin-top:15px; background:var(--blue); color:#FFF; padding:15px;" onclick="share()">🚀 INVITE FRIENDS</button>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div id="p-wallet" style="display:none">
        <h3 style="color:var(--gold)">WALLET CONNECT</h3>
        <div class="card" style="flex-direction:column; align-items:flex-start;">
            <small style="color:var(--text)">TON Wallet Address</small>
            <input type="text" id="w-addr" placeholder="UQC123...456">
            <button class="btn" style="width:100%; background:var(--gold)" onclick="saveWallet()">SAVE ADDRESS</button>
        </div>
        <div class="card" style="margin-top:20px;">
            <div><b>Withdrawals</b><br><small>Coming soon when TGE starts</small></div>
            <button class="btn" disabled>CLAIM</button>
        </div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('wallet')" id="n-wallet" class="nav-item">💎</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; tg.expand(); const uid = tg.initDataUnsafe.user?.id || 0;
        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}`); const d = await r.json();
                if(!d.name) return;
                document.getElementById('u-name').innerText = d.name;
                document.getElementById('u-badge').innerText = d.badge;
                document.getElementById('u-ref').innerText = d.rc + " REFS";
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = (d.g+d.u+d.v).toFixed(2);
                document.getElementById('jack-val').innerText = d.jackpot;
                document.getElementById('u-mult').innerText = `⚡ Multiplier: x${d.multiplier}`;
                document.getElementById('e-bar').style.width = (d.energy/d.max_energy*100)+"%";
                document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
                document.getElementById('daily-btn').style.display = d.can_claim ? 'block' : 'none';
                if(d.wallet && !document.getElementById('w-addr').value) document.getElementById('w-addr').value = d.wallet;
                
                let r_html = ""; d.top.forEach((u, i) => { r_html += `<div class="card"><div>${i+1}. ${u.n}<br><small style="color:var(--gold)">${u.b}</small></div><b>${u.p}</b></div>`; });
                document.getElementById('rank-list').innerHTML = r_html;
            } catch(e) {}
        }
        async function saveWallet() {
            const addr = document.getElementById('w-addr').value;
            if(addr.length < 10) return alert("Invalid address");
            const res = await fetch('/api/wallet', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, address:addr})});
            if(res.ok) { tg.HapticFeedback.notificationOccurred('success'); alert("Wallet Linked!"); }
        }
        async function mine(t) {
            tg.HapticFeedback.impactOccurred('light');
            const res = await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) refresh();
        }
        function show(p) {
            ['mine', 'pillars', 'leader', 'wallet'].forEach(id => {
                document.getElementById('p-'+id).style.display = (id===p?'block':'none');
                document.getElementById('n-'+id).classList.toggle('active', id===p);
            });
        }
        refresh(); setInterval(refresh, 5000);
    </script>
</body>
</html>
"""

async def main():
    global bot_app
    init_db(); bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize(); await bot_app.start()
    await bot_app.bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")).serve()

if __name__ == "__main__": asyncio.run(main())
