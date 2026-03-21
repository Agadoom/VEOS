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
    if not r:
        return JSONResponse(status_code=404, content={})
    
    # --- 1. Gestion du Daily Login (Récompense quotidienne) ---
    daily_reward, final_streak = missions.process_daily_login(uid)

    now = int(time.time())
    last_update = r[6] if r[6] is not None else now
    minutes_passed = (now - last_update) // 60
    
    # --- 2. Calcul Énergie ---
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + (minutes_passed * config.REGEN_RATE))
    
    # --- 3. Calcul Gain Hors-ligne ---
    staked = r[8] or 0
    offline_reward = 0
    if staked >= 100 and minutes_passed > 0:
        offline_reward = round((staked / 100) * 0.01 * minutes_passed, 2)
        conn = database.get_db_conn()
        c = conn.cursor()
        c.execute("UPDATE users SET p_genesis=p_genesis+%s, last_energy_update=%s, energy=%s WHERE user_id=%s", 
                  (offline_reward, now, current_e, uid))
        conn.commit()
        c.close(); conn.close()

    # --- 4. Score Total ---
    # On ajoute r[0] (Genesis), r[1] (Unity), r[2] (Veo), l'offline et le daily
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0) + offline_reward + daily_reward
    badge, _, _ = missions.get_badge_info(score)
    
    top_raw = database.get_leaderboard()
    top = [{"n": x[0], "p": round(x[1], 2), "b": missions.get_badge_info(x[1])[0]} for x in top_raw]
    
    # --- 5. Retour JSON ---
    return {
        "g": (r[0] or 0) + daily_reward, 
        "u": r[1] or 0, 
        "v": r[2] or 0, 
        "rc": r[3] or 0, 
        "name": r[4],
        "energy": int(current_e), 
        "max_energy": config.MAX_ENERGY, 
        "badge": badge,
        "score": round(score, 2), 
        "off_rw": offline_reward, 
        "daily_rw": daily_reward, # Ajouté pour le modal JS
        "top": top, 
        "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "multiplier": round(1.0 + (staked / 100) * 0.1 + (score / 1000), 2),
        "streak": final_streak, # Utilise le streak mis à jour
        "staked": staked,
        "pending_refs": max(0, (r[3] or 0) - (r[9] or 0))
    }





@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, staked_amount, last_click_time FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    now_ms = int(time.time() * 1000); last_click = res[3] or 0
    if (now_ms - last_click) < 80:
        c.close(); conn.close(); return JSONResponse(status_code=429, content={})
    
    now_s = now_ms // 1000
    current_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now_s - (res[1] or now_s)) // 60) * config.REGEN_RATE)
    if current_e >= 1:
        c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05, energy=%s, last_energy_update=%s, last_click_time=%s WHERE user_id=%s", (current_e-1, now_s, now_ms, uid))
        conn.commit(); c.close(); conn.close(); return {"ok": True}
    c.close(); conn.close(); return JSONResponse(status_code=400, content={})

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
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; }
        .energy-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.5s; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; font-size: 11px; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 100; }
        .nav-item { font-size: 20px; opacity: 0.4; } 
        .nav-item.active { opacity: 1; color: var(--gold); }
        .modal { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 2000; display: none; align-items: center; justify-content: center; }
        .modal-content { background: var(--card); border: 2px solid var(--gold); padding: 30px; border-radius: 30px; text-align: center; width: 80%; }
    </style>
</head>
<body>
    <div class="header-ticker">
        <span>👥 REFS: <span id="u-ref-top">0</span></span>
        <span>🔥 JACKPOT: <span id="jack-val">0</span></span>
    </div>
    
    <div class="profile-bar">
        <div><div id="u-name" style="font-weight:700;">...</div><div id="u-badge" class="badge-tag">...</div></div>
        <button class="btn" style="background:var(--gold)" onclick="share()">🚀 INVITE</button>
    </div>

    <div id="daily-modal" class="modal">
        <div class="modal-content" style="border-color:var(--green)">
            <div style="font-size: 50px;">🌟</div>
            <h2 style="color:var(--green)">Daily Reward!</h2>
            <p>Day <span id="streak-num">1</span> Streak</p>
            <div style="font-size:32px; font-weight:900; margin:15px 0;">+ <span id="daily-amt">0</span> WPT</div>
            <button class="btn" style="background:var(--green); width:100%; padding:15px; color:#FFF" onclick="closeDaily()">COLLECT</button>
        </div>
    </div>

    <div id="offline-modal" class="modal">
        <div class="modal-content">
            <div style="font-size: 40px;">😴</div>
            <h2 style="color:var(--gold)">Welcome Back!</h2>
            <div style="font-size:32px; font-weight:900; margin:15px 0;">+ <span id="rw-amt">0</span> WPT</div>
            <button class="btn" style="background:var(--gold); width:100%; padding:15px;" onclick="closeModal()">COLLECT</button>
        </div>
    </div>

    <div id="p-mine">
        <div class="balance">
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
        <div class="card"><div><b>Streak</b></div><div id="u-streak" style="color:var(--gold)">0 Days</div></div>
        <div class="card"><div><b>Staked</b></div><div id="staked-val">0</div></div>
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

        function closeDaily() { document.getElementById('daily-modal').style.display = 'none'; }
        function closeModal() { document.getElementById('offline-modal').style.display = 'none'; }

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}`); const d = await r.json();
                if (!d.name) return;
                if (d.daily_rw > 0) {
                    document.getElementById('daily-amt').innerText = d.daily_rw;
                    document.getElementById('streak-num').innerText = d.streak;
                    document.getElementById('daily-modal').style.display = 'flex';
                } else if (d.off_rw > 0) {
                    document.getElementById('rw-amt').innerText = d.off_rw.toFixed(2);
                    document.getElementById('offline-modal').style.display = 'flex';
                }
                document.getElementById('u-name').innerText = d.name;
                document.getElementById('u-badge').innerText = d.badge;
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('e-bar').style.width = (d.energy/d.max_energy*100) + "%";
                document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
                document.getElementById('u-streak').innerText = d.streak + " Days";
                document.getElementById('jack-val').innerText = d.jackpot;
                document.getElementById('u-ref-top').innerText = d.rc;
                let rl = ""; d.top.forEach((u, i) => { rl += `<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
                document.getElementById('rank-list').innerHTML = rl;
            } catch(e) {}
        }

        function mine(e, t) {
            const now = Date.now(); if (now - lastClick < 80) return; lastClick = now;
            const rect = e.target.getBoundingClientRect();
            const plus = document.createElement('div');
            plus.innerText = '+0.05'; plus.style.position = 'absolute';
            plus.style.left = (e.clientX || rect.left+20) + 'px'; plus.style.top = (e.clientY || rect.top) + 'px';
            plus.style.color = 'var(--gold)'; plus.style.fontWeight = 'bold';
            plus.animate([{transform:'translateY(0)',opacity:1},{transform:'translateY(-50px)',opacity:0}], 600);
            document.body.appendChild(plus); setTimeout(()=>plus.remove(), 600);
            fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            refresh(); tg.HapticFeedback.impactOccurred('light');
        }

        function show(p) { ['mine','pillars','leader','mission'].forEach(id=>{document.getElementById('p-'+id).style.display=(id===p?'block':'none'); document.getElementById('n-'+id).classList.toggle('active',id===p);}); }
        function share() { tg.openTelegramLink(`https://t.me/share/url?url=https://t.me/owpcsbot?start=${uid}`); }
        
        tg.expand(); refresh(); setInterval(refresh, 8000);
    </script>
</body>
</html>
"""

# --- BOT ---

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
