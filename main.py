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
        if res and (now_ms - (res[2] or 0)) >= 85: 
            cur_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now_s - (res[1] or now_s))/60)*config.REGEN_RATE)
            if cur_e >= 1:
                c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05, energy=%s, last_energy_update=%s, last_click_time=%s WHERE user_id=%s", (cur_e-1, now_s, now_ms, uid))
                conn.commit(); return {"ok": True}
        return JSONResponse(status_code=400)
    finally: c.close(); conn.close()

# --- LAUNCHER API ---

@app.get("/api/launcher/list")
async def api_list_tokens():
    return database.get_community_tokens()

@app.post("/api/launcher/deploy")
async def api_deploy_token(request: Request):
    data = await request.json()
    success, msg = database.deploy_token(
        data.get("user_id"), data.get("name"), data.get("symbol"),
        data.get("desc"), data.get("logo"), data.get("banner"),
        data.get("web"), data.get("x")
    )
    if success: return {"ok": True}
    return JSONResponse(status_code=400, content={"error": msg})

@app.post("/api/launcher/buy")
async def api_buy_token(request: Request):
    data = await request.json()
    success, msg = database.buy_token(data.get("user_id"), data.get("token_id"), float(data.get("amount", 10)))
    if success: return {"ok": True}
    return JSONResponse(status_code=400, content={"error": msg})

@app.post("/api/launcher/sell")
async def api_sell_token(request: Request):
    data = await request.json()
    success, msg = database.sell_token(data.get("user_id"), data.get("token_id")) 
    if success: return {"ok": True, "message": msg}
    return JSONResponse(status_code=400, content={"error": msg})

@app.get("/api/launcher/activity/{tid}")
async def api_get_activity(tid: int):
    # Récupération croisée activité + holders
    activity = database.get_token_activity(tid)
    holders = database.get_token_holders(tid)
    return {"activity": activity, "holders": holders}

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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --green: #34C759; --purple: #A259FF; --red: #FF3B30; --text: #8E8E8E; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 120px; overflow-x: hidden; }
        
        .ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; font-size: 10px; font-weight: bold; }
        .t-wrap { display: inline-block; animation: scroll 25s linear infinite; }
        @keyframes scroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        .balance-card { text-align: center; padding: 30px 20px; border-radius: 25px; background: radial-gradient(circle at top, #1c1c1e, #000); border: 1px solid #222; margin-bottom: 15px; }
        .energy-bar { background: #222; height: 8px; border-radius: 4px; margin: 15px 0; overflow: hidden; }
        .energy-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.4s; }

        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; position: relative; overflow: hidden; }
        .btn { background: #FFF; color: #000; border: none; padding: 12px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 11px; text-transform: uppercase; }

        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 1000; }
        .n-i { font-size: 20px; opacity: 0.3; transition: 0.3s; cursor: pointer; }
        .n-i.active { opacity: 1; color: var(--gold); transform: scale(1.2); }

        .l-input { background: #000; border: 1px solid #333; color: #fff; padding: 12px; border-radius: 12px; width: 100%; margin-bottom: 10px; box-sizing: border-box; font-size: 14px; }
        .preview-banner { height: 120px; background: #222; background-size: cover; background-position: center; border-radius: 15px 15px 0 0; }
        .preview-logo { width: 70px; height: 70px; border-radius: 20px; border: 4px solid var(--card); margin-top: -35px; margin-left: 15px; background: #333; object-fit: cover; }
        
        .act-item { display: flex; justify-content: space-between; font-size: 11px; padding: 8px 0; border-bottom: 1px solid #1a1a1c; align-items: center; }
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
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv" style="font-weight:bold; font-size:18px;">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv" style="font-weight:bold; font-size:18px;">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small style="color:var(--purple)">VEO AI</small><div id="vv" style="font-weight:bold; font-size:18px;">0.00</div></div><button class="btn" onclick="mine('veo')" style="background:var(--purple); color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-launcher" style="display:none">
        <h3 style="text-align:center; color:var(--gold);">🚀 TOKEN LAUNCHER</h3>
        <div id="l-step-config">
            <div class="card" style="flex-direction:column; align-items:stretch; gap:5px;">
                <input type="text" id="tk-name" class="l-input" placeholder="Token Name">
                <input type="text" id="tk-sym" class="l-input" placeholder="Symbol">
                <div style="display:flex; gap:10px; margin-bottom:10px;">
                    <label class="btn" style="flex:1; background:#222; color:#fff; text-align:center;">🖼️ LOGO <input type="file" id="f-logo" hidden accept="image/*" onchange="processFile('logo')"></label>
                    <label class="btn" style="flex:1; background:#222; color:#fff; text-align:center;">📺 BANNER <input type="file" id="f-banner" hidden accept="image/*" onchange="processFile('banner')"></label>
                </div>
                <textarea id="tk-desc" class="l-input" placeholder="Description..."></textarea>
                <input type="text" id="tk-web" class="l-input" placeholder="Website URL">
                <input type="text" id="tk-x" class="l-input" placeholder="Twitter / X Link">
                <button class="btn" style="background:var(--gold); width:100%;" onclick="openPreview()">PREVIEW TOKEN</button>
            </div>
        </div>
        <div id="l-step-preview" style="display:none;">
            <div class="card" style="flex-direction:column; align-items:stretch; padding:0; border:1px solid var(--gold);">
                <div id="pre-banner" class="preview-banner"></div>
                <img id="pre-logo" src="" class="preview-logo">
                <div style="padding:15px;">
                    <h2 id="pre-name" style="margin:0;">Name</h2>
                    <b id="pre-sym" style="color:var(--gold)">$SYM</b>
                    <p id="pre-desc" style="font-size:12px; color:var(--text);"></p>
                </div>
                <div style="padding:10px; display:flex; gap:10px;">
                    <button class="btn" style="flex:1; background:#333; color:#fff;" onclick="backToConfig()">EDIT</button>
                    <button class="btn" style="flex:1; background:var(--green); color:#fff;" onclick="deploy()">LAUNCH (1000 WPT)</button>
                </div>
            </div>
        </div>
        <h4 style="margin:20px 0 10px 5px;">LIVE MARKET</h4>
        <div id="token-list"></div>
    </div>

    <div id="p-token-details" style="display:none; padding-bottom:150px;">
        <div style="position:relative;">
            <div id="det-banner" style="height:130px; background-size:cover; background-position:center; background-color:#111;"></div>
            <button class="btn" onclick="show('launcher')" style="position:absolute; top:10px; left:10px; background:rgba(0,0,0,0.6); color:#fff; border-radius:50%; width:35px; height:35px; padding:0; border:1px solid #444; display:flex; align-items:center; justify-content:center;">←</button>
        </div>
        
        <div style="padding:15px; margin-top:-35px;">
            <div style="display:flex; align-items:flex-end; gap:15px;">
                <img id="det-logo" src="" style="width:70px; height:70px; border-radius:15px; border:3px solid var(--bg); background:#222; object-fit:cover;">
                <div>
                    <h2 id="det-name" style="margin:0; font-size:20px;">Name</h2>
                    <b id="det-sym" style="color:var(--gold); font-size:14px;">$SYM</b>
                </div>
            </div>

            <div class="card" style="margin-top:15px; background:#000; flex-direction:column; align-items:stretch; border-color:#333; padding:12px;">
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:12px;">
                    <span>Price: <b id="det-price" style="color:var(--green)">0.00</b></span>
                    <span>Holders: <b id="det-holders" style="color:var(--blue)">0</b></span>
                </div>
                
                <div style="height:70px; width:100%; background:#0a0a0a; border-radius:8px; margin:5px 0; overflow:hidden; position:relative; border:1px solid #1a1a1c;">
                    <svg viewBox="0 0 100 40" preserveAspectRatio="none" style="width:100%; height:100%; opacity:0.8;">
                        <path d="M0 35 Q 20 32, 35 15 T 60 25 T 100 5" fill="none" stroke="var(--green)" stroke-width="2" />
                    </svg>
                    <div style="position:absolute; top:5px; right:5px; display:flex; gap:4px;">
                        <span style="font-size:8px; padding:2px 5px; background:var(--green); color:#000; border-radius:4px; font-weight:bold;">1m</span>
                        <span style="font-size:8px; padding:2px 5px; background:#1a1a1c; color:#555; border-radius:4px;">5m</span>
                        <span style="font-size:8px; padding:2px 5px; background:#1a1a1c; color:#555; border-radius:4px;">15m</span>
                    </div>
                </div>

                <div class="energy-bar" style="height:8px; margin-top:12px; background:#111;"><div id="det-progress" class="energy-fill" style="background:var(--green)"></div></div>
                <div style="display:flex; justify-content:space-between; margin-top:5px;">
                    <small style="color:var(--text); font-size:9px;">Listing: <span id="det-perc">0%</span></small>
                    <small style="color:var(--text); font-size:9px;">Target: 50k WPT</small>
                </div>
            </div>

            <p id="det-desc" style="color:#aaa; font-size:13px; line-height:1.4; margin:15px 0;"></p>

            <h4 style="margin:20px 0 10px 0; font-size:13px; color:var(--text); text-transform:uppercase; letter-spacing:1px; border-bottom:1px solid #222; padding-bottom:5px;">Live Trades</h4>
            <div id="det-activity"></div>
        </div>

        <div style="position:fixed; bottom:80px; left:0; right:0; padding:15px; background:rgba(5,5,5,0.98); display:flex; gap:10px; border-top:1px solid #222; z-index:1001; backdrop-filter:blur(10px);">
            <button class="btn" style="flex:2; background:var(--green); color:#fff; height:50px; font-size:14px;" onclick="quickBuy(10)">BUY 10</button>
            <button class="btn" style="flex:2; background:var(--green); border:1px solid #fff; color:#fff; height:50px; font-size:14px;" onclick="quickBuy(100)">BUY 100</button>
            <button class="btn" style="flex:1.2; background:var(--red); color:#fff; height:50px; font-size:14px;" onclick="sellToken()">SELL</button>
        </div>
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
        let lastClick = 0, b64_logo = "", b64_banner = "", activeTokenId = null;

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

                let rl = ""; d.top.forEach((u, i) => { 
                    rl += `<div class="card"><span>${i+1}. ${u.n} <small style="color:#555">(${u.b})</small></span><b>${u.p}</b></div>`; 
                });
                document.getElementById('rank-list').innerHTML = rl;
            } catch(e) {}
        }

        function processFile(type) {
            const file = document.getElementById('f-' + type).files[0];
            const reader = new FileReader();
            reader.onloadend = () => {
                if(type === 'logo') b64_logo = reader.result;
                else b64_banner = reader.result;
                tg.HapticFeedback.impactOccurred('medium');
            };
            if(file) reader.readAsDataURL(file);
        }

        function openPreview() {
            if(!document.getElementById('tk-name').value || !b64_logo) return tg.showAlert("Name and Logo are required!");
            document.getElementById('pre-name').innerText = document.getElementById('tk-name').value;
            document.getElementById('pre-sym').innerText = "$" + document.getElementById('tk-sym').value.toUpperCase();
            document.getElementById('pre-desc').innerText = document.getElementById('tk-desc').value;
            document.getElementById('pre-logo').src = b64_logo;
            document.getElementById('pre-banner').style.backgroundImage = `url(${b64_banner})`;
            document.getElementById('l-step-config').style.display = 'none';
            document.getElementById('l-step-preview').style.display = 'block';
        }

        function backToConfig() {
            document.getElementById('l-step-config').style.display = 'block';
            document.getElementById('l-step-preview').style.display = 'none';
        }

        async function deploy() {
            const res = await fetch('/api/launcher/deploy', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    user_id: uid, name: document.getElementById('tk-name').value,
                    symbol: document.getElementById('tk-sym').value, desc: document.getElementById('tk-desc').value,
                    logo: b64_logo, banner: b64_banner, web: document.getElementById('tk-web').value, x: document.getElementById('tk-x').value
                })
            });
            if(res.ok) { tg.showAlert("🚀 Token Launched!"); backToConfig(); show('launcher'); }
            else { const e = await res.json(); tg.showAlert(e.error); }
        }

        async function loadLauncher() {
            const r = await fetch(`/api/launcher/list?t=${Date.now()}`);
            const tokens = await r.json();
            let html = "";
            tokens.forEach(t => {
                html += `<div class="card" onclick='openToken(${JSON.stringify(t)})' style="cursor:pointer">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <img src="${t.logo}" style="width:40px; height:40px; border-radius:8px; object-fit:cover;">
                        <div><b>${t.name}</b><br><small>$${t.sym}</small></div>
                    </div>
                    <div style="text-align:right"><b style="color:var(--green)">${t.price.toFixed(6)}</b><br><small>${(t.mcap || 0).toFixed(1)} WPT</small></div>
                </div>`;
            });
            document.getElementById('token-list').innerHTML = html || "<center style='padding:40px; color:#444;'>No tokens in the market yet.</center>";
        }

        async function openToken(t) {
            activeTokenId = t.id;
            show('token-details');
            
            document.getElementById('det-banner').style.backgroundImage = `url(${t.banner || ''})`;
            document.getElementById('det-logo').src = t.logo;
            document.getElementById('det-name').innerText = t.name;
            document.getElementById('det-sym').innerText = "$" + t.sym;
            document.getElementById('det-desc').innerText = t.desc || "No description provided.";
            document.getElementById('det-price').innerText = t.price.toFixed(6);
            
            let mcap = t.mcap || 0;
            let perc = Math.min((mcap / 50000) * 100, 100);
            document.getElementById('det-progress').style.width = perc + "%";
            document.getElementById('det-perc').innerText = perc.toFixed(1) + "%";

            try {
                const res = await fetch(`/api/launcher/activity/${t.id}?t=${Date.now()}`);
                if(res.ok) {
                    const data = await res.json();
                    document.getElementById('det-holders').innerText = data.holders;
                    
                    let actHtml = "";
                    data.activity.forEach(a => {
                        const color = a.type === 'BUY' ? 'var(--green)' : 'var(--red)';
                        const timeStr = new Date(a.time * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                        actHtml += `
                        <div class="act-item">
                            <span><b style="color:${color}">${a.type}</b> by ${a.name}</span>
                            <span style="color:#555">${timeStr} · <b>${a.amt.toFixed(1)} WPT</b></span>
                        </div>`;
                    });
                    document.getElementById('det-activity').innerHTML = actHtml || "<center style='color:#333; padding:20px;'>No trades detected.</center>";
                }
            } catch(e) { console.error(e); }
        }

        async function quickBuy(amt) {
            const res = await fetch('/api/launcher/buy', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body:JSON.stringify({user_id:uid, token_id:activeTokenId, amount:amt})
            });
            if(res.ok) { 
                tg.HapticFeedback.notificationOccurred('success'); 
                // Petit refresh des données du token
                const rList = await fetch(`/api/launcher/list?t=${Date.now()}`);
                const tokens = await rList.json();
                const updatedToken = tokens.find(tk => tk.id === activeTokenId);
                if(updatedToken) openToken(updatedToken);
            } else { const e = await res.json(); tg.showAlert(e.error); }
        }

        async function sellToken() {
            if(!activeTokenId) return;
            if(!confirm("Sell ALL of your tokens for WPT?")) return;
            const res = await fetch('/api/launcher/sell', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: uid, token_id: activeTokenId})
            });
            const data = await res.json();
            if(res.ok) {
                tg.HapticFeedback.notificationOccurred('success');
                tg.showAlert(data.message);
                show('launcher');
            } else { tg.showAlert(data.error); }
        }

        async function mine(t) {
            const now = Date.now(); if(now - lastClick < 85) return; lastClick = now;
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('light'); refresh(); }
        }

        function show(p) {
            const pages = ['mine', 'launcher', 'rank', 'token-details'];
            pages.forEach(id => {
                const el = document.getElementById('p-' + id);
                if(el) el.style.display = (id === p ? 'block' : 'none');
                const nav = document.getElementById('n-' + id);
                if(nav) nav.classList.toggle('active', id === p);
            });
            if(p === 'launcher') loadLauncher();
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
