import asyncio, uvicorn, time, random, threading
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import config, database, missions 

database.init_db_structure()
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def get_network_stats():
    try:
        conn = database.get_db_conn(); c = conn.cursor()
        now = int(time.time())
        c.execute("SELECT COUNT(*) FROM users WHERE last_energy_update > %s", (now - 300,))
        online = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users")
        total = c.fetchone()[0]
        c.close(); conn.close()
        return (max(online, 1)), total
    except: return 1, 1

@app.get("/api/user/{uid}")
async def api_get_user(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={})
    now = int(time.time()); last_upd = r[6] if r[6] else now
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, next_goal, badge_color = missions.get_badge_info(score)
    online_c, total_u = get_network_stats()
    return {
        "uid": uid, "name": r[4], "g": round(r[0] or 0, 2), "u": round(r[1] or 0, 2), "v": round(r[2] or 0, 2),
        "energy": int(min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_upd)/60)*config.REGEN_RATE)),
        "max_energy": config.MAX_ENERGY, "score": round(score, 2), "badge": badge, "badge_color": badge_color,
        "next_goal": next_goal, "online": online_c, "total_users": total_u, "staked": r[8] or 0, "streak": r[7] or 0,
        "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "multiplier": round(1.0 + (score/5000), 2),
        "top": [{"n": x[0], "p": round(x[1], 2), "b": missions.get_badge_info(x[1])[0]} for x in database.get_leaderboard()]
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = database.get_db_conn(); c = conn.cursor()
    try:
        now_ms = int(time.time()*1000); now_s = now_ms//1000
        c.execute("SELECT energy, last_click_time FROM users WHERE user_id=%s", (uid,))
        res = c.fetchone()
        if res and (now_ms - (res[1] or 0)) >= 85 and res[0] >= 1:
            c.execute(f"UPDATE users SET p_{t}=p_{t}+0.05, energy=energy-1, last_energy_update=%s, last_click_time=%s WHERE user_id=%s", (now_s, now_ms, uid))
            conn.commit(); return {"ok": True}
        return JSONResponse(status_code=400)
    except: conn.rollback(); return JSONResponse(status_code=500)
    finally: c.close(); conn.close()

@app.get("/api/launcher/list/{sort}")
async def api_list_tokens(sort: str):
    tokens = database.get_tokens_ordered(sort)
    return [{"name": t[0], "symbol": t[1], "logo": t[2], "price": t[3], "holders": t[4], "mcap": round(t[5]*2, 2), "vol": t[6]} for t in tokens]

@app.post("/api/launcher/deploy")
async def api_deploy_token(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = database.get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        if c.fetchone()[0] < 500: return JSONResponse(status_code=400)
        c.execute("UPDATE users SET p_genesis = p_genesis - 500 WHERE user_id = %s", (uid,))
        c.execute("INSERT INTO community_tokens (creator_id, name, symbol, logo, reserve_wpt, created_at) VALUES (%s, %s, %s, %s, 500, %s)", 
                  (uid, data.get("name"), data.get("symbol"), data.get("logo"), int(time.time())))
        conn.commit(); return {"ok": True}
    except: conn.rollback(); return JSONResponse(status_code=500)
    finally: c.close(); conn.close()

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --text: #8E8E8E; --green: #34C759; --purple: #A259FF; --red: #FF3B30; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        .ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; }
        .t-wrap { display: inline-block; animation: scroll 25s linear infinite; }
        @keyframes scroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
        .t-i { display: inline-block; margin-right: 30px; color: var(--gold); font-size: 10px; font-weight: bold; }
        .b-card { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; }
        .e-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; }
        .e-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.3s; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; font-size: 11px; cursor: pointer; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 15px; border: 1px solid #333; z-index: 100; }
        .n-i { font-size: 18px; opacity: 0.3; } .n-i.active { opacity: 1; color: var(--purple); }
        .tabs { display: flex; gap: 10px; margin-bottom: 15px; border-bottom: 1px solid #222; }
        .tab { font-size: 10px; color: #555; padding: 10px 5px; cursor: pointer; }
        .tab.active { color: var(--purple); font-weight: bold; border-bottom: 2px solid var(--purple); }
        .modal { position: fixed; inset: 0; background: rgba(0,0,0,0.95); z-index: 200; display: none; align-items: center; justify-content: center; padding: 20px; flex-direction: column; }
        .input-group { background: #000; padding: 12px; border-radius: 12px; border: 1px solid #333; margin-bottom: 10px; width: 100%; box-sizing: border-box; }
        input { background: transparent; border: none; color: #FFF; width: 100%; outline: none; }
    </style>
</head>
<body>
    <div class="ticker"><div class="t-wrap">
        <span class="t-i">🟢 ONLINE: <span id="on-v">1</span></span>
        <span class="t-i">👥 TOTAL: <span id="tot-v">1</span></span>
        <span class="t-i">🔥 JACKPOT: <span id="jk-v">0</span> WPT</span>
    </div></div>

    <div id="p-mine">
        <div class="b-card">
            <h1 id="tot">0.00</h1>
            <div id="u-m" style="font-size:10px; color:var(--green)">⚡ Multiplier: x1.0</div>
            <div class="e-bar"><div id="e-f" class="e-fill"></div></div>
            <div id="e-t" style="font-size:11px; color:var(--gold);">⚡ 0 / 100</div>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small style="color:var(--purple)">VEO AI</small><div id="vv">0.00</div></div><button class="btn" onclick="mine('veo')" style="background:var(--purple); color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-missions" style="display:none">
        <h3 style="color:var(--gold); text-align:center;">HUB MISSIONS</h3>
        <div class="card"><div><b>Turbo Robot</b><br><small>Stake 100 WPT</small></div><button class="btn" style="background:var(--gold)">STAKE</button></div>
        <div class="card"><b>Daily Bonus</b><button id="db-btn" class="btn" style="background:var(--green); color:#FFF">CLAIM</button></div>
    </div>

    <div id="p-opps" style="display:none">
        <h3 style="color:var(--blue); text-align:center;">ORACLE PREDICT</h3>
        <div class="card" style="flex-direction:column; gap:10px;">
            <div style="font-size:11px;">Genesis Price in 60s?</div>
            <div style="display:flex; gap:10px; width:100%;">
                <button class="btn" style="flex:1; background:var(--green); color:#FFF">UP ↑</button>
                <button class="btn" style="flex:1; background:var(--red); color:#FFF">DOWN ↓</button>
            </div>
        </div>
    </div>

    <div id="p-leader" style="display:none">
        <h3 style="color:var(--gold); text-align:center;">LEADERBOARD</h3>
        <div id="rank-list"></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="color:var(--green); text-align:center;">PILLARS ASSETS</h3>
        <div class="card"><div><b>Genesis Asset</b></div><button class="btn" onclick="tg.openLink('https://t.me/blum')">GO</button></div>
        <div class="card"><div><b>Unity Asset</b></div><button class="btn" onclick="tg.openLink('https://t.me/blum')">GO</button></div>
    </div>

    <div id="p-profile" style="display:none">
        <div style="text-align:center; padding:20px;">
            <div style="font-size:40px;">👤</div>
            <h2 id="pr-n">...</h2><div id="pr-b" style="color:var(--gold); font-weight:bold; font-size:12px;">...</div>
            <div class="xp-b" style="background:#222; height:6px; border-radius:3px; margin:10px 0;"><div id="xp-f" style="background:var(--purple); height:100%; border-radius:3px; width:0%"></div></div>
            <small id="xp-t" style="color:var(--text); font-size:9px;">Next Rank: ...</small>
        </div>
        <div class="card"><span>Power</span><b id="pr-m">x1.0</b></div>
        <div class="card"><span>Streak</span><b id="pr-s">0 Days</b></div>
    </div>

    <div id="p-launcher" style="display:none">
        <button class="btn" style="width:100%; background:var(--purple); color:#FFF; margin-bottom:20px; padding:16px;" onclick="document.getElementById('m-create').style.display='flex'">🚀 LAUNCH YOUR TOKEN</button>
        <div class="tabs">
            <div class="tab active" onclick="switchTab(this, 'new')">NEW</div>
            <div class="tab" onclick="switchTab(this, 'mcap')">MARKET CAP</div>
            <div class="tab" onclick="switchTab(this, 'vol')">BY MISLOCAP</div>
        </div>
        <div id="tk-list"></div>
    </div>

    <div id="m-create" class="modal">
        <div style="background:var(--card); width:100%; padding:20px; border-radius:20px; border:1px solid var(--purple);">
            <h3>Launch Token</h3>
            <div class="input-group"><input type="text" id="tk-name" placeholder="Token Name"></div>
            <div class="input-group"><input type="text" id="tk-sym" placeholder="Symbol"></div>
            <div class="input-group"><input type="text" id="tk-logo" placeholder="Logo URL"></div>
            <button class="btn" style="width:100%; background:var(--green); color:#FFF;" onclick="deploy()">DEPLOY (500 WPT)</button>
            <button class="btn" style="width:100%; background:#222; color:#FFF; margin-top:10px;" onclick="document.getElementById('m-create').style.display='none'">CANCEL</button>
        </div>
    </div>

    <div id="m-trade" class="modal">
        <div style="background:var(--card); width:100%; padding:20px; border-radius:20px;">
            <h3 id="tr-title">Trade</h3>
            <div class="input-group"><input type="number" id="tr-amt" oninput="calcTrade()" placeholder="WPT Amount"></div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:8px; margin-bottom:15px;">
                <button class="btn" style="background:#222; color:#FFF; font-size:10px;" onclick="setAmt(25)">25%</button>
                <button class="btn" style="background:#222; color:#FFF; font-size:10px;" onclick="setAmt(50)">50%</button>
                <button class="btn" style="background:#222; color:#FFF; font-size:10px;" onclick="setAmt(100)">MAX</button>
                <button class="btn" style="background:var(--purple); color:#FFF; font-size:10px;" onclick="document.getElementById('tr-amt').focus()">EDIT</button>
            </div>
            <div id="tr-res" style="background:#000; padding:15px; border-radius:10px; color:var(--green); text-align:center; font-family:monospace;">Receive: 0 tokens</div>
            <button class="btn" style="width:100%; background:var(--green); color:#FFF; margin-top:15px; padding:12px;" onclick="tg.showAlert('Order Sent')">CONFIRM</button>
            <button class="btn" style="width:100%; background:#222; color:#FFF; margin-top:10px;" onclick="document.getElementById('m-trade').style.display='none'">CLOSE</button>
        </div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="n-i active">🏠</div>
        <div onclick="show('opps')" id="n-opps" class="n-i">📈</div>
        <div onclick="show('launcher')" id="n-launcher" class="n-i">🚀</div>
        <div onclick="show('pillars')" id="n-pillars" class="n-i">🏛️</div>
        <div onclick="show('profile')" id="n-profile" class="n-i">👤</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let userBalance = 0; let currentPrice = 0.0001;

        function show(p) {
            ['mine','opps','missions','profile','pillars','leader','launcher'].forEach(id=>{
                if(document.getElementById('p-'+id)) document.getElementById('p-'+id).style.display=(id===p?'block':'none');
                if(document.getElementById('n-'+id)) document.getElementById('n-'+id).classList.toggle('active',id===p);
            });
            if(p==='launcher') loadTokens('new');
        }

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}`); const d = await r.json();
                userBalance = d.score;
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('e-f').style.width = (d.energy / d.max_energy * 100) + "%";
                document.getElementById('e-t').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
                document.getElementById('pr-n').innerText = d.name;
                document.getElementById('pr-b').innerText = d.badge;
                document.getElementById('jk-v').innerText = d.jackpot;
                // Leaderboard update
                let lhtml = ""; d.top.forEach(x => { lhtml += `<div class="card"><div>${x.n} <small>(${x.b})</small></div><b>${x.p}</b></div>`; });
                document.getElementById('rank-list').innerHTML = lhtml;
            } catch(e) {}
        }

        async function mine(t) {
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('light'); refresh(); }
        }

        async function loadTokens(sort) {
            const r = await fetch(`/api/launcher/list/`+sort); const tokens = await r.json();
            let html = "";
            tokens.forEach(t => {
                html += `<div class="card" onclick="openTrade('${t.name}', ${t.price})">
                    <img src="${t.logo}" style="width:35px; height:35px; border-radius:50%; background:#333;">
                    <div style="flex:1; margin-left:10px;"><b>${t.name}</b><br><small>$${t.mcap}</small></div>
                    <div style="text-align:right"><b style="color:var(--green)">${t.price}</b><br><small>VOL: ${t.vol}</small></div>
                </div>`;
            });
            document.getElementById('tk-list').innerHTML = html || "<center><small>Empty</small></center>";
        }

        function switchTab(el, sort) {
            document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
            el.classList.add('active'); loadTokens(sort);
        }

        function openTrade(name, price) {
            currentPrice = price; document.getElementById('tr-title').innerText = "Trade " + name;
            document.getElementById('m-trade').style.display = 'flex';
        }

        function setAmt(pct) {
            document.getElementById('tr-amt').value = (userBalance * (pct/100)).toFixed(2);
            calcTrade();
        }

        function calcTrade() {
            const amt = document.getElementById('tr-amt').value || 0;
            document.getElementById('tr-res').innerText = "Receive: " + Math.floor(amt / currentPrice).toLocaleString() + " tokens";
        }

        async function deploy() {
    const n = document.getElementById('tk-name').value; 
    const s = document.getElementById('tk-sym').value;
    const l = document.getElementById('tk-logo').value;

    if(!n || !s) return tg.showAlert("Please enter Name and Symbol");

    try {
        const res = await fetch('/api/launcher/deploy', {
            method: 'POST', 
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: uid, name: n, symbol: s, logo: l})
        });

        if(res.ok) {
            tg.showAlert("🚀 Token successfully deployed!");
            // 1. Fermer le modal
            document.getElementById('m-create').style.display = 'none';
            // 2. Vider les inputs
            document.getElementById('tk-name').value = "";
            document.getElementById('tk-sym').value = "";
            document.getElementById('tk-logo').value = "";
            // 3. Forcer l'onglet NEW et recharger la liste
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(t => t.classList.remove('active'));
            tabs[0].classList.add('active'); // On active l'onglet NEW (index 0)
            
            await loadTokens('new'); // On recharge
            await refresh(); // On met à jour le solde (les -500 WPT)
        } else {
            tg.showAlert("❌ Error: You need 500 Genesis WPT");
        }
    } catch (e) {
        tg.showAlert("Network error");
    }
}


        tg.expand(); refresh(); setInterval(refresh, 5000);
    </script>
</body>
</html>
    """

# --- BOT SETUP ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    await missions.register_user(uid, name, ref)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome {name}!", reply_markup=kb)

async def main_loop():
    bot = ApplicationBuilder().token(config.TOKEN).build()
    bot.add_handler(CommandHandler("start", start_cmd))
    await bot.initialize()
    await bot.bot.delete_webhook(drop_pending_updates=True)
    await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    c = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    await uvicorn.Server(c).serve()

if __name__ == "__main__":
    asyncio.run(main_loop())