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
    print(f"⚠️ Security Alert: Database init failed: {e}")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- CORE LOGIC FUNCTIONS ---

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

def calculate_yield(token_type, market_pump):
    """Logique du Market Index Boost : Double le gain si le marché 'Pump'"""
    base_yield = 0.05
    if token_type == 'genesis' and market_pump:
        return base_yield * 2 # Boost Or
    return base_yield

# --- API ROUTES ---

@app.get("/api/user/{uid}")
async def api_get_user(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    last_update = r[6] if r[6] is not None else now
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_update) / 60) * config.REGEN_RATE)
    staked = r[8] or 0
    
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, badge_rank, _ = missions.get_badge_info(score)
    top_raw = database.get_leaderboard()
    
    top = []
    for x in top_raw:
        # Badge Michael 8136550118
        is_partner = " 💎 PARTNER" if str(uid) == "8136550118" and x[0] == r[4] else ""
        top.append({
            "n": f"{x[0]}{is_partner}", "p": round(x[1], 2), 
            "b": missions.get_badge_info(x[1])[0], "is_p": (is_partner != "")
        })
    
    # Stratégie de Puissance : Multiplicateur lié au Badge Rank (0 à 5)
    badge_boost = badge_rank * 0.05
    multiplier = round(1.0 + (staked / 100) * 0.1 + (score / 1000) + badge_boost, 2)
    
    market_pump = random.random() > 0.75 # 25% de chance de boost global
    online_c, total_u = get_network_stats()

    news_list = [
        "🟡 Gold price stability attracts institutional investors.",
        "⚪ Silver demand surges in solar panel industry.",
        "💎 Genesis Mining efficiency increased by 5%.",
        "🚀 WPT Ecosystem reaches new active users milestone.",
        "📊 Copper prices rebound amid global supply tightening."
    ]

    return {
        "uid": uid, "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[4],
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "badge": badge,
        "score": round(score, 2), "top": top, "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "multiplier": multiplier, "streak": r[7] or 0, "staked": staked,
        "pending_refs": max(0, (r[3] or 0) - (r[9] or 0)), 
        "online": online_c, "total_users": total_u,
        "market_pump": market_pump,
        "news": random.choice(news_list),
        "prices": {
            "gold": 2150.40 + random.uniform(-2, 2),
            "silver": 24.15 + random.uniform(-0.1, 0.1),
            "copper": 3.85 + random.uniform(-0.02, 0.02)
        }
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    # Simulation simple du pump pour le calcul du rendement API
    is_pump = random.random() > 0.75 
    yield_val = calculate_yield(t, is_pump)

    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, last_click_time FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    now_ms = int(time.time()*1000); now_s = now_ms//1000
    
    if res and (now_ms - (res[2] or 0)) >= 80:
        cur_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now_s - (res[1] or now_s))/60)*config.REGEN_RATE)
        if cur_e >= 1:
            c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+%s, energy=%s, last_energy_update=%s, last_click_time=%s WHERE user_id=%s", 
                      (yield_val, cur_e-1, now_s, now_ms, uid))
            conn.commit(); c.close(); conn.close(); return {"ok": True, "yield": yield_val}
    c.close(); conn.close(); return JSONResponse(status_code=400)

# --- WEB UI (FIXED LAYOUT) ---

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --text: #8E8E8E; --green: #34C759; --purple: #A259FF; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        .ticker-container { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; }
        .ticker-wrapper { display: inline-block; animation: ticker 25s linear infinite; padding-left: 100%; }
        .ticker-item { display: inline-block; margin-right: 40px; color: var(--gold); font-size: 10px; font-weight: bold; }
        @keyframes ticker { 0% { transform: translateX(0); } 100% { transform: translateX(-100%); } }
        
        .alert-zone { height: 45px; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; }
        .market-alert { width: 100%; background: rgba(52, 199, 89, 0.1); border: 1px solid var(--green); color: var(--green); padding: 8px; border-radius: 12px; font-size: 10px; text-align: center; display: none; animation: flash 2s infinite; }
        @keyframes flash { 0% { opacity: 0.5; } 50% { opacity: 1; } 100% { opacity: 0.5; } }

        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2c2c2e; }
        .badge-tag { font-size: 9px; padding: 2px 6px; border-radius: 6px; background: #222; border: 1px solid #333; color: var(--text); }
        .balance { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; position: relative; }
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; position: relative; }
        .energy-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.5s; }
        
        .auto-toggle { position: absolute; top: 10px; right: 10px; font-size: 20px; opacity: 0.3; filter: grayscale(1); transition: 0.3s; cursor: pointer; }
        .auto-toggle.active { opacity: 1; filter: grayscale(0); transform: scale(1.2); text-shadow: 0 0 10px var(--gold); }
        
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .news-box { background: #000; border-left: 3px solid var(--blue); padding: 10px; border-radius: 8px; font-size: 10px; margin-bottom: 10px; color: #ddd; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; font-size: 11px; }
        
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 15px; border: 1px solid #333; z-index: 100; }
        .nav-item { font-size: 18px; opacity: 0.4; position: relative; } 
        .nav-item.active { opacity: 1; color: var(--gold); }
    </style>
</head>
<body>
    <div class="ticker-container">
        <div class="ticker-wrapper">
            <span class="ticker-item">🟢 ONLINE: <span id="online-val">1</span> | 👥 TOTAL: <span id="total-val">1</span></span>
            <span class="ticker-item">🔥 JACKPOT: <span id="jack-val">0</span> WPT</span>
            <span class="ticker-item">📉 MARKET: <span id="news-ticker">Stable</span></span>
        </div>
    </div>

    <div class="alert-zone">
        <div id="m-alert" class="market-alert">📈 GOLD MARKET PUMP! Genesis Yield Boosted x2.</div>
    </div>

    <div class="profile-bar">
        <div><div id="u-name" style="font-weight:700;">...</div><div id="u-badge" class="badge-tag">...</div></div>
        <button class="btn" style="background:var(--gold)" onclick="share()">🚀 INVITE</button>
    </div>

    <div id="p-mine">
        <div class="balance">
            <div id="btn-auto" class="auto-toggle" onclick="toggleAuto()">🤖</div>
            <small style="color:var(--text)">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:45px; margin:8px 0;">0.00</h1>
            <div id="u-mult" style="font-size:10px; color:var(--green)">⚡ Multiplier: x1.0</div>
            <div class="energy-bar"><div id="e-bar" class="energy-fill"></div></div>
            <div id="e-text" style="font-size:11px; color:var(--gold);">⚡ 0 / 100</div>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn" onclick="mine(event, 'genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine(event, 'unity')">SYNC</button></div>
        <div class="card"><div><small style="color:var(--purple)">VEO AI</small><div id="vv">0.00</div></div><button class="btn" onclick="mine(event, 'veo')" style="background:var(--purple); color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="color:var(--gold); text-align:center;">WPT PILLARS</h3>
        <div class="card"><b>WPT Token</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Unity Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Veo AI Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Genesis Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA')">GO</button></div>
    </div>

    <div id="p-opps" style="display:none">
        <h3 style="color:var(--blue); text-align:center;">OPPORTUNITIES</h3>
        <div id="news-feed" class="news-box">⌛ Loading market news...</div>
        <div class="card" style="border: 1px solid #333; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; text-align: center;">
            <div><small style="color:var(--gold)">GOLD</small><br><b id="price-gold" style="font-size:10px;">$---</b></div>
            <div><small style="color:var(--silver)">SILVER</small><br><b id="price-silver" style="font-size:10px;">$---</b></div>
            <div><small style="color:var(--copper)">COPPER</small><br><b id="price-copper" style="font-size:10px;">$---</b></div>
        </div>
        <div class="card" style="border: 1px solid var(--purple); background: linear-gradient(135deg, #111, #1a0a2a); flex-direction: column;">
            <div style="display: flex; justify-content: space-between; width: 100%;"><b>Partner Dashboard</b><span style="color:var(--purple); font-size:10px;">CONNECTED</span></div>
            <div style="margin-top: 15px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; width: 100%;">
                <div style="background:#000; padding:10px; border-radius:10px; text-align:center;"><small style="color:var(--text); font-size:8px;">MY REFERRALS</small><br><b id="p-fol" style="color:var(--purple)">0</b></div>
                <div style="background:#000; padding:10px; border-radius:10px; text-align:center;"><small style="color:var(--text); font-size:8px;">EST. EARNINGS</small><br><b id="p-earn" style="color:var(--green)">0.00</b></div>
            </div>
        </div>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div id="p-mission" style="display:none">
        <h3 style="color:var(--gold); text-align:center;">HUB SETTINGS</h3>
        <div class="card"><div><b>Turbo Robot</b><br><small style="color:var(--text)">Lock 100 WPT for speed boost</small></div><button class="btn" style="background:var(--gold); color:#000">LOCK</button></div>
        <div class="card"><b>Energy Drink</b><button class="btn" style="background:var(--blue); color:#FFF" onclick="useDrink()">DRINK</button></div>
        <div class="card"><div><b>Daily Streak</b></div><div id="u-streak" style="color:var(--gold)">0 Days</div></div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('opps')" id="n-opps" class="nav-item">💡</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('mission')" id="n-mission" class="nav-item">⚙️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let lastClick = 0; let isAuto = false; let hasStaked = false;

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}`); const d = await r.json();
                document.getElementById('u-name').innerText = d.name;
                document.getElementById('u-badge').innerText = d.badge;
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('u-streak').innerText = (d.streak || 0) + " Days";
                document.getElementById('u-mult').innerText = "⚡ Multiplier: x" + d.multiplier;
                document.getElementById('online-val').innerText = d.online;
                document.getElementById('total-val').innerText = d.total_users;
                document.getElementById('jack-val').innerText = d.jackpot;
                document.getElementById('p-fol').innerText = d.rc;
                document.getElementById('p-earn').innerText = (d.rc * 50).toFixed(2);
                document.getElementById('price-gold').innerText = "$" + d.prices.gold.toFixed(2);
                document.getElementById('price-silver').innerText = "$" + d.prices.silver.toFixed(2);
                document.getElementById('price-copper').innerText = "$" + d.prices.copper.toFixed(2);
                
                document.getElementById('news-feed').innerText = d.news;
                document.getElementById('news-ticker').innerText = d.news.substring(0, 15) + "...";
                document.getElementById('m-alert').style.display = d.market_pump ? 'block' : 'none';
                
                hasStaked = (d.staked > 0);
                let botSpeed = hasStaked ? 4000 : 8000;
                let energyVal = Math.floor(d.energy);
                document.getElementById('e-bar').style.width = (energyVal / d.max_energy * 100) + "%";
                document.getElementById('e-text').innerText = `⚡ ${energyVal} / ${d.max_energy}`;
                
                let rl = ""; d.top.forEach((u, i) => { 
                    let color = u.is_p ? "color:var(--purple); font-weight:bold;" : "";
                    rl += `<div class="card"><span style="${color}">${i+1}. ${u.n}</span><b>${u.p}</b></div>`; 
                });
                document.getElementById('rank-list').innerHTML = rl;

                if(isAuto && energyVal >= 1) { setTimeout(simulateAutoMine, botSpeed); }
            } catch(e) {}
        }

        function toggleAuto() {
            isAuto = !isAuto;
            document.getElementById('btn-auto').classList.toggle('active', isAuto);
            if(isAuto) { tg.HapticFeedback.notificationOccurred('success'); refresh(); }
        }

        async function simulateAutoMine() {
            if(!isAuto) return;
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:'genesis'})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('soft'); refresh(); }
        }

        async function mine(e, t) {
            const now = Date.now(); if (now - lastClick < 80) return; lastClick = now;
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('light'); refresh(); }
        }

        async function useDrink() {
            const res = await fetch('/api/use_drink', {method:'POST', body:JSON.stringify({user_id:uid})});
            if(res.ok) { tg.showPopup({title:'Refilled!', message:'Energy 100%.'}); refresh(); }
        }

        function show(p) { ['mine','pillars','leader','mission','opps'].forEach(id=>{document.getElementById('p-'+id).style.display=(id===p?'block':'none'); document.getElementById('n-'+id).classList.toggle('active',id===p);}); }
        function share() { tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/owpcsbot?start=${uid}`); }
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
