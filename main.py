import asyncio, uvicorn, time, random
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import config, database, missions

# --- INITIALISATION & SECURITY ---
try:
    database.init_db_structure()
    print("✅ Database Master Structure Active")
except Exception as e:
    print(f"⚠️ Security Alert: {e}")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- CORE LOGIC ---

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
    
    now = int(time.time()); last_update = r[6] if r[6] is not None else now
    
    # --- LOGIQUE FRENZY COMBO (Vitesse x5) ---
    is_frenzy = (r[7] or 0) > 5 or (random.random() > 0.92)
    regen_rate = config.REGEN_RATE * (5.0 if is_frenzy else 1.0)
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_update) / 60) * regen_rate)
    
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, rank_idx, next_goal = missions.get_badge_info(score)
    staked = r[8] or 0
    
    # Multiplicateur Master (Badge + Stake + Score + Frenzy)
    mult = round(1.0 + (staked / 100) * 0.1 + (score / 1000) + (rank_idx * 0.05), 2)
    if is_frenzy: mult = round(mult * 1.2, 2)

    online_c, total_u = get_network_stats()
    
    # News & Oracle Or/Argent
    prices = {"gold": 2150.40 + random.uniform(-1, 1), "silver": 24.15 + random.uniform(-0.1, 0.1), "copper": 3.85}
    news_items = ["🟡 Gold stability attracts VCs.", "🚀 WPT Network hitting new ATH.", "💎 Genesis Yield Boosted."]
    
    return {
        "uid": uid, "name": r[4], "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0,
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "badge": badge, "rank_idx": rank_idx,
        "score": round(score, 2), "next_goal": next_goal, "multiplier": mult, "frenzy": is_frenzy,
        "online": online_c, "total_users": total_u, "staked": staked, "streak": r[7] or 0,
        "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "news": random.choice(news_items), "prices": prices,
        "top": [{"n": f"{x[0]}", "p": round(x[1], 2), "b": missions.get_badge_info(x[1])[0]} for x in database.get_leaderboard()[:10]]
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, last_click_time FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    now_ms = int(time.time()*1000); now_s = now_ms//1000
    if res and (now_ms - (res[2] or 0)) >= 80:
        cur_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now_s - (res[1] or now_s))/60)*config.REGEN_RATE)
        if cur_e >= 1:
            c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05, energy=%s, last_energy_update=%s, last_click_time=%s WHERE user_id=%s", (cur_e-1, now_s, now_ms, uid))
            conn.commit(); c.close(); conn.close(); return {"ok": True}
    c.close(); conn.close(); return JSONResponse(status_code=400)

@app.post("/api/use_drink")
async def api_use_drink(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET energy = %s, last_energy_update = %s WHERE user_id = %s", (config.MAX_ENERGY, int(time.time()), uid))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --text: #8E8E8E; --green: #34C759; --purple: #A259FF; --red: #FF3B30; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        
        .ticker-container { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; }
        .ticker-wrapper { display: inline-block; animation: ticker 25s linear infinite; padding-left: 100%; }
        .ticker-item { display: inline-block; margin-right: 40px; color: var(--gold); font-size: 10px; font-weight: bold; }
        @keyframes ticker { 0% { transform: translateX(0); } 100% { transform: translateX(-100%); } }
        
        .frenzy-glow { position: fixed; inset: 0; border: 4px solid var(--red); pointer-events: none; z-index: 99; display: none; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 0.1; } 50% { opacity: 0.4; } }

        .alert-zone { height: 45px; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; }
        .m-alert { width: 100%; background: rgba(255, 59, 48, 0.1); border: 1px solid var(--red); color: var(--red); padding: 8px; border-radius: 12px; font-size: 10px; text-align: center; display: none; }

        .balance-card { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; position: relative; }
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; }
        .energy-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.5s; }
        .energy-fill.frenzy { background: linear-gradient(90deg, var(--red), #FF9500); }
        
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; font-size: 11px; }
        
        .xp-bar { background: #222; height: 6px; border-radius: 3px; margin: 10px 0; }
        .xp-fill { background: var(--purple); height: 100%; border-radius: 3px; width: 0%; transition: 1s; }

        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 100; }
        .nav-item { font-size: 20px; opacity: 0.3; } 
        .nav-item.active { opacity: 1; color: var(--gold); }
    </style>
</head>
<body>
    <div id="f-glow" class="frenzy-glow"></div>
    <div class="ticker-container"><div class="ticker-wrapper">
        <span class="ticker-item">🟢 ONLINE: <span id="online-val">1</span> | 👥 TOTAL: <span id="total-val">1</span></span>
        <span class="ticker-item">🔥 JACKPOT: <span id="jack-val">0</span> WPT</span>
    </div></div>

    <div class="alert-zone"><div id="m-alert" class="m-alert">⚡ COMBO FRENZY: 5x REGEN ACTIVE!</div></div>

    <div id="p-mine">
        <div class="balance-card">
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

    <div id="p-profile" style="display:none">
        <div style="text-align:center; padding:20px;">
            <div style="font-size:50px; margin-bottom:10px;">👤</div>
            <h2 id="prof-name">...</h2>
            <div id="prof-badge" style="color:var(--gold); font-size:12px; font-weight:bold;">...</div>
            <div class="xp-bar"><div id="xp-fill" class="xp-fill"></div></div>
            <small id="xp-text" style="color:var(--text); font-size:9px;">Next Goal: ...</small>
        </div>
        <div class="card"><span>Network Power</span><b id="prof-mult">x1.0</b></div>
        <div class="card"><span>Streak</span><b id="prof-streak">0 Days</b></div>
        <div class="card"><span>Staked WPT</span><b id="prof-stake">0</b></div>
    </div>

    <div id="p-opps" style="display:none">
        <h3 style="color:var(--blue); text-align:center;">OPPORTUNITIES</h3>
        <div id="news-feed" style="background:#000; padding:10px; border-radius:10px; font-size:11px; margin-bottom:15px; border-left:3px solid var(--blue);">...</div>
        <div class="card" style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:5px; text-align:center;">
            <div><small style="color:var(--gold)">GOLD</small><br><b id="pr-g" style="font-size:10px;">$---</b></div>
            <div><small style="color:var(--text)">SILVER</small><br><b id="pr-s" style="font-size:10px;">$---</b></div>
            <div><small style="color:var(--purple)">COPPER</small><br><b id="pr-c" style="font-size:10px;">$---</b></div>
        </div>
        <div class="card" style="border:1px solid var(--purple); flex-direction:column; margin-top:10px;">
            <div style="display:flex; justify-content:space-between; width:100%;"><b>Partner Dashboard</b><span style="color:var(--purple); font-size:10px;">CONNECTED</span></div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; width:100%; margin-top:10px;">
                <div style="background:#000; padding:10px; border-radius:10px; text-align:center;"><small style="font-size:8px;">MY REFS</small><br><b id="opp-refs" style="color:var(--purple)">0</b></div>
                <div style="background:#000; padding:10px; border-radius:10px; text-align:center;"><small style="font-size:8px;">EST. EARN</small><br><b id="opp-earn" style="color:var(--green)">0.00</b></div>
            </div>
        </div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="color:var(--gold); text-align:center;">WPT PILLARS</h3>
        <div class="card"><b>WPT Token</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Unity Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Veo AI Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Genesis Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA')">GO</button></div>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('opps')" id="n-opps" class="nav-item">💡</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('profile')" id="n-profile" class="nav-item">👤</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let lastClick = 0;

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}`); const d = await r.json();
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('u-mult').innerText = "⚡ Multiplier: x" + d.multiplier;
                document.getElementById('online-val').innerText = d.online;
                document.getElementById('total-val').innerText = d.total_users;
                document.getElementById('jack-val').innerText = d.jackpot;
                
                // Profile & Opps
                document.getElementById('prof-name').innerText = d.name;
                document.getElementById('prof-badge').innerText = d.badge;
                document.getElementById('prof-mult').innerText = "x" + d.multiplier;
                document.getElementById('prof-streak').innerText = d.streak + " Days";
                document.getElementById('prof-stake').innerText = d.staked;
                document.getElementById('opp-refs').innerText = d.rc;
                document.getElementById('opp-earn').innerText = (d.rc * 50).toFixed(2);
                document.getElementById('news-feed').innerText = d.news;
                document.getElementById('pr-g').innerText = "$" + d.prices.gold.toFixed(2);
                document.getElementById('pr-s').innerText = "$" + d.prices.silver.toFixed(2);
                document.getElementById('pr-c').innerText = "$" + d.prices.copper.toFixed(2);

                // XP Bar logic
                document.getElementById('xp-fill').style.width = ((d.score % 1000) / 10) + "%";
                document.getElementById('xp-text').innerText = "Next Rank: " + d.next_goal;

                // Frenzy Logic
                document.getElementById('f-glow').style.display = d.frenzy ? 'block' : 'none';
                document.getElementById('m-alert').style.display = d.frenzy ? 'block' : 'none';
                document.getElementById('e-bar').classList.toggle('frenzy', d.frenzy);

                let energyVal = Math.floor(d.energy);
                document.getElementById('e-bar').style.width = (energyVal / d.max_energy * 100) + "%";
                document.getElementById('e-text').innerText = `⚡ ${energyVal} / ${d.max_energy}`;
                
                let rl = ""; d.top.forEach((u, i) => { 
                    rl += `<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; 
                });
                document.getElementById('rank-list').innerHTML = rl;
            } catch(e) {}
        }

        async function mine(t) {
            const now = Date.now(); if (now - lastClick < 80) return; lastClick = now;
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('light'); refresh(); }
        }

        function show(p) { ['mine','opps','leader','profile','pillars'].forEach(id=>{document.getElementById('p-'+id).style.display=(id===p?'block':'none'); document.getElementById('n-'+id).classList.toggle('active',id===p);}); }
        tg.expand(); refresh(); setInterval(refresh, 8000);
    </script>
</body>
</html>


"""



async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    # Gestion sécurisée du parrainage
    ref_id = None
    if context.args and context.args[0].isdigit():
        ref_id = int(context.args[0])
    
    await missions.register_user(uid, name, ref_id)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome {name}! Ready to explore the HUB?", reply_markup=kb)

async def main():
    # 1. Préparation de l'application
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_cmd))
    
    # 2. Nettoyage et Initialisation
    await bot_app.initialize()
    # Le drop_pending_updates est crucial pour Michael et les autres
    await bot_app.bot.delete_webhook(drop_pending_updates=True)
    print("🧹 Old sessions cleared. Starting fresh...")
    
    # 3. Lancement du polling en arrière-plan
    await bot_app.start()
    # On utilise create_task pour que le bot n'empêche pas FastAPI de démarrer
    polling_task = asyncio.create_task(bot_app.updater.start_polling())
    print("🤖 Bot Ready and Polling!")
    
    # 4. Lancement du serveur Web (FastAPI)
    # C'est cette partie qui doit "tourner" pour que Railway marque "Completed"
    config_server = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    server = uvicorn.Server(config_server)
    
    try:
        await server.serve()
    finally:
        # Arrêt propre si on coupe le serveur
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
