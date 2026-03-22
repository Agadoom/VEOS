import asyncio, uvicorn, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import config, database, missions

# --- INITIALISATION ---
try:
    database.init_db_structure()
    print("✅ Database structure updated!")
except Exception as e:
    print(f"⚠️ Update failed: {e}")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- API ROUTES ---

@app.get("/api/user/{uid}")
async def api_get_user(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    last_update = r[6] if r[6] is not None else now
    seconds_passed = now - last_update
    minutes_passed = seconds_passed // 60
    
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + (seconds_passed / 60) * config.REGEN_RATE)
    
    staked = r[8] or 0
    offline_reward = 0
    if staked >= 100 and minutes_passed > 0:
        offline_reward = round((staked / 100) * 0.01 * minutes_passed, 2)
        conn = database.get_db_conn(); c = conn.cursor()
        c.execute("UPDATE users SET p_genesis = p_genesis + %s, last_energy_update = %s, energy = %s WHERE user_id = %s", 
                  (offline_reward, now, current_e, uid))
        conn.commit(); c.close(); conn.close()

    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0) + offline_reward
    badge, _, _ = missions.get_badge_info(score)
    top_raw = database.get_leaderboard()
    top = [{"n": x[0], "p": round(x[1], 2), "b": missions.get_badge_info(x[1])[0]} for x in top_raw]
    
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[4],
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "badge": badge,
        "score": round(score, 2), "off_rw": offline_reward, 
        "top": top, "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "multiplier": round(1.0 + (staked / 100) * 0.1 + (score / 1000), 2),
        "streak": r[7] or 0, "staked": staked,
        "pending_refs": max(0, (r[3] or 0) - (r[9] or 0))
    }

@app.post("/api/use_drink")
async def api_use_drink(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET energy = %s, last_energy_update = %s WHERE user_id = %s", (config.MAX_ENERGY, int(time.time()), uid))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, last_click_time FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    if not res: c.close(); conn.close(); return JSONResponse(status_code=404)
    now_ms = int(time.time() * 1000); now_s = now_ms // 1000
    if (now_ms - (res[2] or 0)) < 80: c.close(); conn.close(); return JSONResponse(status_code=429)
    current_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now_s - (res[1] or now_s)) / 60) * config.REGEN_RATE)
    if current_e >= 1:
        c.execute(f"UPDATE users SET p_{t} = COALESCE(p_{t}, 0) + 0.05, energy = %s, last_energy_update = %s, last_click_time = %s WHERE user_id = %s", (current_e - 1, now_s, now_ms, uid))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    c.close(); conn.close(); return JSONResponse(status_code=400)

@app.post("/api/claim_refs")
async def api_claim_refs(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT ref_count, ref_claimed FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    pending = (res[0] or 0) - (res[1] or 0)
    if pending > 0:
        reward = pending * 5.0
        c.execute("UPDATE users SET p_genesis=p_genesis+%s, ref_claimed=ref_count WHERE user_id=%s", (reward, uid))
        conn.commit(); c.close(); conn.close(); return {"ok": True, "reward": reward}
    c.close(); conn.close(); return JSONResponse(status_code=400)

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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --text: #8E8E93; --green: #34C759; --purple: #A259FF; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        
        .ticker-container { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; }
        .ticker-wrapper { display: inline-block; animation: ticker 15s linear infinite; padding-left: 100%; }
        .ticker-item { display: inline-block; margin-right: 50px; color: var(--gold); font-size: 11px; font-weight: bold; }
        @keyframes ticker { 0% { transform: translateX(0); } 100% { transform: translateX(-100%); } }

        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2c2c2e; }
        .badge-tag { font-size: 9px; padding: 2px 6px; border-radius: 6px; background: #222; border: 1px solid #333; color: var(--text); }
        .balance { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; position: relative; }
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; position: relative; }
        .energy-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.5s; }
        
        .auto-toggle { position: absolute; top: 10px; right: 10px; font-size: 20px; opacity: 0.3; filter: grayscale(1); transition: 0.3s; cursor: pointer; }
        .auto-toggle.active { opacity: 1; filter: grayscale(0); transform: scale(1.2); text-shadow: 0 0 10px var(--gold); }

        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; font-size: 11px; }
        
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 100; }
        .nav-item { font-size: 20px; opacity: 0.4; position: relative; } 
        .nav-item.active { opacity: 1; color: var(--gold); }
        .notif-dot { position: absolute; top: -2px; right: -2px; width: 8px; height: 8px; background: #FF3B30; border-radius: 50%; display: none; box-shadow: 0 0 5px #FF3B30; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0% { transform: scale(0.9); opacity: 1; } 50% { transform: scale(1.2); opacity: 0.5; } 100% { transform: scale(0.9); opacity: 1; } }
    </style>
</head>
<body>
    <div class="ticker-container">
        <div class="ticker-wrapper">
            <span class="ticker-item">👥 NETWORK REFS: <span id="u-ref-top">0</span></span>
            <span class="ticker-item">🔥 GLOBAL JACKPOT: <span id="jack-val">0</span> WPT</span>
            <span class="ticker-item">🚀 MINING BOT: <span id="bot-status" style="color:var(--text)">OFF</span></span>
        </div>
    </div>
    
    <div class="profile-bar">
        <div><div id="u-name" style="font-weight:700;">...</div><div id="u-badge" class="badge-tag">...</div></div>
        <button class="btn" style="background:var(--gold)" onclick="share()">🚀 INVITE</button>
    </div>

    <div id="offline-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:2000; align-items:center; justify-content:center;">
        <div style="background:#111; border:2px solid #FFD700; padding:30px; border-radius:30px; text-align:center;">
            <h2 style="color:#FFD700">Bon retour !</h2>
            <div style="font-size:32px; font-weight:bold; margin:15px 0;">+ <span id="rw-amt">0</span> WPT</div>
            <button onclick="document.getElementById('offline-modal').style.display='none'" class="btn">RÉCOLTER</button>
        </div>
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
        <h3 style="color:var(--gold); text-align:center;">$WPT PILLARS</h3>
        <div class="card"><b>WPT Token</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Unity Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Veo AI Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA')">GO</button></div>
        <div class="card"><b>Genesis Asset</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA')">GO</button></div>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div id="p-mission" style="display:none">
        <h3 style="color:var(--gold); text-align:center;">MISSIONS</h3>
        <div class="card" style="border: 1px solid var(--blue);">
            <div><b>Energy Drink</b><br><small style="color:var(--text)">Refill 100% instantly</small></div>
            <button class="btn" style="background:var(--blue); color:#FFF" onclick="useDrink()">DRINK</button>
        </div>
        <div class="card">
            <div style="display: flex; flex-direction: column; width: 100%;">
                <div style="display: flex; justify-content: space-between; width: 100%;"><b>Referral Bonus</b><span id="pending-val" style="color:var(--gold);">0 pending</span></div>
                <button id="claim-btn" class="btn" style="width:100%; background:var(--green); color:#FFF; display:none; margin-top:10px;" onclick="claimRefs()">CLAIM REWARD</button>
            </div>
        </div>
        <div class="card"><div><b>Daily Streak</b></div><div id="u-streak" style="color:var(--gold)">0 Days</div></div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠<div id="notif-mine" class="notif-dot"></div></div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('mission')" id="n-mission" class="nav-item">⚙️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let lastClick = 0; let offlineShowed = false;
        let isAuto = false; 
        let autoAssets = ['genesis', 'unity', 'veo'];
        let autoIndex = 0;

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}`); const d = await r.json();
                if(!d.name) return;

                if(d.off_rw > 0 && !offlineShowed) {
                    document.getElementById('rw-amt').innerText = d.off_rw.toFixed(2);
                    document.getElementById('offline-modal').style.display = 'flex';
                    offlineShowed = true;
                }

                document.getElementById('u-name').innerText = d.name;
                document.getElementById('u-badge').innerText = d.badge;
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('u-streak').innerText = d.streak + " Days";
                document.getElementById('jack-val').innerText = d.jackpot;
                document.getElementById('u-ref-top').innerText = d.rc;
                document.getElementById('u-mult').innerText = "⚡ Multiplier: x" + d.multiplier;

                let energyVal = Math.floor(d.energy);
                document.getElementById('e-bar').style.width = (energyVal / d.max_energy * 100) + "%";
                document.getElementById('e-text').innerText = `⚡ ${energyVal} / ${d.max_energy}`;
                document.getElementById('notif-mine').style.display = (energyVal >= d.max_energy) ? 'block' : 'none';

                const pending = d.pending_refs || 0;
                document.getElementById('pending-val').innerText = pending + " pending";
                document.getElementById('claim-btn').style.display = (pending > 0) ? 'block' : 'none';

                let rl = ""; d.top.forEach((u, i) => { rl += `<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
                document.getElementById('rank-list').innerHTML = rl;

                // SI AUTO-MINE : On mine l'actif suivant dans la rotation
                if(isAuto && energyVal >= 1) {
                    let assetToMine = autoAssets[autoIndex];
                    autoIndex = (autoIndex + 1) % autoAssets.length;
                    simulateAutoMine(assetToMine);
                }
            } catch(e) { console.error(e); }
        }

        function toggleAuto() {
            isAuto = !isAuto;
            const btn = document.getElementById('btn-auto');
            const status = document.getElementById('bot-status');
            btn.classList.toggle('active', isAuto);
            status.innerText = isAuto ? "ACTIVE ⚡" : "OFF";
            status.style.color = isAuto ? "var(--green)" : "var(--text)";
            if(isAuto) { tg.HapticFeedback.notificationOccurred('success'); refresh(); }
        }

        async function simulateAutoMine(token) {
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:token})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('soft'); refresh(); }
        }

        async function useDrink() {
            const res = await fetch('/api/use_drink', {method:'POST', body:JSON.stringify({user_id:uid})});
            if(res.ok) { tg.showPopup({title:'Refilled!', message:'Your energy is now 100%'}); refresh(); }
        }

        async function mine(e, t) {
            const now = Date.now(); if (now - lastClick < 80) return; lastClick = now;
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) {
                const rect = e.target.getBoundingClientRect();
                const plus = document.createElement('div'); plus.innerText = '+0.05';
                plus.style.cssText = `position:absolute; left:${rect.left+20}px; top:${rect.top}px; color:var(--gold); font-weight:bold; z-index:1000; pointer-events:none;`;
                plus.animate([{transform:'translateY(0)',opacity:1},{transform:'translateY(-50px)',opacity:0}], 600);
                document.body.appendChild(plus); setTimeout(()=>plus.remove(), 600);
                tg.HapticFeedback.impactOccurred('light'); refresh();
            }
        }

        async function claimRefs() {
            const r = await fetch('/api/claim_refs', {method:'POST', body:JSON.stringify({user_id:uid})});
            if((await r.json()).ok) { tg.showPopup({title:'Success!', message:'Reward claimed!'}); refresh(); }
        }

        function show(p) { ['mine','pillars','leader','mission'].forEach(id=>{document.getElementById('p-'+id).style.display=(id===p?'block':'none'); document.getElementById('n-'+id).classList.toggle('active',id===p);}); }
        function share() { tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/owpcsbot?start=${uid}`); }
        
        tg.expand(); refresh(); setInterval(refresh, 8000);
    </script>
</body>
</html>
"""

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    await missions.register_user(uid, name, ref_id)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome {name}!", reply_markup=kb)

async def main():
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start_cmd))
    await bot_app.initialize(); await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    config_server = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    await uvicorn.Server(config_server).serve()

if __name__ == "__main__":
    asyncio.run(main())
