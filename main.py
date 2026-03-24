import asyncio, uvicorn, time, random
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import config, database, missions

# --- INITIALISATION ---
try:
    database.init_db_structure()
    # Note: On pourrait ajouter ici une table 'community_tokens' plus tard
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
    is_frenzy = (r[7] or 0) > 5 or (random.random() > 0.95)
    regen_rate = config.REGEN_RATE * (5.0 if is_frenzy else 1.0)
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_update) / 60) * regen_rate)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, rank_idx, next_goal = missions.get_badge_info(score)
    staked = r[8] or 0
    mult = round(1.0 + (staked / 100) * 0.1 + (score / 1000) + (rank_idx * 0.05), 2)
    if is_frenzy: mult = round(mult * 1.2, 2)
    online_c, total_u = get_network_stats()
    return {
        "uid": uid, "name": r[4], "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0,
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "badge": badge, "rank_idx": rank_idx,
        "score": round(score, 2), "next_goal": next_goal, "multiplier": mult, "frenzy": is_frenzy,
        "online": online_c, "total_users": total_u, "staked": staked, "streak": r[7] or 0,
        "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "news": "🔥 FRENZY ACTIVE" if is_frenzy else "🚀 WPT HUB Online",
        "top": [{"n": f"{x[0]}", "p": round(x[1], 2), "b": missions.get_badge_info(x[1])[0]} for x in database.get_leaderboard()[:10]]
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, last_click_time FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    now_ms = int(time.time()*1000); now_s = now_ms//1000
    if res and (now_ms - (res[2] or 0)) >= 85:
        cur_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now_s - (res[1] or now_s))/60)*config.REGEN_RATE)
        if cur_e >= 1:
            c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05, energy=%s, last_energy_update=%s, last_click_time=%s WHERE user_id=%s", (cur_e-1, now_s, now_ms, uid))
            conn.commit(); c.close(); conn.close(); return {"ok": True}
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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --text: #8E8E8E; --green: #34C759; --purple: #A259FF; --red: #FF3B30; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        .ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; }
        .t-wrap { display: inline-block; animation: scroll 25s linear infinite; }
        @keyframes scroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
        .t-i { display: inline-block; margin-right: 30px; color: var(--gold); font-size: 10px; font-weight: bold; }
        .f-glow { position: fixed; inset: 0; border: 4px solid var(--red); pointer-events: none; z-index: 99; display: none; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 0.1; } 50% { opacity: 0.4; } }
        .b-card { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; }
        .e-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; }
        .e-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.3s; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; font-size: 11px; cursor: pointer; }
        .input-group { background: #000; padding: 12px; border-radius: 12px; border: 1px solid #333; margin-bottom: 10px; width: 100%; box-sizing: border-box; }
        input { background: transparent; border: none; color: #FFF; width: 100%; outline: none; font-size: 13px; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 10px 15px; border-radius: 40px; display: flex; gap: 8px; border: 1px solid #333; z-index: 100; }
        .n-i { font-size: 15px; opacity: 0.3; padding: 5px; } .n-i.active { opacity: 1; color: var(--gold); }
        .banner-preview { width: 100%; height: 60px; border-radius: 10px; background: #222; margin-bottom: 10px; border: 1px dashed #444; object-fit: cover; display: none; }
    </style>
</head>
<body>
    <div id="f-glow" class="f-glow"></div>
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
        <div class="card"><b>Daily Bonus</b><button id="db-btn" class="btn" style="background:var(--green); color:#FFF" onclick="claimDaily()">CLAIM</button></div>
        <div class="card"><b>Energy Drink</b><button class="btn" style="background:var(--blue); color:#FFF">REFILL</button></div>
    </div>

    <div id="p-opps" style="display:none">
        <h3 style="color:var(--blue); text-align:center;">ORACLE PREDICT</h3>
        <div class="card" style="flex-direction:column; gap:10px;">
            <div style="font-size:11px;">Gold (Genesis) Price in 60s?</div>
            <div style="display:flex; gap:10px; width:100%;">
                <button class="btn" onclick="predict('up')" style="flex:1; background:var(--green); color:#FFF">UP ↑</button>
                <button class="btn" onclick="predict('down')" style="flex:1; background:var(--red); color:#FFF">DOWN ↓</button>
            </div>
        </div>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div id="p-profile" style="display:none">
        <div style="text-align:center; padding:20px;">
            <div style="font-size:40px;">👤</div>
            <h2 id="pr-n">...</h2><div id="pr-b" style="color:var(--gold); font-weight:bold; font-size:12px;">...</div>
        </div>
        <div class="card" style="background:linear-gradient(45deg, #111, #1a1a1a); border: 1px solid var(--purple);">
            <div><b>Team Hub</b><br><small id="team-status">Mining: 12%</small></div><b style="color:var(--purple)">+0.05x</b>
        </div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="color:var(--green); text-align:center;">PILLARS ASSETS</h3>
        <div class="card"><b>WPT Token</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">GO</button></div>
    </div>

    <div id="p-launcher" style="display:none">
        <h3 style="color:var(--purple); text-align:center;">🚀 SOLANA LAUNCHER</h3>
        
        <img id="ban-pre" class="banner-preview">
        
        <div class="input-group"><input type="text" id="tk-name" placeholder="Token Name (ex: SolMoon)"></div>
        <div class="input-group"><input type="text" id="tk-sym" placeholder="Symbol (ex: MOON)"></div>
        <div class="input-group"><input type="text" id="tk-ban" placeholder="Banner Image URL" onchange="updateBan(this.value)"></div>
        <div class="input-group"><input type="text" id="tk-web" placeholder="Website URL (Optional)"></div>
        <div class="input-group"><input type="text" id="tk-x" placeholder="X (Twitter) Handle @"></div>
        
        <div class="card" style="margin-top:10px; border:1px dashed var(--purple); background:rgba(162, 89, 255, 0.05);">
            <div><small style="color:var(--purple)">DEPLOYMENT COST</small><br><b>500 WPT</b></div>
            <button class="btn" style="background:var(--purple); color:#FFF" onclick="launchToken()">LAUNCH</button>
        </div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="n-i active">🏠</div>
        <div onclick="show('missions')" id="n-missions" class="n-i">⚙️</div>
        <div onclick="show('opps')" id="n-opps" class="n-i">💡</div>
        <div onclick="show('leader')" id="n-leader" class="n-i">🏆</div>
        <div onclick="show('profile')" id="n-profile" class="n-i">👤</div>
        <div onclick="show('pillars')" id="n-pillars" class="n-i">📊</div>
        <div onclick="show('launcher')" id="n-launcher" class="n-i">🚀</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let last = 0;
        
        function updateBan(url) {
            const img = document.getElementById('ban-pre');
            if(url) { img.src = url; img.style.display = 'block'; }
            else { img.style.display = 'none'; }
        }

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}`); const d = await r.json();
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('u-m').innerText = "⚡ Multiplier: x" + d.multiplier;
                document.getElementById('pr-n').innerText = d.name;
                document.getElementById('pr-b').innerText = d.badge;
                let ev = Math.floor(d.energy);
                document.getElementById('e-f').style.width = (ev / d.max_energy * 100) + "%";
                document.getElementById('e-t').innerText = `⚡ ${ev} / ${d.max_energy}`;
            } catch(e) {}
        }

        async function mine(t) {
            const now = Date.now(); if (now - last < 85) return; last = now;
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('light'); refresh(); }
        }

        function launchToken() {
            const name = document.getElementById('tk-name').value;
            const sym = document.getElementById('tk-sym').value;
            if(!name || !sym) return tg.showAlert("Name and Symbol required!");
            
            tg.showConfirm(`Deploy ${name} ($${sym}) on Solana for 500 WPT?`, (ok) => {
                if(ok) {
                    tg.HapticFeedback.notificationOccurred('success');
                    tg.showAlert("🚀 Token Queued! It will appear in the Community section shortly.");
                }
            });
        }

        function show(p) { ['mine','opps','missions','profile','pillars','leader','launcher'].forEach(id=>{document.getElementById('p-'+id).style.display=(id===p?'block':'none'); document.getElementById('n-'+id).classList.toggle('active',id===p);}); }
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

async def main():
    bot = ApplicationBuilder().token(config.TOKEN).build()
    bot.add_handler(CommandHandler("start", start_cmd))
    await bot.initialize()
    await bot.bot.delete_webhook(drop_pending_updates=True)
    await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    c = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    await uvicorn.Server(c).serve()

if __name__ == "__main__":
    asyncio.run(main())
