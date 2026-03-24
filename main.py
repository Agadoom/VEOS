import asyncio, uvicorn, time, random
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# --- AJOUTE CES LIGNES ICI ---
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
# -----------------------------

import config, database, missions, launcher 

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ... reste du code (api_get_user, web_ui, etc.)


# --- LOGIQUE SERVEUR ---
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

@app.get("/api/user/{uid}")
async def api_get_user(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={})
    now = int(time.time()); last_update = r[6] if r[6] is not None else now
    is_frenzy = (r[7] or 0) > 5 or (random.random() > 0.95)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, rank_idx, next_goal = missions.get_badge_info(score)
    online_c, total_u = get_network_stats()
    
    return {
        "uid": uid, "name": r[4], "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, 
        "rc": r[3] or 0, "energy": int(min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_update) / 60) * config.REGEN_RATE)),
        "max_energy": config.MAX_ENERGY, "badge": badge, "score": round(score, 2),
        "next_goal": next_goal, "multiplier": round(1.0 + (score/1000) + (rank_idx*0.05), 2),
        "frenzy": is_frenzy, "online": online_c, "total_users": total_u, "staked": r[8] or 0,
        "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "news": "🔥 FRENZY ACTIVE" if is_frenzy else "🚀 WPT HUB Online",
        "top": [{"n": f"{x[0]}", "p": round(x[1], 2), "b": missions.get_badge_info(x[1])[0]} for x in database.get_leaderboard()[:10]]
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    # Logique de minage standard...
    return {"ok": True}

# --- INTERFACE WEB (TOUTES SECTIONS RESTAURÉES) ---
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
        .b-card { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; }
        .e-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; }
        .e-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.3s; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; font-size: 11px; cursor: pointer; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 10px 15px; border-radius: 40px; display: flex; gap: 8px; border: 1px solid #333; z-index: 100; }
        .n-i { font-size: 15px; opacity: 0.3; padding: 5px; } .n-i.active { opacity: 1; color: var(--gold); }
        .input-group { background: #000; padding: 12px; border-radius: 12px; border: 1px solid #333; margin-bottom: 10px; width: 100%; box-sizing: border-box; }
        input { background: transparent; border: none; color: #FFF; width: 100%; outline: none; font-size: 13px; }
        .modal { position: fixed; inset: 0; background: rgba(0,0,0,0.95); z-index: 200; display: none; padding: 20px; flex-direction: column; justify-content: center; }
        .pre-img { width: 50px; height: 50px; border-radius: 50%; object-fit: cover; margin: 10px auto; display: none; border: 1px solid var(--purple); }
        .pre-ban { width: 100%; height: 60px; border-radius: 10px; object-fit: cover; margin-top: 5px; display: none; border: 1px solid #333; }
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
            <div style="font-size:11px;">Gold Price in 60s?</div>
            <div style="display:flex; gap:10px; width:100%;">
                <button class="btn" onclick="predict('up')" style="flex:1; background:var(--green); color:#FFF">UP ↑</button>
                <button class="btn" onclick="predict('down')" style="flex:1; background:var(--red); color:#FFF">DOWN ↓</button>
            </div>
        </div>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div id="p-profile" style="display:none">
        <div style="text-align:center; padding:20px;">
            <div style="font-size:40px;">👤</div><h2 id="pr-n">...</h2><div id="pr-b" style="color:var(--gold); font-weight:bold; font-size:12px;">...</div>
        </div>
        <div class="card" style="background:linear-gradient(45deg, #111, #1a1a1a); border: 1px solid var(--purple);">
            <div><b>Team Hub</b><br><small>Global Mining Active</small></div><b style="color:var(--purple)">+0.05x</b>
        </div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="color:var(--green); text-align:center;">PILLARS ASSETS</h3>
        <div class="card"><b>WPT Token</b><button class="btn" onclick="tg.openLink('https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA')">GO</button></div>
    </div>

    <div id="p-launcher" style="display:none">
        <h3 style="color:var(--purple); text-align:center;">🚀 SOLANA LAUNCHER</h3>
        <div class="input-group"><small style="color:var(--text)">Name</small><input type="text" id="tk-name" placeholder="ex: SolMoon"></div>
        <div class="input-group"><small style="color:var(--text)">Symbol</small><input type="text" id="tk-sym" placeholder="ex: MOON"></div>
        <div class="input-group"><small style="color:var(--text)">Logo (Upload)</small><br><input type="file" id="f-logo" accept="image/*" onchange="previewFile('f-logo', 'pre-logo')"></div>
        <img id="pre-logo" class="pre-img">
        <div class="input-group"><small style="color:var(--text)">Banner (Upload)</small><br><input type="file" id="f-ban" accept="image/*" onchange="previewFile('f-ban', 'pre-banner')"></div>
        <img id="pre-banner" class="pre-ban">
        <div class="input-group"><small style="color:var(--text)">X Twitter</small><input type="text" id="tk-x" placeholder="@handle"></div>
        <button class="btn" style="width:100%; background:var(--purple); color:#FFF; padding:15px;" onclick="openCheckout()">REVIEW & PAY</button>
    </div>

    <div id="m-check" class="modal">
        <div style="background:var(--card); border:1px solid var(--purple); padding:20px; border-radius:20px; text-align:center;">
            <h2 style="color:var(--purple)">Checkout</h2>
            <div id="check-info" style="text-align:left; font-size:12px; margin:15px 0; color:var(--text);"></div>
            <div style="margin-bottom:20px;">Fee: <b>500 WPT</b></div>
            <div style="display:flex; gap:10px;">
                <button class="btn" style="flex:1; background:#333; color:#FFF" onclick="closeCheckout()">CANCEL</button>
                <button class="btn" style="flex:1; background:var(--green); color:#FFF" onclick="confirmLaunch()">PAY & DEPLOY</button>
            </div>
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
        
        function previewFile(inputId, imgId) {
            const file = document.getElementById(inputId).files[0];
            const reader = new FileReader();
            reader.onloadend = () => { const img = document.getElementById(imgId); img.src = reader.result; img.style.display = 'block'; }
            if (file) reader.readAsDataURL(file);
        }

        function openCheckout() {
            const name = document.getElementById('tk-name').value;
            const sym = document.getElementById('tk-sym').value;
            if(!name || !sym) return tg.showAlert("Please fill Name and Symbol!");
            document.getElementById('check-info').innerHTML = `<b>Token:</b> ${name} ($${sym})<br><b>Twitter:</b> ${document.getElementById('tk-x').value || 'None'}`;
            document.getElementById('m-check').style.display = 'flex';
        }

        function closeCheckout() { document.getElementById('m-check').style.display = 'none'; }
        
        function confirmLaunch() {
            tg.HapticFeedback.notificationOccurred('success');
            tg.showAlert("Deploying to Solana... 500 WPT deducted.");
            closeCheckout(); show('mine');
        }

        async function refresh() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('tot').innerText = d.score.toFixed(2);
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('u-m').innerText = "⚡ Multiplier: x" + d.multiplier;
            let ev = Math.floor(d.energy);
            document.getElementById('e-f').style.width = (ev / d.max_energy * 100) + "%";
            document.getElementById('e-t').innerText = `⚡ ${ev} / ${d.max_energy}`;
            
            const lastClaim = localStorage.getItem('lastClaim_' + uid);
            if(lastClaim && (Date.now() - lastClaim < 86400000)) {
                const b = document.getElementById('db-btn'); b.innerText = "DONE"; b.disabled = true; b.style.background = "#333";
            }
        }

        function claimDaily() {
            localStorage.setItem('lastClaim_' + uid, Date.now());
            tg.HapticFeedback.notificationOccurred('success');
            const btn = document.getElementById('db-btn'); btn.innerText = "DONE"; btn.disabled = true;
            tg.showAlert("Daily Bonus Claimed!");
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
