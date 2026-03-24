import asyncio, uvicorn, time, random, threading
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
    # Calcul Energie
    last_upd = r[6] if r[6] else now
    regen = config.REGEN_RATE
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_upd)/60) * regen)
    
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, rank_idx, next_goal = missions.get_badge_info(score)
    online_c, total_u = get_network_stats()
    
    return {
        "uid": uid, "name": r[4], "g": round(r[0] or 0, 2), "u": round(r[1] or 0, 2), "v": round(r[2] or 0, 2),
        "energy": int(current_e), "max_energy": config.MAX_ENERGY,
        "score": round(score, 2), "badge": badge, "next_goal": next_goal,
        "online": online_c, "total_users": total_u, "staked": r[8] or 0, "streak": r[7] or 0,
        "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "multiplier": round(1.0 + (score/5000), 2)
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    conn = database.get_db_conn(); c = conn.cursor()
    try:
        now_ms = int(time.time()*1000); now_s = now_ms//1000
        # Vérification énergie et anti-spam (85ms)
        c.execute("SELECT energy, last_energy_update, last_click_time FROM users WHERE user_id=%s", (uid,))
        res = c.fetchone()
        if res and (now_ms - (res[2] or 0)) >= 85:
            if (res[0] or 0) >= 1:
                c.execute(f"UPDATE users SET p_{t}=p_{t}+0.05, energy=energy-1, last_energy_update=%s, last_click_time=%s WHERE user_id=%s", (now_s, now_ms, uid))
                conn.commit()
                return {"ok": True}
        return JSONResponse(status_code=400, content={"error": "Cooldown or No Energy"})
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        c.close(); conn.close()

@app.post("/api/launcher/deploy")
async def api_deploy_token(request: Request):
    data = await request.json()
    uid, name, symbol, logo = data.get("user_id"), data.get("name"), data.get("symbol"), data.get("logo")
    conn = database.get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res or res[0] < 500:
            return JSONResponse(status_code=400, content={"error": "Need 500 Genesis WPT"})
        
        c.execute("UPDATE users SET p_genesis = p_genesis - 500 WHERE user_id = %s", (uid,))
        c.execute("INSERT INTO community_tokens (creator_id, name, symbol, logo, reserve_wpt, created_at) VALUES (%s, %s, %s, %s, %s, %s)", 
                  (uid, name, symbol, logo, 500, int(time.time())))
        conn.commit()
        return {"ok": True}
    except:
        conn.rollback(); return JSONResponse(status_code=500)
    finally:
        c.close(); conn.close()

@app.get("/api/launcher/list")
async def api_list_tokens():
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT name, symbol, logo, price, holders, reserve_wpt FROM community_tokens ORDER BY id DESC")
    tokens = c.fetchall()
    c.close(); conn.close()
    return [{"name": t[0], "symbol": t[1], "logo": t[2], "price": t[3], "holders": t[4], "mcap": round(t[5]*2, 2)} for t in tokens]

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
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 15px; border: 1px solid #333; z-index: 100; }
        .n-i { font-size: 18px; opacity: 0.3; } .n-i.active { opacity: 1; color: var(--gold); }
        .input-group { background: #000; padding: 12px; border-radius: 12px; border: 1px solid #333; margin-bottom: 10px; width: 100%; box-sizing: border-box; }
        input { background: transparent; border: none; color: #FFF; width: 100%; outline: none; }
        .modal { position: fixed; inset: 0; background: rgba(0,0,0,0.95); z-index: 200; display: none; padding: 20px; flex-direction: column; justify-content: center; }
        .pre-img { width: 50px; height: 50px; border-radius: 50%; display: none; margin: 10px auto; border: 1px solid var(--purple); }
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
        <div class="card"><div><b>Turbo Robot</b><br><small>Stake 100 WPT</small></div><button class="btn" style="background:var(--gold)">STAKE</button></div>
        <div class="card"><b>Daily Bonus</b><button id="db-btn" class="btn" style="background:var(--green); color:#FFF" onclick="claimDaily()">CLAIM</button></div>
    </div>

    <div id="p-opps" style="display:none">
        <h3 style="color:var(--blue); text-align:center;">ORACLE PREDICT</h3>
        <div id="n-f" style="background:#000; padding:10px; border-radius:10px; font-size:11px; margin-bottom:10px; border-left:3px solid var(--blue);">...</div>
        <div class="card" style="flex-direction:column; gap:10px;">
            <div style="font-size:11px;">Genesis Price in 60s?</div>
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
            <div class="xp-b" style="background:#222; height:6px; border-radius:3px; margin:10px 0;"><div id="xp-f" class="xp-f" style="background:var(--purple); height:100%; border-radius:3px; width:0%"></div></div>
            <small id="xp-t" style="color:var(--text); font-size:9px;">Next Rank: ...</small>
        </div>
        <div class="card"><span>Power</span><b id="pr-m">x1.0</b></div>
        <div class="card"><span>Streak</span><b id="pr-s">0 Days</b></div>
        <div class="card"><span>Staked</span><b id="pr-st">0</b></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="color:var(--green); text-align:center;">PILLARS ASSETS</h3>
        <div class="card"><div><b>Genesis Asset</b></div><button class="btn" onclick="tg.openLink('https://t.me/blum')">GO</button></div>
        <div class="card"><div><b>Unity Asset</b></div><button class="btn" onclick="tg.openLink('https://t.me/blum')">GO</button></div>
    </div>

    <div id="p-launcher" style="display:none">
        <h3 style="color:var(--purple); text-align:center;">🚀 SOLANA TERMINAL</h3>
        
        <div id="launch-form">
            <div class="input-group"><small style="color:var(--text)">Token Name</small><input type="text" id="tk-name" placeholder="ex: SolMoon"></div>
            <div class="input-group"><small style="color:var(--text)">Symbol</small><input type="text" id="tk-sym" placeholder="ex: MOON"></div>
            <div class="input-group"><small style="color:var(--text)">Logo</small><br><input type="file" id="f-logo" accept="image/*" onchange="previewFile('f-logo', 'pre-logo')"></div>
            <img id="pre-logo" class="pre-img">
            <div class="input-group"><small style="color:var(--text)">X Twitter</small><input type="text" id="tk-x" placeholder="@handle"></div>
            <button class="btn" style="width:100%; background:var(--purple); color:#FFF; padding:15px;" onclick="openCheckout()">REVIEW & PAY</button>
            <hr style="border:0; border-top:1px solid #222; margin:20px 0;">
            <small style="color:var(--text)">EXPLORE COMMUNITY</small>
            <div id="community-tokens-list" style="margin-top:10px;"></div>
        </div>

        <div id="token-live-view" style="display:none;">
            <button class="btn" style="background:#222; color:#FFF; margin-bottom:10px;" onclick="backToLauncher()">< BACK</button>
            <div class="card" style="border: 1px solid var(--purple); flex-direction:column; align-items:flex-start; gap:12px;">
                <div style="display:flex; gap:10px; align-items:center; width:100%;">
                    <img id="live-tk-logo" src="" style="width:45px; height:45px; border-radius:50%; border:2px solid var(--purple);">
                    <div style="flex:1">
                        <b id="live-tk-name">---</b>
                        <div id="live-tk-price" style="color:var(--green); font-family:monospace;">0.0000 WPT</div>
                    </div>
                    <div style="text-align:right"><small>HOLDERS</small><br><b id="live-tk-holders">1</b></div>
                </div>
                <div style="width:100%;">
                    <div style="display:flex; justify-content:space-between; font-size:9px;"><span>Bonding Curve</span><span id="curve-pct">0%</span></div>
                    <div class="xp-b" style="background:#222; height:6px; margin:5px 0;"><div id="bonding-curve" class="xp-f" style="width:0%; background:var(--green)"></div></div>
                </div>
            </div>
            <div style="margin-top:15px;">
                <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:5px;">
                    <button class="btn" style="background:#222; color:#FFF" onclick="setTradePct(25)">25%</button>
                    <button class="btn" style="background:#222; color:#FFF" onclick="setTradePct(50)">50%</button>
                    <button class="btn" style="background:#222; color:#FFF" onclick="setTradePct(75)">75%</button>
                    <button class="btn" style="background:var(--purple); color:#FFF" onclick="setTradePct(100)">MAX</button>
                </div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:15px;">
                <button class="btn" style="background:var(--green); color:#FFF; padding:18px;" onclick="executeTrade('buy')">BUY</button>
                <button class="btn" style="background:var(--red); color:#FFF; padding:18px;" onclick="executeTrade('sell')">SELL</button>
            </div>
        </div>
    </div>

    <div id="m-check" class="modal">
        <div style="background:var(--card); border:1px solid var(--purple); padding:20px; border-radius:20px; text-align:center;">
            <h2 style="color:var(--purple)">Final Review</h2>
            <div id="check-info" style="text-align:left; font-size:11px; margin:15px 0;"></div>
            <b style="font-size:18px; color:#FFF">500 WPT FEE</b>
            <div style="display:flex; gap:10px; margin-top:20px;">
                <button class="btn" style="flex:1; background:#333; color:#FFF" onclick="closeCheckout()">CANCEL</button>
                <button class="btn" style="flex:1; background:var(--green); color:#FFF" onclick="confirmLaunch()">PAY & DEPLOY</button>
            </div>
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
        let last = 0; let currentToken = null; let selectedTradeAmount = 0;

        function show(p) {
            ['mine','opps','missions','profile','pillars','leader','launcher'].forEach(id=>{
                const el = document.getElementById('p-'+id); if(el) el.style.display=(id===p?'block':'none');
                const nav = document.getElementById('n-'+id); if(nav) nav.classList.toggle('active',id===p);
            });
            if(p==='launcher') loadCommunityTokens();
        }

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}`); const d = await r.json();
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('on-v').innerText = d.online;
                document.getElementById('tot-v').innerText = d.total_users;
                document.getElementById('jk-v').innerText = d.jackpot;
                document.getElementById('pr-n').innerText = d.name;
                document.getElementById('pr-b').innerText = d.badge;
                document.getElementById('pr-m').innerText = "x"+d.multiplier;
                document.getElementById('pr-s').innerText = d.streak + " Days";
                document.getElementById('pr-st').innerText = d.staked;
                document.getElementById('xp-f').style.width = ((d.score % 1000) / 10) + "%";
                document.getElementById('xp-t').innerText = "Next: " + d.next_goal;
                document.getElementById('e-f').style.width = (d.energy / d.max_energy * 100) + "%";
                document.getElementById('e-t').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
            } catch(e) {}
        }

        async function mine(t) {
            const now = Date.now(); if (now - last < 85) return; last = now;
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('light'); refresh(); }
        }

        // --- LAUNCHER JS ---
        function previewFile(inputId, imgId) {
            const file = document.getElementById(inputId).files[0];
            const reader = new FileReader();
            reader.onloadend = () => { const img = document.getElementById(imgId); img.src = reader.result; img.style.display = 'block'; }
            if (file) reader.readAsDataURL(file);
        }

        function openCheckout() {
            const name = document.getElementById('tk-name').value;
            const sym = document.getElementById('tk-sym').value;
            if(!name || !sym) return tg.showAlert("Fill Name & Symbol!");
            document.getElementById('check-info').innerHTML = `<b>Token:</b> ${name} ($${sym})<br><b>Fee:</b> 500 WPT`;
            document.getElementById('m-check').style.display = 'flex';
        }
        function closeCheckout() { document.getElementById('m-check').style.display = 'none'; }

        async function confirmLaunch() {
            const name = document.getElementById('tk-name').value;
            const sym = document.getElementById('tk-sym').value;
            const logo = document.getElementById('pre-logo').src;
            const res = await fetch('/api/launcher/deploy', {method:'POST', body:JSON.stringify({user_id:uid, name, symbol:sym, logo})});
            if(res.ok) {
                tg.showAlert("Success! Token Live."); closeCheckout(); refresh();
                openTokenLive({name, symbol:sym, logo, price:0.0001, holders:1, mcap:1000});
            } else { tg.showAlert("Error: Insufficient WPT"); }
        }

        async function loadCommunityTokens() {
            const r = await fetch('/api/launcher/list'); const tokens = await r.json();
            let html = "";
            tokens.forEach(t => {
                html += `<div class="card" onclick='openTokenLive(${JSON.stringify(t)})'>
                    <div style="display:flex; gap:10px; align-items:center;"><img src="${t.logo}" style="width:30px; border-radius:50%;">
                    <div><b>${t.name}</b><br><small>${t.price} WPT</small></div></div>
                    <div style="text-align:right"><small>MCAP</small><br><b>$${t.mcap}</b></div></div>`;
            });
            document.getElementById('community-tokens-list').innerHTML = html || "<small>No tokens yet</small>";
        }

        function openTokenLive(t) {
            currentToken = t;
            document.getElementById('launch-form').style.display = 'none';
            document.getElementById('token-live-view').style.display = 'block';
            document.getElementById('live-tk-name').innerText = t.name + " ($"+t.symbol+")";
            document.getElementById('live-tk-logo').src = t.logo;
            document.getElementById('live-tk-price').innerText = t.price + " WPT";
            document.getElementById('live-tk-holders').innerText = t.holders;
        }

        function backToLauncher() {
            document.getElementById('launch-form').style.display = 'block';
            document.getElementById('token-live-view').style.display = 'none';
        }

        function setTradePct(pct) {
            const total = parseFloat(document.getElementById('tot').innerText);
            selectedTradeAmount = (total * (pct/100)).toFixed(2);
            tg.HapticFeedback.impactOccurred('medium');
            tg.showAlert("Amount: " + selectedTradeAmount + " WPT");
        }

        function executeTrade(side) {
            if(selectedTradeAmount <= 0) return tg.showAlert("Select amount!");
            tg.showConfirm(`Confirm ${side} ${selectedTradeAmount} WPT?`, (ok)=>{
                if(ok) tg.showAlert("Transaction Processing...");
            });
        }

        tg.expand(); refresh(); setInterval(refresh, 5000);
    </script>
</body>
</html>
    """




# --- BOT SETUP ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🚀 Launch WPT HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]]
    await update.message.reply_text("Welcome to WPT HUB!", reply_markup=InlineKeyboardMarkup(keyboard))

def run_all():
    # Correction : On utilise config.TOKEN comme sur ta photo
    bot_token = getattr(config, 'TOKEN', None)
    
    if bot_token:
        apps = ApplicationBuilder().token(bot_token).build()
        apps.add_handler(CommandHandler("start", start_cmd))
        
        def start_fastapi():
            uvicorn.run(app, host="0.0.0.0", port=8000)
        
        threading.Thread(target=start_fastapi, daemon=True).start()
        print("🤖 Bot & API are running...")
        apps.run_polling()
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run_all()