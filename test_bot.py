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
RAW_URL = os.getenv("WEBAPP_URL", "")
WEBAPP_URL = RAW_URL if RAW_URL.startswith("http") else f"https://{RAW_URL}"

logging.basicConfig(level=logging.INFO)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

bot_app = None 

# --- BOT FUNCTIONS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    referrer_id = None
    if context.args:
        try:
            arg = int(context.args[0])
            referrer_id = arg if arg != uid else None
        except: pass

    conn = get_db_conn()
    if conn:
        try:
            c = conn.cursor()
            c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
            if not c.fetchone():
                # Création du nouvel utilisateur
                c.execute("INSERT INTO users (user_id, name, referred_by) VALUES (%s, %s, %s)", (uid, name, referrer_id))
                
                if referrer_id:
                    # 1. Récompense de base (+1.0 UNITY)
                    c.execute("UPDATE users SET p_unity = p_unity + 1.0, ref_count = ref_count + 1 WHERE user_id = %s RETURNING ref_count", (referrer_id,))
                    new_ref_count = c.fetchone()[0]
                    c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (%s, 'REFERRAL_REWARD', 1.0, %s)", (referrer_id, int(time.time())))
                    
                    # 2. Bonus par Étapes (Milestones)
                    if new_ref_count == 5:
                        c.execute("UPDATE users SET p_genesis = p_genesis + 5.0 WHERE user_id = %s", (referrer_id,))
                        c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (%s, 'BONUS_5_REFS', 5.0, %s)", (referrer_id, int(time.time())))
                    elif new_ref_count == 10:
                        c.execute("UPDATE users SET p_veo = p_veo + 10.0 WHERE user_id = %s", (referrer_id,))
                        c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (%s, 'BONUS_10_REFS', 10.0, %s)", (referrer_id, int(time.time())))
            
            conn.commit(); c.close(); conn.close()
        except Exception as e: logging.error(f"SQL Start Error: {e}")
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📢 Invite Friends", switch_inline_query=f"\nJoin me on OWPC HUB! 🚀 https://t.me/owpcsbot?start={uid}")]
    ])
    await update.message.reply_text(f"Welcome {name}!", reply_markup=kb)

# --- API DONATE (STARS) ---
@app.post("/api/donate")
async def donate_stars(request: Request):
    data = await request.json()
    try:
        link = await bot_app.bot.create_invoice_link(
            title="Support OWPC HUB", description="Donate 50 Stars", payload="donate_50",
            provider_token="", currency="XTR", prices=[LabeledPrice("Support", 50)]
        )
        return {"ok": True, "link": link}
    except Exception as e: return {"ok": False, "error": str(e)}

# --- API USER DATA ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn()
    if not conn: return JSONResponse(status_code=500, content={"error": "DB"})
    c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_daily, total_clicks, name FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={"error": "404"})
    
    c.execute("SELECT token, amount, timestamp FROM logs WHERE user_id=%s ORDER BY id DESC LIMIT 5", (uid,))
    history = [{"t": x[0], "a": x[1], "ts": x[2]} for x in c.fetchall()]
    
    c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 10")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    
    c.close(); conn.close()
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "history": history, "name": r[6], "top": top}

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    col = {"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}.get(t)
    conn = get_db_conn()
    if conn and col:
        c = conn.cursor()
        c.execute(f"UPDATE users SET {col} = {col} + 0.05, total_clicks = total_clicks + 1 WHERE user_id = %s", (uid,))
        c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (%s, %s, 0.05, %s)", (uid, t.upper(), int(time.time())))
        conn.commit(); c.close(); conn.close()
        return {"ok": True}
    return {"ok": False}

# --- WEB UI (PROGRESSION PARRAINAGE) ---
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
        :root { --bg: #000; --card: #111; --blue: #007AFF; --green: #34C759; --gold: #FFD700; --text: #8E8E93; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x:hidden; }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 20px; border: 1px solid #2c2c2e; }
        .avatar { width: 35px; height: 35px; background: var(--blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; }
        .balance { text-align: center; border: 1px solid #222; padding: 20px; border-radius: 25px; background: linear-gradient(145deg, #050505, #111); margin-bottom: 15px; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1C1C1E; }
        .btn { background: #FFF; color: #000; border: none; padding: 8px 15px; border-radius: 10px; font-weight: 700; cursor: pointer; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.9); backdrop-filter: blur(15px); padding: 10px 25px; border-radius: 35px; display: flex; gap: 30px; border: 1px solid #333; z-index: 1000; }
        .nav-item { font-size: 20px; opacity: 0.3; cursor: pointer; }
        .nav-item.active { opacity: 1; }
        .section-title { font-size: 11px; font-weight: 700; color: var(--text); margin: 20px 0 8px 5px; text-transform: uppercase; }
        .history-item { display: flex; justify-content: space-between; font-size: 12px; color: var(--text); padding: 8px 0; border-bottom: 1px solid #1c1c1e; }
        .progress-container { width: 100%; background: #222; border-radius: 10px; height: 8px; margin: 10px 0; }
        .progress-bar { background: var(--blue); height: 100%; border-radius: 10px; transition: width 0.5s; }
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
        <div id="history-list"></div>
    </div>

    <div id="p-pillars" style="display:none">
        <div class="section-title">Milestones Progression</div>
        <div class="card" style="display:block">
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <small id="milestone-text">Next Reward: 5 Friends</small>
                <small id="milestone-count">0/5</small>
            </div>
            <div class="progress-container"><div id="p-bar" class="progress-bar" style="width: 0%"></div></div>
        </div>

        <div class="section-title">Your Referral Link</div>
        <div class="card" style="flex-direction:column; align-items:flex-start; gap:10px;">
            <small id="ref-link" style="color:var(--blue); font-size:11px;">https://t.me/owpcsbot?start=...</small>
            <button class="btn" style="width:100%" onclick="copyRef()">Copy Link</button>
        </div>

        <div class="section-title">Support Project</div>
        <div class="card">
            <div><b>Donate Stars</b></div>
            <button class="btn" style="background:var(--gold)" onclick="donate()">⭐️ 50</button>
        </div>
    </div>

    <div id="p-leader" style="display:none"><div class="section-title">Top Players</div><div id="rank-list"></div></div>

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
                const d = await r.json();
                document.getElementById('u-name').innerText = d.name;
                document.getElementById('u-avatar').innerText = d.name[0].toUpperCase();
                document.getElementById('u-ref').innerText = d.rc;
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = (d.g + d.u + d.v).toFixed(2);
                document.getElementById('ref-link').innerText = `https://t.me/owpcsbot?start=${uid}`;

                // Progression Milestones
                let next = d.rc < 5 ? 5 : 10;
                document.getElementById('milestone-text').innerText = `Next Reward: ${next} Friends`;
                document.getElementById('milestone-count').innerText = `${d.rc}/${next}`;
                document.getElementById('p-bar').style.width = Math.min((d.rc / next) * 100, 100) + "%";

                let h_html = "";
                d.history.forEach(h => { h_html += `<div class="history-item"><span>${h.t}</span><b>+${h.a}</b></div>`; });
                document.getElementById('history-list').innerHTML = h_html;

                let r_html = "";
                d.top.forEach((u, i) => { r_html += `<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
                document.getElementById('rank-list').innerHTML = r_html;
            } catch(e) { console.error(e); }
        }

        async function mine(t) {
            confetti({ particleCount: 40, spread: 60, origin: { y: 0.8 }, colors: ['#FFD700', '#007AFF'] });
            tg.HapticFeedback.impactOccurred('medium');
            await fetch(`${apiBase}/api/mine`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            refresh();
        }

        async function donate() {
            const r = await fetch(`${apiBase}/api/donate`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            const data = await r.json();
            if(data.ok) tg.openInvoice(data.link, (s) => { if(s=='paid') refresh(); });
        }

        function show(p) {
            ['mine', 'pillars', 'leader'].forEach(id => {
                document.getElementById('p-'+id).style.display = (id===p ? 'block' : 'none');
                document.getElementById('n-'+id).classList.toggle('active', id===p);
            });
        }
        function copyRef() {
            navigator.clipboard.writeText(document.getElementById('ref-link').innerText);
            tg.showAlert("Link copied!");
        }
        refresh();
        setInterval(refresh, 8000);
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
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
