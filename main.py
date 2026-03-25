import asyncio, uvicorn, time, json
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

# Variable globale pour accéder au bot depuis les routes API
bot_app = None

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

# --- LAUNCHER & STARS PAYMENT API ---

@app.get("/api/launcher/list")
async def api_list_tokens():
    return database.get_community_tokens()

@app.post("/api/launcher/create-invoice")
async def api_create_invoice(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    name = data.get("name")
    
    # On prépare le payload avec les infos du token pour les récupérer après paiement
    # On limite la taille du payload (max 128 chars pour Telegram)
    token_data = {
        "uid": uid, "n": name, "s": data.get("symbol"), "d": data.get("desc")[:50],
        "l": data.get("logo")[:20], "b": data.get("banner")[:20], # On stockera le reste en DB temporaire si besoin
        "w": data.get("web"), "x": data.get("x")
    }
    
    try:
        # Génération du lien de paiement Stars (XTR)
        link = await bot_app.bot.create_invoice_link(
            title=f"Deploy {name}",
            description=f"Launch your community token on WPT Launcher",
            payload=json.dumps(token_data),
            provider_token="", # Vide pour les Stars
            currency="XTR",
            prices=[LabeledPrice("Deployment Fee", config.DEPLOY_FEE_STARS)]
        )
        return {"ok": True, "link": link}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.post("/api/launcher/buy")
async def api_buy_token(request: Request):
    data = await request.json()
    success, msg = database.buy_token(data.get("user_id"), data.get("token_id"), float(data.get("amount", 10)))
    return {"ok": success, "error": msg if not success else None}

@app.post("/api/launcher/sell")
async def api_sell_token(request: Request):
    data = await request.json()
    success, msg = database.sell_token(data.get("user_id"), data.get("token_id")) 
    return {"ok": success, "message": msg}

@app.get("/api/launcher/activity/{tid}")
async def api_get_activity(tid: int):
    return {"activity": database.get_token_activity(tid), "holders": database.get_token_holders(tid)}

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
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; position: relative; }
        .btn { background: #FFF; color: #000; border: none; padding: 12px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 11px; text-transform: uppercase; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 1000; }
        .n-i { font-size: 20px; opacity: 0.3; transition: 0.3s; cursor: pointer; }
        .n-i.active { opacity: 1; color: var(--gold); transform: scale(1.2); }
        .l-input { background: #000; border: 1px solid #333; color: #fff; padding: 12px; border-radius: 12px; width: 100%; margin-bottom: 10px; box-sizing: border-box; font-size: 14px; }
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
            <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--gold)"><span>ENERGY</span><span id="e-t">0 / 100</span></div>
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
                <button class="btn" style="background:var(--gold); width:100%;" onclick="deployWithStars()">LAUNCH (★ STARS)</button>
            </div>
        </div>
        <div id="token-list" style="margin-top:20px;"></div>
    </div>

    <div id="p-token-details" style="display:none; padding-bottom:150px;">
        <button class="btn" onclick="show('launcher')" style="margin-bottom:10px;">← BACK</button>
        <div id="det-banner" style="height:120px; background-size:cover; border-radius:15px;"></div>
        <div style="padding:15px; margin-top:-30px; display:flex; align-items:flex-end; gap:15px;">
            <img id="det-logo" style="width:70px; height:70px; border-radius:15px; border:3px solid var(--bg); background:#222;">
            <div><h2 id="det-name" style="margin:0;"></h2><b id="det-sym" style="color:var(--gold);"></b></div>
        </div>
        <div class="card" style="margin-top:15px; flex-direction:column; align-items:stretch;">
            <div style="display:flex; justify-content:space-between; font-size:12px;">
                <span>Price: <b id="det-price" style="color:var(--green)"></b></span>
                <span>Holders: <b id="det-holders" style="color:var(--blue)"></b></span>
            </div>
            <p id="det-desc" style="font-size:13px; color:#aaa;"></p>
            <div style="display:flex; gap:10px; margin-top:10px;">
                <button class="btn" style="flex:1; background:var(--green); color:#fff;" onclick="quickBuy(10)">BUY 10</button>
                <button class="btn" style="flex:1; background:var(--red); color:#fff;" onclick="sellToken()">SELL ALL</button>
            </div>
        </div>
        <div id="det-activity" style="margin-top:20px;"></div>
    </div>

    <nav class="nav">
        <div onclick="show('mine')" id="n-mine" class="n-i active">🏠</div>
        <div onclick="show('launcher')" id="n-launcher" class="n-i">🚀</div>
    </nav>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let b64_logo = "", b64_banner = "", activeTokenId = null;

        async function refresh() {
            const r = await fetch(`/api/user/${uid}`);
            const d = await r.json();
            document.getElementById('tot').innerText = d.score.toFixed(2);
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('e-f').style.width = (d.energy/d.max_energy*100) + "%";
            document.getElementById('e-t').innerText = `${d.energy} / ${d.max_energy}`;
        }

        function processFile(type) {
            const file = document.getElementById('f-' + type).files[0];
            const reader = new FileReader();
            reader.onloadend = () => { if(type==='logo') b64_logo=reader.result; else b64_banner=reader.result; };
            if(file) reader.readAsDataURL(file);
        }

        async function deployWithStars() {
            const name = document.getElementById('tk-name').value;
            if(!name || !b64_logo) return tg.showAlert("Name and Logo required!");
            
            const res = await fetch('/api/launcher/create-invoice', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({
                    user_id:uid, name:name, symbol:document.getElementById('tk-sym').value,
                    desc:document.getElementById('tk-desc').value, logo:b64_logo, banner:b64_banner,
                    web:document.getElementById('tk-web').value, x:document.getElementById('tk-x').value
                })
            });
            const data = await res.json();
            if(data.ok) {
                tg.openInvoice(data.link, function(status) {
                    if(status==='paid') { tg.showAlert("✅ Success! Token will appear shortly."); show('launcher'); }
                });
            }
        }

        async function loadLauncher() {
            const r = await fetch('/api/launcher/list');
            const tokens = await r.json();
            let html = "";
            tokens.forEach(t => {
                html += `<div class="card" onclick='openToken(${JSON.stringify(t)})'>
                    <div style="display:flex; align-items:center; gap:10px;"><img src="${t.logo}" style="width:40px;height:40px;border-radius:8px;"><b>${t.name}</b></div>
                    <div style="text-align:right"><b>${t.price.toFixed(6)}</b></div></div>`;
            });
            document.getElementById('token-list').innerHTML = html;
        }

        async function openToken(t) {
            activeTokenId = t.id; show('token-details');
            document.getElementById('det-banner').style.backgroundImage = `url(${t.banner})`;
            document.getElementById('det-logo').src = t.logo;
            document.getElementById('det-name').innerText = t.name;
            document.getElementById('det-sym').innerText = "$"+t.sym;
            document.getElementById('det-price').innerText = t.price.toFixed(6);
            document.getElementById('det-desc').innerText = t.desc;
            const res = await fetch(`/api/launcher/activity/${t.id}`);
            const data = await res.json();
            document.getElementById('det-holders').innerText = data.holders;
        }

        async function mine(t) {
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('light'); refresh(); }
        }

        function show(p) {
            ['mine', 'launcher', 'token-details'].forEach(id => {
                document.getElementById('p-' + id).style.display = (id === p ? 'block' : 'none');
                if(document.getElementById('n-' + id)) document.getElementById('n-' + id).classList.toggle('active', id === p);
            });
            if(p === 'launcher') loadLauncher();
        }

        tg.expand(); refresh();
    </script>
</body>
</html>
"""

# --- BOT HANDLERS ---

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    await missions.register_user(uid, name, None)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to the WPT HUB! Ready to earn?", reply_markup=kb)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Obligatoire : On valide que le serveur est prêt à recevoir le paiement
    await update.pre_checkout_query.answer(ok=True)

async def success_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # C'est ici que l'on crée le token en base de données après le paiement réussi
    payload = json.loads(update.message.successful_payment.invoice_payload)
    
    # On utilise database.deploy_token mais on saute la vérification du solde WPT 
    # (ou on adapte database.py pour accepter le paiement Stars)
    # Pour l'instant, on appelle directement l'insertion
    database.deploy_token(
        payload['uid'], payload['n'], payload['s'], payload['d'],
        payload['l'], payload['b'], payload['w'], payload['x']
    )
    await update.message.reply_text(f"✅ Awesome! Your token '{payload['n']}' is now LIVE on the market!")

async def main():
    global bot_app
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    
    # Handlers Bot
    bot_app.add_handler(CommandHandler("start", start_cmd))
    bot_app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    bot_app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, success_payment_callback))
    
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    
    # Lancement Serveur Web
    conf = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    await uvicorn.Server(conf).serve()

if __name__ == "__main__":
    asyncio.run(main())
