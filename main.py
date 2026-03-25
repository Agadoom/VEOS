import asyncio, uvicorn, time, json, uuid
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters

import config, database, missions

# --- INITIALISATION ---
database.init_db_structure()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Stockage temporaire pour les tokens (images lourdes) en attente de paiement
pending_tokens = {}
bot_instance = None

# --- API ROUTES ---

@app.get("/api/user/{uid}")
async def api_get_user(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={})
    
    # Calcul énergie et score
    now = int(time.time())
    last_update = r[6] if r[6] is not None else now
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_update) / 60) * config.REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, _, _ = missions.get_badge_info(score)
    
    # Stats réseau
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE last_energy_update > %s", (now - 300,))
    online = max(1, c.fetchone()[0])
    jk = database.get_total_network_score() * 0.1
    
    # Assets du profil
    c.execute("SELECT t.name, t.symbol, a.amount FROM user_community_assets a JOIN community_tokens t ON a.token_id = t.id WHERE a.user_id = %s AND a.amount > 0", (uid,))
    assets = [{"n": x[0], "s": x[1], "a": float(x[2])} for x in c.fetchall()]
    c.close(); conn.close()

    return {
        "uid": uid, "name": r[4], "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0,
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "score": round(score, 2),
        "badge": badge, "jackpot": round(jk, 2), "online": online, "assets": assets
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    database.mine_points(data.get("user_id"), data.get("token"))
    return {"ok": True}

@app.get("/api/launcher/list")
async def api_list_tokens():
    return database.get_community_tokens()

@app.post("/api/launcher/save-pending")
async def save_pending(request: Request):
    data = await request.json()
    temp_id = str(uuid.uuid4())[:8]
    pending_tokens[temp_id] = data
    return {"ok": True, "temp_id": temp_id}

@app.post("/api/launcher/create-invoice")
async def api_create_invoice(request: Request):
    data = await request.json()
    temp_id = data.get("temp_id")
    token = pending_tokens.get(temp_id)
    if not token: return JSONResponse(status_code=400, content={"error": "Session expired"})
    
    link = await bot_instance.bot.create_invoice_link(
        title=f"Deploy ${token['symbol']}",
        description=f"Fee for {token['name']}",
        payload=temp_id,
        provider_token="", currency="XTR",
        prices=[LabeledPrice("Launch Fee", config.DEPLOY_FEE_STARS)]
    )
    return {"ok": True, "link": link}

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
        :root { --bg: #050505; --card: #121214; --gold: #FFD700; --blue: #007AFF; --green: #34C759; --purple: #A259FF; --text: #8E8E8E; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 0; user-select: none; }
        
        .ticker { background: #1a1a1c; padding: 10px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; font-size: 11px; font-weight: bold; }
        .t-wrap { display: inline-block; animation: scroll 20s linear infinite; }
        @keyframes scroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        .container { padding: 15px; padding-bottom: 120px; }
        .main-card { background: radial-gradient(circle at top right, #1c1c1e, #050505); border-radius: 25px; padding: 25px; text-align: center; border: 1px solid #222; margin-bottom: 15px; }
        
        .energy-bar { background: #222; height: 8px; border-radius: 10px; margin: 15px 0; overflow: hidden; }
        .energy-fill { background: var(--gold); height: 100%; width: 0%; transition: 0.4s; }

        .card { background: var(--card); border-radius: 20px; padding: 15px; margin-bottom: 10px; border: 1px solid #1c1c1e; display: flex; justify-content: space-between; align-items: center; }
        .btn { background: #FFF; color: #000; border: none; padding: 12px 20px; border-radius: 12px; font-weight: 800; cursor: pointer; transition: 0.2s; }
        .btn:active { transform: scale(0.95); }

        /* Navigation Fixée */
        .nav { position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); background: rgba(20,20,20,0.9); backdrop-filter: blur(15px); padding: 12px 35px; border-radius: 50px; display: flex; gap: 40px; border: 1px solid #333; z-index: 9999; }
        .n-i { font-size: 26px; opacity: 0.2; transition: 0.3s; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .n-i.active { opacity: 1; color: var(--gold); transform: translateY(-5px); }

        .l-input { background: #000; border: 1px solid #222; color: #fff; padding: 14px; border-radius: 14px; width: 100%; margin-bottom: 10px; box-sizing: border-box; }
        .page { display: none; animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    </style>
</head>
<body>
    <div class="ticker"><div class="t-wrap">
        <span style="margin-right:50px; color:var(--gold)">🏆 JACKPOT: <span id="jk-v">0</span> WPT</span>
        <span style="color:var(--green)">● NETWORK: <span id="on-v">0</span> ONLINE</span>
    </div></div>

    <div class="container">
        <div id="p-mine" class="page" style="display:block;">
            <div class="main-card">
                <div id="u-badge" style="color:var(--gold); font-size:12px; font-weight:bold;">...</div>
                <h1 id="tot" style="font-size:50px; margin:10px 0;">0.00</h1>
                <div class="energy-bar"><div id="e-f" class="energy-fill"></div></div>
                <small id="e-t" style="color:var(--text)">0 / 100</small>
            </div>
            <div class="card"><div><b>Genesis</b><br><small id="gv">0.00</small></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
            <div class="card"><div><b>Unity</b><br><small id="uv">0.00</small></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
            <div class="card" style="border-left: 4px solid var(--purple);"><div><b style="color:var(--purple)">Veo AI</b><br><small id="vv">0.00</small></div><button class="btn" style="background:var(--purple); color:#fff;" onclick="mine('veo')">COMPUTE</button></div>
        </div>

        <div id="p-launcher" class="page">
            <h2 style="text-align:center;">🚀 LAUNCHER</h2>
            <div class="card" style="flex-direction:column; align-items:stretch;">
                <input type="text" id="tk-name" class="l-input" placeholder="Token Name">
                <input type="text" id="tk-sym" class="l-input" placeholder="Symbol (ex: WPT)">
                <textarea id="tk-desc" class="l-input" placeholder="Description..."></textarea>
                <div style="display:flex; gap:10px; margin-bottom:10px;">
                    <label class="btn" style="flex:1; background:#222; color:#fff; text-align:center;">🖼️ LOGO <input type="file" id="f-logo" hidden accept="image/*" onchange="processFile('logo')"></label>
                    <label class="btn" style="flex:1; background:#222; color:#fff; text-align:center;">📺 BANNER <input type="file" id="f-banner" hidden accept="image/*" onchange="processFile('banner')"></label>
                </div>
                <button class="btn" style="background:var(--gold); width:100%; padding:15px;" onclick="deployStars()">LAUNCH (★ STARS)</button>
            </div>
            <div id="token-list"></div>
        </div>

        <div id="p-details" class="page">
            <button class="btn" onclick="show('launcher')" style="margin-bottom:15px; background:#222; color:#fff;">← BACK</button>
            <div id="det-banner" style="height:140px; border-radius:20px; background-size:cover; background-color:#1a1a1c;"></div>
            <div style="display:flex; align-items:flex-end; gap:15px; margin-top:-40px; padding:0 15px;">
                <img id="det-logo" style="width:70px; height:70px; border-radius:20px; border:4px solid #000; background:#222;">
                <div><h2 id="det-name" style="margin:0;"></h2><b id="det-sym" style="color:var(--gold)"></b></div>
            </div>
            <p id="det-desc" style="padding:15px; color:var(--text); font-size:14px; line-height:1.4;"></p>
            <div class="card" style="background:#000; flex-direction:column;">
                <div style="display:flex; justify-content:space-between; width:100%;">
                    <span>Price: <b id="det-price" style="color:var(--green)"></b></span>
                    <span>Holders: <b id="det-holders" style="color:var(--blue)">0</b></span>
                </div>
                <button class="btn" style="background:var(--green); color:#fff; width:100%; margin-top:15px;" onclick="tg.showAlert('Buying system coming with TON Connect!')">BUY TOKEN</button>
            </div>
        </div>

        <div id="p-profil" class="page">
            <div class="main-card">
                <div style="font-size:60px;">💎</div>
                <h2 id="prof-name">...</h2>
                <div id="prof-badge" style="color:var(--gold); font-weight:bold;">...</div>
            </div>
            <h4 style="margin-left:10px;">MY WALLET</h4>
            <div id="prof-assets"></div>
        </div>
    </div>

    <nav class="nav">
        <div onclick="show('mine')" id="n-mine" class="n-i active">🏠</div>
        <div onclick="show('launcher')" id="n-launcher" class="n-i">🚀</div>
        <div onclick="show('profil')" id="n-profil" class="n-i">👤</div>
    </nav>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let b64_logo = "", b64_banner = "";

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}`);
                const d = await r.json();
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('jk-v').innerText = d.jackpot;
                document.getElementById('on-v').innerText = d.online;
                document.getElementById('u-badge').innerText = d.badge.toUpperCase();
                document.getElementById('prof-name').innerText = d.name;
                document.getElementById('prof-badge').innerText = d.badge.toUpperCase();
                document.getElementById('e-f').style.width = (d.energy/d.max_energy*100) + "%";
                document.getElementById('e-t').innerText = `${Math.floor(d.energy)} / ${d.max_energy}`;

                let ah = ""; d.assets.forEach(a => {
                    ah += `<div class="card"><span>${a.n} ($${a.s})</span><b>${a.a.toFixed(2)}</b></div>`;
                });
                document.getElementById('prof-assets').innerHTML = ah || "<center style='color:#444; margin-top:20px;'>No tokens held</center>";
            } catch(e) {}
        }

        function show(pageId) {
            // Masquer toutes les pages
            document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
            // Afficher la page demandée
            document.getElementById('p-' + pageId).style.display = 'block';
            
            // Gérer l'état de la navigation
            document.querySelectorAll('.n-i').forEach(nav => nav.classList.remove('active'));
            const activeNav = document.getElementById('n-' + pageId);
            if(activeNav) activeNav.classList.add('active');

            // Actions spécifiques
            if(pageId === 'launcher') loadMarket();
            refresh();
            tg.HapticFeedback.impactOccurred('light');
        }

        function processFile(type) {
            const file = document.getElementById('f-' + type).files[0];
            const reader = new FileReader();
            reader.onloadend = () => { if(type==='logo') b64_logo=reader.result; else b64_banner=reader.result; };
            if(file) reader.readAsDataURL(file);
        }

        async function deployStars() {
            const name = document.getElementById('tk-name').value;
            const sym = document.getElementById('tk-sym').value;
            if(!name || !b64_logo) return tg.showAlert("Logo and Name are required!");

            const save = await fetch('/api/launcher/save-pending', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({
                    user_id:uid, name:name, symbol:sym,
                    desc:document.getElementById('tk-desc').value, logo:b64_logo, banner:b64_banner
                })
            });
            const sData = await save.json();

            const res = await fetch('/api/launcher/create-invoice', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({temp_id: sData.temp_id})
            });
            const data = await res.json();
            if(data.ok) tg.openInvoice(data.link, (status) => { if(status==='paid') show('launcher'); });
        }

        async function loadMarket() {
            const r = await fetch('/api/launcher/list');
            const tokens = await r.json();
            let h = "";
            tokens.forEach(t => {
                h += `<div class="card" onclick='openToken(${JSON.stringify(t)})'>
                    <div style="display:flex; align-items:center; gap:12px;">
                        <img src="${t.logo}" style="width:40px;height:40px;border-radius:10px;">
                        <b>${t.name} <br><small style="color:var(--text)">$${t.sym}</small></b>
                    </div>
                    <b style="color:var(--green)">${t.price.toFixed(6)}</b>
                </div>`;
            });
            document.getElementById('token-list').innerHTML = h || "<center style='color:#444; margin-top:20px;'>Market empty</center>";
        }

        async function openToken(t) {
            show('details');
            document.getElementById('det-banner').style.backgroundImage = `url(${t.banner})`;
            document.getElementById('det-logo').src = t.logo;
            document.getElementById('det-name').innerText = t.name;
            document.getElementById('det-sym').innerText = "$"+t.sym;
            document.getElementById('det-desc').innerText = t.desc || "Community token launched on WPT.";
            document.getElementById('det-price').innerText = t.price.toFixed(6);
            const res = await fetch(`/api/launcher/activity/${t.id}`);
            const d = await res.json();
            document.getElementById('det-holders').innerText = d.holders;
        }

        async function mine(t) {
            await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            refresh();
            tg.HapticFeedback.impactOccurred('medium');
        }

        tg.expand();
        refresh();
        setInterval(refresh, 5000); // Auto-refresh every 5s
    </script>
</body>
</html>
"""

# --- BOT ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 ENTER HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text("Welcome back! Ready to manage your tokens?", reply_markup=kb)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    temp_id = update.message.successful_payment.invoice_payload
    data = pending_tokens.get(temp_id)
    if data:
        database.deploy_token(data['user_id'], data['name'], data['symbol'], data['desc'], data['logo'], data['banner'], "", "")
        del pending_tokens[temp_id]
        await update.message.reply_text(f"✅ Your token {data['name']} is now live!")

async def main():
    global bot_instance
    bot_instance = ApplicationBuilder().token(config.TOKEN).build()
    bot_instance.add_handler(CommandHandler("start", start_cmd))
    bot_instance.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    bot_instance.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, success_payment_callback))
    
    await bot_instance.initialize(); await bot_instance.start(); await bot_instance.updater.start_polling()
    conf = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    await uvicorn.Server(conf).serve()

if __name__ == "__main__":
    asyncio.run(main())
