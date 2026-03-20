import os, asyncio, uvicorn, logging, time, random, datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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
        c = conn.cursor()
        # Ajout des colonnes si elles manquent pour éviter l'Erreur 500
        cols = [
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"),
            ("streak", "INTEGER DEFAULT 0"),
            ("last_streak_date", "TEXT"),
            ("ref_count", "INTEGER DEFAULT 0")
        ]
        for col, dtype in cols:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except: pass # Déjà existant
        conn.commit(); c.close(); conn.close()

patch_db()

# --- BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    if update.effective_chat.type in ['group', 'supergroup']: return 

    # Logique de parrainage (Vérification si nouveau user)
    ref_id = None
    if context.args and context.args[0].isdigit():
        ref_id = int(context.args[0])
        if ref_id == uid: ref_id = None # Pas d'auto-parrainage

    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
        if not c.fetchone():
            c.execute("""INSERT INTO users (user_id, name, referred_by, energy, last_energy_update, staked_amount, streak) 
                         VALUES (%s, %s, %s, %s, %s, 0, 0)""", 
                      (uid, name, ref_id, MAX_ENERGY, int(time.time())))
            # Récompense pour le parrain
            if ref_id:
                c.execute("UPDATE users SET p_unity = p_unity + 10.0, ref_count = ref_count + 1 WHERE user_id = %s", (ref_id,))
        conn.commit(); c.close(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"✨ Welcome {name}!\nNode DePIN Synchronized.", reply_markup=kb)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg = " ".join(context.args)
    if not msg: return
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT user_id FROM users"); users = c.fetchall(); c.close(); conn.close()
    for u in users:
        try: await context.bot.send_message(chat_id=u[0], text=msg); await asyncio.sleep(0.05)
        except: continue

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_streak_date, name, energy, last_energy_update, streak, staked_amount FROM users WHERE user_id=%s", (uid,))
        r = c.fetchone()
        if not r: return JSONResponse(status_code=404, content={})
        
        now = int(time.time())
        current_e = min(MAX_ENERGY, (r[6] or 0) + ((now - (r[7] or now)) // 60) * REGEN_RATE)
        score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
        
        today = datetime.date.today().isoformat()
        can_claim = (r[4] != today)

        c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 5")
        top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
        
        return {
            "g": r[0], "u": r[1], "v": r[2], "rc": r[3] or 0, "name": r[5], "energy": int(current_e), 
            "max_energy": MAX_ENERGY, "top": top, "multiplier": round(1.0 + ((r[9] or 0)/100)*0.1, 2), 
            "staked": r[9] or 0, "streak": r[8] or 0, "can_claim": can_claim
        }
    finally:
        c.close(); conn.close()

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, staked_amount FROM users WHERE user_id = %s", (uid,))
    r = c.fetchone()
    now = int(time.time()); cur_e = min(MAX_ENERGY, r[0] + ((now - r[1]) // 60) * REGEN_RATE)
    if cur_e >= 1:
        gain = 0.05 * (1.0 + (r[2]/100)*0.1)
        c.execute(f"UPDATE users SET p_{t} = p_{t} + %s, energy = %s, last_energy_update = %s WHERE user_id = %s", (gain, cur_e - 1, now, uid))
        conn.commit(); c.close(); conn.close()
        return {"ok": True}
    return JSONResponse(status_code=400, content={"ok": False})

@app.post("/api/daily")
async def daily_api(request: Request):
    data = await request.json(); uid = data.get("user_id"); today = datetime.date.today()
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT last_streak_date, streak FROM users WHERE user_id = %s", (uid,))
    r = c.fetchone()
    if r[0] != today.isoformat():
        new_s = (r[1]+1) if r[0] == (today - datetime.timedelta(days=1)).isoformat() else 1
        c.execute("UPDATE users SET p_genesis=p_genesis+5, streak=%s, last_streak_date=%s WHERE user_id=%s", (new_s, today.isoformat(), uid))
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
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(20,20,20,0.9); padding: 15px 25px; border-radius: 40px; display: flex; gap: 25px; border: 1px solid #333; z-index: 1000; }
        .nav-item { font-size: 22px; opacity: 0.3; } .nav-item.active { opacity: 1; color: var(--gold); }
        .energy-bar { background: #222; border-radius: 10px; height: 6px; margin: 15px 0; overflow: hidden; }
        .energy-fill { background: var(--gold); height: 100%; width: 0%; transition: 0.3s; }
    </style>
</head>
<body>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
        <div><b id="u-name">...</b><br><small id="u-ref" style="color:var(--gold)">0 Refs</small></div>
        <button id="daily-btn" class="btn" style="background:var(--gold); display:none" onclick="claimDaily()">🎁 GIFT</button>
    </div>

    <div id="p-mine">
        <div style="text-align:center; padding:20px 0;">
            <small style="color:var(--text)">TOTAL OWPC</small>
            <h1 id="tot" style="font-size:48px; margin:10px 0;">0.00</h1>
            <div class="energy-bar"><div id="e-bar" class="energy-fill"></div></div>
            <small id="e-text" style="color:var(--gold)">⚡ 0 / 100</small>
        </div>
        <div class="card"><div><small>GENESIS</small><div id="gv">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div><small>UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small>VEO AI</small><div id="vv">0.00</div></div><button class="btn" onclick="mine('veo')">COMPUTE</button></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="color:var(--gold)">$WPT PILLARS</h3>
        <p style="font-size:12px; color:var(--text)">Claim your assets on Blum Memepad</p>
        <div class="card"><b>World Peace Token</b><button class="btn" onclick="window.open('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">CLAIM</button></div>
        <div class="card"><b>Unity Asset</b><button class="btn" onclick="window.open('https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA')">CLAIM</button></div>
        <div class="card"><b>Veo AI Asset</b><button class="btn" onclick="window.open('https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA')">CLAIM</button></div>
        <button class="btn" style="width:100%; margin-top:10px; background:var(--blue); color:#FFF;" onclick="share()">🚀 INVITE & EARN +10 UNITY</button>
    </div>

    <div id="p-mission" style="display:none">
        <h3 style="color:var(--gold)">STAKING & NODES</h3>
        <div class="card"><div><b>Active Nodes</b><br><small>Streak: <span id="u-streak">0</span> Days</small></div><div id="u-mult" style="color:var(--green)">1.0x</div></div>
        <div class="card"><div><b>Community</b></div><button class="btn" onclick="window.open('https://t.me/OWPC_Co')">JOIN</button></div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">💎</div>
        <div onclick="show('mission')" id="n-mission" class="nav-item">⚙️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        async function refresh() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('u-name').innerText = d.name;
            document.getElementById('u-ref').innerText = d.rc + " Refs";
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('tot').innerText = (d.g+d.u+d.v).toFixed(2);
            document.getElementById('u-mult').innerText = d.multiplier + "x";
            document.getElementById('u-streak').innerText = d.streak;
            document.getElementById('e-bar').style.width = (d.energy/d.max_energy*100) + "%";
            document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
            document.getElementById('daily-btn').style.display = d.can_claim ? 'block' : 'none';
        }
        async function mine(t) {
            const res = await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('medium'); refresh(); }
        }
        async function claimDaily() {
            const res = await fetch('/api/daily', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            if(res.ok) { confetti(); refresh(); }
        }
        function share() { tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/owpcsbot?start=${uid}&text=Join my DePIN Node and earn OWPC!`); }
        function show(p) {
            ['mine', 'pillars', 'mission'].forEach(id => {
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
    init_db()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize(); await bot_app.start()
    await bot_app.bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")).serve()

if __name__ == "__main__":
    asyncio.run(main())
