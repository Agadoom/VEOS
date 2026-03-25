import asyncio, uvicorn, time, random
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import config, database, missions

# --- INITIALISATION ---
database.init_db_structure()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- HELPERS ---
def get_network_stats():
    try:
        conn = database.get_db_conn(); c = conn.cursor()
        now = int(time.time())
        c.execute("SELECT COUNT(*) FROM users WHERE last_energy_update > %s", (now - 300,))
        online = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users")
        total = c.fetchone()[0]
        c.close(); conn.close()
        return (online if online > 0 else 1), total
    except: return 1, 1

# --- API ROUTES ---

@app.get("/api/user/{uid}")
async def api_get_user(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    last_update = r[6] if r[6] is not None else now
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_update) / 60) * config.REGEN_RATE)
    
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, _, _ = missions.get_badge_info(score)
    
    online_c, total_u = get_network_stats()
    top_raw = database.get_leaderboard()
    top = [{"n": x[0], "p": round(x[1], 2), "b": missions.get_badge_info(x[1])[0]} for x in top_raw]

    return {
        "uid": uid, "name": r[4], "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0,
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "score": round(score, 2),
        "badge": badge, "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "online": online_c, "total_users": total_u, "top": top
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = database.get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT energy, last_energy_update, last_click_time FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        now_ms = int(time.time()*1000); now_s = now_ms//1000
        if res and (now_ms - (res[2] or 0)) >= 85: # Protection 85ms
            cur_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now_s - (res[1] or now_s))/60)*config.REGEN_RATE)
            if cur_e >= 1:
                c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05, energy=%s, last_energy_update=%s, last_click_time=%s WHERE user_id=%s", (cur_e-1, now_s, now_ms, uid))
                conn.commit(); return {"ok": True}
        return JSONResponse(status_code=400)
    finally: c.close(); conn.close()

# --- LAUNCHER API (Dev Special Start) ---

@app.get("/api/launcher/list")
async def api_list_tokens():
    # Simulation de tokens pour l'interface
    return [
        {"name": "Pepe Gold", "sym": "PEPEG", "price": "0.00042", "mcap": "4.2K", "img": "🐸"},
        {"name": "Dog v3", "sym": "DOG3", "price": "0.00015", "mcap": "1.5K", "img": "🐶"}
    ]

@app.post("/api/launcher/deploy")
async def api_deploy_token(request: Request):
    data = await request.json()
    # Logique : Coût 1000 WPT (Score total) pour créer un token
    return {"ok": True, "msg": "Token queued for deployment"}

# --- WEB UI ---

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --green: #34C759; --purple: #A259FF; --text: #8E8E8E; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        
        /* Layout */
        .ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; font-size: 10px; font-weight: bold; }
        .t-wrap { display: inline-block; animation: scroll 25s linear infinite; }
        @keyframes scroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        .balance-card { text-align: center; padding: 30px 20px; border-radius: 25px; background: radial-gradient(circle at top, #1c1c1e, #000); border: 1px solid #222; margin-bottom: 15px; }
        .energy-bar { background: #222; height: 8px; border-radius: 4px; margin: 15px 0; overflow: hidden; }
        .energy-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.4s; }

        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 11px; }

        /* Navigation */
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 1000; }
        .n-i { font-size: 20px; opacity: 0.3; transition: 0.3s; cursor: pointer; }
        .n-i.active { opacity: 1; color: var(--gold); transform: scale(1.2); }

        /* Launcher Styles */
        .l-input { background: #000; border: 1px solid #333; color: #fff; padding: 10px; border-radius: 10px; width: 100%; margin-bottom: 10px; box-sizing: border-box; }
    </style>
</head>
<body>
    <div class="ticker"><div class="t-wrap">
        <span style="margin-right:40px; color:var(--gold)">🏆 JACKPOT: <span id="jk-v">0</span> WPT</span>
        <span style="color:var(--green)">● NETWORK ONLINE: <span id="on-v">0</span> USERS</span>
    </div></div>

    <div id="p-mine">
        <div class="balance-card">
            <div id="u-badge" style="font-size:10px; color:var(--text); margin-bottom:5px;">...</div>
            <h1 id="tot" style="font-size:45px; margin:0;">0.00</h1>
            <div class="energy-bar"><div id="e-f" class="energy-fill"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--gold)">
                <span>ENERGY</span><span id="e-t">0 / 100</span>
            </div>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small style="color:var(--purple)">VEO AI</small><div id="vv">0.00</div></div><button class="btn" onclick="mine('veo')" style="background:var(--purple); color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-launcher" style="display:none">
        <h3 style="text-align:center; color:var(--gold);">🚀 TOKEN LAUNCHER</h3>
        <div class="card" style="flex-direction:column; align-items:stretch;">
            <input type="text" id="tk-name" class="l-input" placeholder="Token Name (ex: Pepe)">
            <input type="text" id="tk-sym" class="l-input" placeholder="Symbol (ex: PEPE)">
            <button class="btn" style="background:var(--gold); width:100%;" onclick="deploy()">DEPLOY NEW TOKEN (1000 WPT)</button>
        </div>
        <h4 style="margin-left:5px;">LIVE TOKENS</h4>
        <div id="token-list"></div>
    </div>

    <div id="p-rank" style="display:none">
        <h3 style="text-align:center;">🏆 WORLD RANKING</h3>
        <div id="rank-list"></div>
    </div>

    <nav class="nav">
        <div onclick="show('mine')" id="n-mine" class="n-i active">🏠</div>
        <div onclick="show('launcher')" id="n-launcher" class="n-i">🚀</div>
        <div onclick="show('rank')" id="n-rank" class="n-i">🏆</div>
    </nav>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let lastClick = 0;

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}?t=${Date.now()}`);
                const d = await r.json();
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('u-badge').innerText = d.badge.toUpperCase();
                document.getElementById('jk-v').innerText = d.jackpot.toLocaleString();
                document.getElementById('on-v').innerText = d.online;
                document.getElementById('e-f').style.width = (d.energy/d.max_energy*100) + "%";
                document.getElementById('e-t').innerText = `${d.energy} / ${d.max_energy}`;

                // Ranking
                let rl = ""; d.top.forEach((u, i) => { 
                    rl += `<div class="card"><span>${i+1}. ${u.n} <small style="color:#555">(${u.b})</small></span><b>${u.p}</b></div>`; 
                });
                document.getElementById('rank-list').innerHTML = rl;
            } catch(e) {}
        }

        async function loadLauncher() {
    const r = await fetch('/api/launcher/list');
    const tokens = await r.json();
    let html = "";
    tokens.forEach(t => {
        html += `
        <div class="card" style="display:block;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style="display:flex; align-items:center;">
                    <div style="font-size:24px; margin-right:12px; background:#222; padding:5px; border-radius:10px;">🚀</div>
                    <div><b>${t.name}</b><br><small style="color:var(--text)">${t.sym}</small></div>
                </div>
                <div style="text-align:right;">
                    <b style="color:var(--green)">${t.price} WPT</b><br>
                    <small style="color:var(--text)">MCAP: ${t.mcap}$</small>
                </div>
            </div>
            <div style="display:flex; gap:10px; margin-top:10px;">
                <button class="btn" style="flex:1; background:var(--green); color:#fff;" onclick="trade('${t.id}', 10)">BUY 10</button>
                <button class="btn" style="flex:1; background:#333; color:#fff;" onclick="trade('${t.id}', -10)">SELL</button>
            </div>
        </div>`;
    });
    document.getElementById('token-list').innerHTML = html || "<center>No tokens yet</center>";
}

async function trade(tid, amt) {
    // Appel API pour acheter/vendre (à créer dans FastAPI)
    tg.showConfirm(`Confirm trade for ${amt} WPT?`, (ok) => {
        if(ok) tg.showAlert("Trade executed! (Bonding curve updated)");
    });
}


        async function mine(t) {
            const now = Date.now(); if(now - lastClick < 85) return; lastClick = now;
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('light'); refresh(); }
        }

        async function deploy() {
            const n = document.getElementById('tk-name').value;
            const s = document.getElementById('tk-sym').value;
            if(!n || !s) return tg.showAlert("Fill all fields");
            const res = await fetch('/api/launcher/deploy', {method:'POST', body:JSON.stringify({user_id:uid, name:n, symbol:s})});
            if(res.ok) { tg.showAlert("Deployment request sent!"); loadLauncher(); }
        }

        function show(p) {
            ['mine','launcher','rank'].forEach(id => {
                document.getElementById('p-'+id).style.display = (id===p?'block':'none');
                document.getElementById('n-'+id).classList.toggle('active', id===p);
            });
            if(p==='launcher') loadLauncher();
            refresh();
        }

        tg.expand(); refresh(); setInterval(refresh, 8000);
    </script>
</body>
</html>
"""

# --- BOT LAUNCH ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    await missions.register_user(uid, name, None)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome {name} to the WPT HUB!", reply_markup=kb)

async def main():
    bot = ApplicationBuilder().token(config.TOKEN).build()
    bot.add_handler(CommandHandler("start", start_cmd))
    await bot.initialize(); await bot.start(); await bot.updater.start_polling()
    conf = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    await uvicorn.Server(conf).serve()

if __name__ == "__main__":
    asyncio.run(main())
