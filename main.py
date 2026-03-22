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
    
    # Calcul Énergie fluide (secondes / 60)
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + (seconds_passed / 60) * config.REGEN_RATE)
    
    # Gain Hors-ligne (Miné pendant l'absence)
    staked = r[8] or 0
    offline_reward = 0
    if staked >= 100 and minutes_passed >= 1:
        offline_reward = round((staked / 100) * 0.01 * minutes_passed, 2)

    # Sauvegarde si > 5 sec pour synchroniser la base avec la Mine
    if seconds_passed >= 5:
        conn = database.get_db_conn(); c = conn.cursor()
        c.execute("""
            UPDATE users 
            SET p_genesis = p_genesis + %s, energy = %s, last_energy_update = %s 
            WHERE user_id = %s
        """, (offline_reward, current_e, now, uid))
        conn.commit(); c.close(); conn.close()

    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0) + offline_reward
    top_raw = database.get_leaderboard()
    top = [{"n": x[0], "p": round(x[1], 2), "b": missions.get_badge_info(x[1])[0]} for x in top_raw]
    
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[4],
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "score": round(score, 2), 
        "off_rw": offline_reward, "top": top, "multiplier": round(1.0 + (staked/100)*0.1 + (score/1000), 2),
        "streak": r[7] or 0, "staked": staked, "pending_refs": max(0, (r[3] or 0)-(r[9] or 0)),
        "badge": missions.get_badge_info(score)[0], "jackpot": round(database.get_total_network_score()*0.1, 2)
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    
    # Récupération directe pour éviter les erreurs d'index de liste
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, last_click_time FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    
    if not res: 
        c.close(); conn.close(); return JSONResponse(status_code=404)
    
    now_ms = int(time.time() * 1000)
    now_s = now_ms // 1000
    
    # 1. Anti-spam 80ms
    if (now_ms - (res[2] or 0)) < 80:
        c.close(); conn.close(); return JSONResponse(status_code=429)
    
    # 2. Calcul Énergie identique au GET (Synchro parfaite)
    last_update = res[1] or now_s
    seconds_passed = now_s - last_update
    current_e = min(config.MAX_ENERGY, (res[0] or 0) + (seconds_passed / 60) * config.REGEN_RATE)
    
    if current_e >= 1:
        c.execute(f"""
            UPDATE users 
            SET p_{t} = COALESCE(p_{t}, 0) + 0.05, 
                energy = %s, 
                last_energy_update = %s, 
                last_click_time = %s 
            WHERE user_id = %s
        """, (current_e - 1, now_s, now_ms, uid))
        conn.commit(); c.close(); conn.close()
        return {"ok": True}
    
    c.close(); conn.close()
    return JSONResponse(status_code=400, content={"error": "no_energy"})

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
        conn.commit(); c.close(); conn.close()
        return {"ok": True, "reward": reward}
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
        .header-ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px; font-size: 10px; display: flex; justify-content: space-between; border-bottom: 1px solid #333; color: var(--gold); }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2c2c2e; }
        .badge-tag { font-size: 9px; padding: 2px 6px; border-radius: 6px; background: #222; border: 1px solid #333; color: var(--text); }
        .balance { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; }
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; position: relative; }
        .energy-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.5s; }
        .energy-full-badge { position: absolute; top: -15px; right: 0; font-size: 8px; color: var(--green); font-weight: bold; display: none; animation: blink 1s infinite; }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0; } 100% { opacity: 1; } }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; font-size: 11px; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 100; }
        .nav-item { font-size: 20px; opacity: 0.4; } 
        .nav-item.active { opacity: 1; color: var(--gold); }
    </style>
</head>
<body>
    <div class="header-ticker"><span>👥 REFS: <span id="u-ref-top">0</span></span><span>🔥 JACKPOT: <span id="jack-val">0</span></span></div>
    
    <div class="profile-bar">
        <div><div id="u-name" style="font-weight:700;">...</div><div id="u-badge" class="badge-tag">...</div></div>
        <button class="btn" style="background:var(--gold)" onclick="share()">🚀 INVITE</button>
    </div>

    <div id="offline-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:2000; align-items:center; justify-content:center;">
        <div style="background:#111; border:2px solid #FFD700; padding:30px; border-radius:30px; text-align:center;">
            <h2 style="color:#FFD700">Bon retour !</h2>
            <p>Tes actifs ont miné pendant ton absence :</p>
            <div style="font-size:32px; font-weight:bold; margin:15px 0;">+ <span id="rw-amt">0</span> WPT</div>
            <button onclick="document.getElementById('offline-modal').style.display='none'" style="background:#FFF; color:#000; border:none; padding:10px 20px; border-radius:10px; font-weight:bold;">RÉCOLTER</button>
        </div>
    </div>

    <div id="p-mine">
        <div class="balance">
            <small style="color:var(--text)">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:45px; margin:8px 0;">0.00</h1>
            <div id="u-mult" style="font-size:10px; color:var(--green)">⚡ Multiplier: x1.0</div>
            <div class="energy-bar">
                <div id="e-bar" class="energy-fill"></div>
                <div id="e-full" class="energy-full-badge">READY TO MINE</div>
            </div>
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
        <div class="card">
            <div style="display: flex; flex-direction: column; width: 100%;">
                <div style="display: flex; justify-content: space-between; width: 100%;">
                    <b>Referral Bonus</b>
                    <span id="pending-val" style="color:var(--gold); font-weight:800;">0 pending</span>
                </div>
                <button id="claim-btn" class="btn" style="width:100%; background:var(--green); color:#FFF; display:none; margin-top:10px;" onclick="claimRefs()">CLAIM REWARD</button>
            </div>
        </div>
        <div class="card"><div><b>Daily Streak</b></div><div id="u-streak" style="color:var(--gold)">0 Days</div></div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('mission')" id="n-mission" class="nav-item">⚙️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let lastClick = 0;
        let offlineShowed = false;

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}`); 
                const d = await r.json();
                if(!d.name) return;

                // Affichage du modal de récolte si gain détecté
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

                // Énergie (Math.floor pour éviter les décimales moches)
                let energyVal = Math.floor(d.energy);
                document.getElementById('e-bar').style.width = (energyVal / d.max_energy * 100) + "%";
                document.getElementById('e-text').innerText = `⚡ ${energyVal} / ${d.max_energy}`;
                document.getElementById('e-full').style.display = (d.energy >= d.max_energy) ? 'block' : 'none';

                // Missions
                const pending = d.pending_refs || 0;
                document.getElementById('pending-val').innerText = pending + " pending";
                document.getElementById('claim-btn').style.display = (pending > 0) ? 'block' : 'none';

                // Leaderboard
                let rl = ""; d.top.forEach((u, i) => { rl += `<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
                document.getElementById('rank-list').innerHTML = rl;
            } catch(e) { console.error(e); }
        }

        async function mine(e, t) {
            const now = Date.now(); if (now - lastClick < 80) return; lastClick = now;
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) {
                // Animation petit +0.05
                const rect = e.target.getBoundingClientRect();
                const plus = document.createElement('div'); plus.innerText = '+0.05';
                plus.style.cssText = `position:absolute; left:${rect.left+20}px; top:${rect.top}px; color:var(--gold); font-weight:bold; z-index:1000; pointer-events:none;`;
                plus.animate([{transform:'translateY(0)',opacity:1},{transform:'translateY(-50px)',opacity:0}], 600);
                document.body.appendChild(plus); setTimeout(()=>plus.remove(), 600);
                
                tg.HapticFeedback.impactOccurred('light');
                refresh();
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
