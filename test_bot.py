import os, asyncio, uvicorn, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from data_conx import init_db, get_db_conn

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")

logging.basicConfig(level=logging.INFO)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bot_app = None 

# --- BOT FUNCTIONS (AVEC PARRAINAGE) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    # Vérification du parrain (ex: /start 123456)
    referrer_id = None
    if context.args:
        try:
            arg = int(context.args[0])
            if arg != uid: referrer_id = arg
        except: pass

    conn = get_db_conn()
    if conn:
        try:
            c = conn.cursor()
            # 1. Vérifier si l'utilisateur existe déjà
            c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
            exists = c.fetchone()
            
            if not exists:
                # 2. Créer l'utilisateur avec son parrain s'il y en a un
                c.execute("INSERT INTO users (user_id, name, referred_by) VALUES (%s, %s, %s)", (uid, name, referrer_id))
                
                # 3. Récompenser le parrain (+1.0 UNITY)
                if referrer_id:
                    c.execute("UPDATE users SET p_unity = p_unity + 1.0, ref_count = ref_count + 1 WHERE user_id = %s", (referrer_id,))
                    c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (%s, 'REFERRAL_REWARD', 1.0, %s)", (referrer_id, int(time.time())))
            
            conn.commit()
            c.close(); conn.close()
        except Exception as e:
            logging.error(f"Erreur SQL Start: {e}")
    
    url = WEBAPP_URL.rstrip('/')
    final_url = url if url.startswith("http") else f"https://{url}"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=final_url))],
        [InlineKeyboardButton("📢 Share Referral Link", switch_inline_query=f"\nJoin me on OWPC HUB and earn! https://t.me/{(await context.bot.get_me()).username}?start={uid}")]
    ])
    await update.message.reply_text(f"Welcome to the Ecosystem, {name}!", reply_markup=kb)

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
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "history": history, "clicks": r[5], "name": r[6], "top": top, "uid": uid}

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

# --- WEB UI (RETOUR DE L'HISTORIQUE + NOUVEAUX ONGLETS) ---
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
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 20px; border: 1px solid #2c2c2e; }
        .avatar { width: 35px; height: 35px; background: var(--blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; }
        .balance { text-align: center; border: 1px solid #222; padding: 20px; border-radius: 25px; background: linear-gradient(145deg, #050505, #111); margin-bottom: 15px; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1C1C1E; }
        .btn { background: #FFF; color: #000; border: none; padding: 8px 15px; border-radius: 10px; font-weight: 700; cursor: pointer; }
        .pill-link { background: #1C1C1E; color: #FFF; text-decoration: none; padding: 10px 15px; border-radius: 10px; font-size: 12px; font-weight: 700; border: 1px solid #333; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.9); backdrop-filter: blur(15px); padding: 10px 25px; border-radius: 35px; display: flex; gap: 30px; border: 1px solid #333; z-index: 1000; }
        .nav-item { font-size: 20px; opacity: 0.3; cursor: pointer; }
        .nav-item.active { opacity: 1; }
        .section-title { font-size: 11px; font-weight: 700; color: var(--text); margin: 20px 0 8px 5px; text-transform: uppercase; }
        .history-item { display: flex; justify-content: space-between; font-size: 12px; color: var(--text); padding: 8px 0; border-bottom: 1px solid #1c1c1e; }
    </style>
</head>
<body>
    <div class="profile-bar">
        <div style="display:flex; align-items:center; gap:10px;"><div class="avatar" id="u-avatar">?</div><div id="u-name" style="font-weight:700">Loading...</div></div>
        <div style="text-align:right"><small style="color:var(--text); font-size:9px">REFERRALS</small><div id="u-ref" style="color:var(--gold); font-weight:bold">0</div></div>
    </div>

    <div id="p-mine">
        <div class="balance"><span>TOTAL ASSETS</span><h1 id="tot" style="font-size:38px; margin:5px 0">0.00</h1></div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv" style="font-size:16px; font-weight:700">0.00</div></div><button class="btn" onclick="mine('genesis')">CLAIM</button></div>
        <div class="card"><div><small style="color:#FFF">UNITY</small><div id="uv" style="font-size:16px; font-weight:700">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small style="color:var(--blue)">VEO AI</small><div id="vv" style="font-size:16px; font-weight:700">0.00</div></div><button class="btn" onclick="mine('veo')" style="background:var(--blue);color:#FFF">COMPUTE</button></div>
        
        <div class="section-title">Recent Activity</div>
        <div id="history-list" style="background: var(--card); padding: 10px 15px; border-radius: 18px; border: 1px solid #1C1C1E;"></div>
    </div>

    <div id="p-pillars" style="display:none">
        <div class="section-title">Ecosystem Pillars (Blum)</div>
        <div class="card"><div><b>Genesis Unit</b><br><small>Open Blum App</small></div><a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" class="pill-link">OPEN ↗</a></div>
        <div class="card"><div><b>Unity Unit</b><br><small>Open Blum App</small></div><a href="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA" class="pill-link">OPEN ↗</a></div>
        <div class="card"><div><b>Veo AI Unit</b><br><small>Open Blum App</small></div><a href="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA" class="pill-link">OPEN ↗</a></div>
        
        <div class="section-title">Your Referral Link</div>
        <div class="card" style="flex-direction:column; align-items:flex-start; gap:10px;">
            <small id="ref-link" style="color:var(--blue); word-break:break-all; font-size:11px;">Generate link...</small>
            <button class="btn" style="width:100%" onclick="copyRef()">Copy Link</button>
        </div>
    </div>

    <div id="p-leader" style="display:none">
        <div class="section-title">Global Top Players</div>
        <div id="rank-list"></div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">💎</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;
        const apiBase = window.location.origin;

        async function refresh() {
            if(!uid) return;
            try {
                const r = await fetch(`${apiBase}/api/user/${uid}`);
                if(!r.ok) return;
                const d = await r.json();
                
                document.getElementById('u-name').innerText = d.name;
                document.getElementById('u-avatar').innerText = d.name[0].toUpperCase();
                document.getElementById('u-ref').innerText = d.rc;
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = (d.g + d.u + d.v).toFixed(2);
                
                // Ton bot username pour le lien de parrainage
                const botUsername = "TON_BOT_USERNAME"; // <-- METS TON NOM DE BOT ICI (ex: owpc_hub_bot)
                document.getElementById('ref-link').innerText = `https://t.me/${botUsername}?start=${uid}`;

                // Remplissage de l'historique
                let h_html = "";
                d.history.forEach(h => {
                    let color = h.t.includes('REFERRAL') ? 'var(--gold)' : 'var(--text)';
                    h_html += `<div class="history-item"><span style="color:${color}">${h.t}</span><b>+${h.a}</b></div>`;
                });
                document.getElementById('history-list').innerHTML = h_html || "<small>No activity yet</small>";

                let r_html = "";
                d.top.forEach((u, i) => { r_html += `<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
                document.getElementById('rank-list').innerHTML = r_html;
            } catch(e) { console.error("Refresh failed", e); }
        }

        async function mine(t) {
            tg.HapticFeedback.impactOccurred('medium');
            await fetch(`${apiBase}/api/mine`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            refresh();
        }

        function show(p) {
            ['mine', 'pillars', 'leader'].forEach(id => {
                document.getElementById('p-'+id).style.display = (id===p ? 'block' : 'none');
                document.getElementById('n-'+id).classList.toggle('active', id===p);
            });
        }

        function copyRef() {
            const link = document.getElementById('ref-link').innerText;
            navigator.clipboard.writeText(link);
            tg.showAlert("Referral link copied!");
        }

        refresh();
        // Rafraîchir toutes les 10 secondes pour voir les points de parrainage tomber
        setInterval(refresh, 10000);
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
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
