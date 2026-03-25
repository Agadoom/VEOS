import asyncio, uvicorn, time, json, uuid, random
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

pending_tokens = {}
bot_instance = None

# --- API ROUTES ---

@app.get("/api/user/{uid}")
async def api_get_user(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={})
    now = int(time.time()); last_update = r[6] if r[6] is not None else now
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_update) / 60) * config.REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, _, _ = missions.get_badge_info(score)
    online, _, jk = (1, 1, score * 0.1)
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT t.name, t.symbol, a.amount FROM user_community_assets a JOIN community_tokens t ON a.token_id = t.id WHERE a.user_id = %s AND a.amount > 0", (uid,))
    assets = [{"n": x[0], "s": x[1], "a": float(x[2])} for x in c.fetchall()]
    c.close(); conn.close()
    return {"uid": uid, "name": r[4], "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "energy": int(current_e), "max_energy": config.MAX_ENERGY, "score": round(score, 2), "badge": badge, "jackpot": round(jk, 2), "online": online, "assets": assets}

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

@app.get("/api/launcher/list")
async def api_list_tokens():
    return database.get_community_tokens()

@app.post("/api/launcher/save-pending")
async def save_pending(request: Request):
    data = await request.json()
    temp_id = str(uuid.uuid4())[:8]
    pending_tokens[temp_id] = data
    return {"ok": True, "temp_id": temp_id}

@app.post("/api/launcher/buy-request")
async def api_buy_request(request: Request):
    data = await request.json()
    uid, tid, qty = data.get("user_id"), data.get("token_id"), float(data.get("qty", 100))
    
    # 1. Vérifier si l'user a assez de WPT (Score global ou Genesis)
    r = database.get_user_full(uid)
    if (r[0] or 0) < 50: # Exemple: l'achat coûte 50 WPT
        return JSONResponse(status_code=400, content={"error": "Pas assez de WPT"})

    # 2. Créer la facture Stars pour les FRAIS de réseau/service (ex: 10 Stars)
    payload = f"buy|{uid}|{tid}|{qty}|50" # buy|user|token|quantité|prix_wpt
    link = await bot_instance.bot.create_invoice_link(
        title="Frais d'achat Token",
        description=f"Frais de service pour {qty} tokens",
        payload=payload, provider_token="", currency="XTR",
        prices=[LabeledPrice("Service Fee", 10)] # Frais en Stars
    )
    return {"ok": True, "link": link}

# Dans success_payment_callback du Bot :
async def success_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    
    if payload.startswith("buy|"):
        _, uid, tid, qty, cost_wpt = payload.split('|')
        conn = database.get_db_conn(); c = conn.cursor()
        # On déduit les WPT et on ajoute le token
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (float(cost_wpt), uid))
        database.buy_token(int(uid), int(tid), float(qty))
        await update.message.reply_text("✅ Achat réussi : Frais payés (Stars) et WPT déduits !")


@app.get("/api/launcher/chart/{tid}")
async def get_chart_data(tid: int):
    points = [random.uniform(0.0001, 0.0005) for _ in range(12)]
    points.sort() 
    return {"points": points}

@app.post("/api/launcher/sell")
async def api_sell_token(request: Request):
    data = await request.json()
    uid, tid, qty = data.get("user_id"), data.get("token_id"), float(data.get("amount", 0))
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT amount FROM user_community_assets WHERE user_id=%s AND token_id=%s", (uid, tid))
    res = c.fetchone()
    if not res or res[0] < qty: return JSONResponse(status_code=400, content={"error": "Not enough tokens"})
    c.execute("SELECT price FROM community_tokens WHERE id=%s", (tid,))
    price = c.fetchone()[0]
    gain = qty * price
    c.execute("UPDATE user_community_assets SET amount = amount - %s WHERE user_id=%s AND token_id=%s", (qty, uid, tid))
    c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id=%s", (gain, uid))
    conn.commit(); c.close(); conn.close()
    return {"ok": True, "gain": gain}

@app.post("/api/launcher/create-invoice")
async def api_create_invoice(request: Request):
    data = await request.json()
    temp_id = data.get("temp_id")
    token = pending_tokens.get(temp_id)
    link = await bot_instance.bot.create_invoice_link(title=f"Launch {token['symbol']}", description="Creation fee", payload=temp_id, provider_token="", currency="XTR", prices=[LabeledPrice("Launch Fee", 500)])
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
        :root { --bg: #050505; --card: #121214; --gold: #FFD700; --blue: #007AFF; --green: #34C759; --red: #eb4034; --text: #8E8E8E; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 0; overflow: hidden; }
        .ticker { background: #1a1a1c; padding: 8px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; font-size: 11px; }
        .t-wrap { display: inline-block; animation: scroll 20s linear infinite; }
        @keyframes scroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
        .container { padding: 15px; padding-bottom: 100px; height: 90vh; overflow-y: auto; }
        .prof-header { background: linear-gradient(135deg, #1c1c1e 0%, #050505 100%); border-radius: 30px; padding: 30px 20px; border: 1px solid #222; margin-bottom: 20px; text-align: center; }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 20px; }
        .stat-card { background: #161618; padding: 15px; border-radius: 20px; border: 1px solid #222; }
        .card { background: var(--card); border-radius: 20px; padding: 15px; margin-bottom: 12px; border: 1px solid #1c1c1e; display: flex; justify-content: space-between; align-items: center; }
        .btn { background: #FFF; color: #000; border: none; padding: 12px 20px; border-radius: 14px; font-weight: 800; cursor: pointer; transition: 0.2s; }
        .btn:active { transform: scale(0.95); opacity: 0.8; }
        .nav { position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.95); backdrop-filter: blur(15px); padding: 12px 35px; border-radius: 50px; display: flex; gap: 40px; border: 1px solid #333; z-index: 999; }
        .n-i { font-size: 24px; opacity: 0.3; transition: 0.3s; cursor:pointer; }
        .n-i.active { opacity: 1; color: var(--gold); transform: scale(1.1); }
        .page { display: none; }
        .active-page { display: block; }
        .l-input { background: #000; border: 1px solid #333; color: #fff; padding: 12px; border-radius: 12px; width: 100%; box-sizing: border-box; }
    </style>
</head>
<body>
    <div class="ticker"><div class="t-wrap">
        <span style="margin-right:50px; color:var(--gold)">🏆 JACKPOT: <span id="jk-v">0</span> WPT</span>
        <span style="color:var(--green)">● NETWORK ONLINE</span>
    </div></div>

    <div class="container">
        <div id="p-mine" class="page active-page">
            <div class="prof-header">
                <small id="u-badge" style="color:var(--gold); font-weight:bold; letter-spacing:1px;"></small>
                <h1 id="tot" style="font-size:50px; margin:10px 0;">0.00</h1>
                <div style="background:#222; height:6px; border-radius:10px; margin:15px 0;"><div id="e-f" style="background:var(--gold); height:100%; width:0%; border-radius:10px; transition:0.3s;"></div></div>
                <small id="e-t" style="color:var(--text)">Energy: 0/100</small>
            </div>
            <div class="card"><div><b>Genesis</b><br><small id="gv">0.00</small></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
            <div class="card"><div><b>Unity</b><br><small id="uv">0.00</small></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
            <div class="card"><div><b style="color:var(--purple)">Veo AI</b><br><small id="vv">0.00</small></div><button class="btn" style="background:var(--purple); color:#fff;" onclick="mine('veo')">COMPUTE</button></div>
        </div>

        <div id="p-launcher" class="page">
            <h2 style="text-align:center; margin-bottom:20px;">🚀 TOKEN LAUNCHPAD</h2>
            <div class="card" style="flex-direction:column; align-items:stretch; gap:12px; background:linear-gradient(to bottom, #121214, #000);">
                <div style="display:flex; gap:10px;">
                    <input type="text" id="tk-name" class="l-input" placeholder="Token Name">
                    <input type="text" id="tk-sym" class="l-input" style="width:100px" placeholder="$SYM">
                </div>
                <textarea id="tk-desc" class="l-input" style="height:60px" placeholder="Describe your project..."></textarea>
                <div style="display:flex; gap:10px;">
                    <label class="btn" style="flex:1; background:#222; color:#fff; font-size:11px; text-align:center;">LOGO<input type="file" id="f-logo" hidden onchange="processFile('logo')"></label>
                    <label class="btn" style="flex:1; background:#222; color:#fff; font-size:11px; text-align:center;">BANNER<input type="file" id="f-banner" hidden onchange="processFile('banner')"></label>
                </div>
                <button class="btn" style="background:var(--gold); padding:15px;" onclick="deployStars()">LAUNCH FOR 500 ★</button>
            </div>
            <h3 style="margin-left:5px;">🔥 LIVE MARKET</h3>
            <div id="token-list"></div>
        </div>

        <div id="p-details" class="page">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <button class="btn" onclick="show('launcher')" style="background:#222; color:#fff;">← BACK</button>
                <b id="det-price-top" style="color:var(--green); font-family:monospace;">0.000000</b>
            </div>
            <div id="det-banner" style="height:140px; border-radius:20px; background-size:cover; position:relative; background-color:#1a1a1c;">
                <img id="det-logo" style="width:70px; height:70px; border-radius:20px; border:4px solid #000; position:absolute; bottom:-30px; left:20px; background:#222;">
            </div>
            <div style="margin-top:40px; padding:0 15px;">
                <h2 id="det-name" style="margin:0;"></h2>
                <b id="det-sym" style="color:var(--gold)"></b>
            </div>
            <div style="padding:15px;">
                <svg id="price-chart" viewBox="0 0 300 100" style="width:100%; height:120px; background:#0a0a0a; border-radius:15px; border:1px solid #222;">
                    <line x1="0" y1="25" x2="300" y2="25" stroke="#1a1a1c" />
                    <line x1="0" y1="50" x2="300" y2="50" stroke="#1a1a1c" />
                    <line x1="0" y1="75" x2="300" y2="75" stroke="#1a1a1c" />
                    <polyline id="chart-line" fill="none" stroke="#34C759" stroke-width="2.5" points="0,100 300,100" />
                </svg>
            </div>
            <p id="det-desc" style="padding:0 15px; color:var(--text); font-size:13px;"></p>
            <div style="display:flex; gap:10px; padding:15px;">
                <button class="btn" style="flex:1; background:var(--green); color:#fff;" onclick="buyTokenStars()">BUY</button>
                <button class="btn" style="flex:1; background:var(--red); color:#fff;" onclick="sellToken()">SELL</button>
            </div>
            <div class="card" style="margin:0 15px; background:transparent; border:none;">
                <span>Holders: <b id="det-holders" style="color:var(--blue)">0</b></span>
                <span>Liquidity: <b style="color:var(--gold)">Locked</b></span>
            </div>

<div style="display:flex; flex-direction:column; gap:10px; padding:15px;">
    <div style="display:flex; gap:10px;">
        <button class="btn" style="flex:1; background:var(--green); color:#fff;" onclick="buyTokenStars()">BUY (WPT + Stars)</button>
        <button class="btn" style="flex:1; background:var(--red); color:#fff;" onclick="sellToken()">SELL</button>
    </div>
    <button class="btn" style="background:#222; color:var(--blue); border:1px solid var(--blue);" onclick="withdrawToken()">📤 WITHDRAW TO EXTERNAL WALLET</button>
</div>


        </div>

        <div id="p-profil" class="page">
            <div class="prof-header">
                <div style="font-size:50px;">💎</div>
                <h2 id="prof-name">User</h2>
                <div id="prof-badge" style="color:var(--gold); font-size:12px; font-weight:bold;">RANK: NOVICE</div>
                <div class="stat-grid">
                    <div class="stat-card"><small style="color:var(--text)">TOTAL SCORE</small><div id="prof-score">0</div></div>
                    <div class="stat-card"><small style="color:var(--text)">RANKING</small><div style="color:var(--blue)">#124</div></div>
                </div>
            </div>
            <h3 style="margin-left:10px;">📦 MY WALLET</h3>
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
        let b64_logo = "", b64_banner = "", currentTokenId = null;

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}`);
                const d = await r.json();
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('jk-v').innerText = d.jackpot;
                document.getElementById('u-badge').innerText = d.badge.toUpperCase();
                document.getElementById('prof-name').innerText = d.name;
                document.getElementById('prof-score').innerText = d.score.toFixed(0);
                document.getElementById('prof-badge').innerText = "RANK: " + d.badge.toUpperCase();
                document.getElementById('e-f').style.width = (d.energy/d.max_energy*100) + "%";
                document.getElementById('e-t').innerText = `Energy: ${Math.floor(d.energy)} / ${d.max_energy}`;
                let ah = ""; d.assets.forEach(a => { ah += `<div class="card"><span>${a.n} ($${a.s})</span><b>${a.a.toFixed(2)}</b></div>`; });
                document.getElementById('prof-assets').innerHTML = ah || "<center style='color:#444; padding:20px;'>No tokens</center>";
            } catch(e) {}
        }

        async function mine(t) {
            const res = await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('medium'); refresh(); }
            else { tg.showAlert("Wait or Low Energy"); }
        }

        async function openToken(t) {
            currentTokenId = t.id;
            show('details');
            document.getElementById('det-banner').style.backgroundImage = `url(${t.banner || ''})`;
            document.getElementById('det-logo').src = t.logo;
            document.getElementById('det-name').innerText = t.name;
            document.getElementById('det-sym').innerText = "$" + t.sym;
            document.getElementById('det-desc').innerText = t.desc || "Community token.";
            document.getElementById('det-price-top').innerText = t.price.toFixed(6);
            const cRes = await fetch(`/api/launcher/chart/${t.id}`);
            const cData = await cRes.json();
            drawChart(cData.points);
        }

        function drawChart(points) {
            const poly = document.getElementById('chart-line');
            const max = Math.max(...points), min = Math.min(...points);
            let ptsString = "";
            points.forEach((p, i) => {
                const x = (i / (points.length - 1)) * 300;
                const y = 100 - ((p - min) / (max - min) * 80 + 10);
                ptsString += `${x},${y} `;
            });
            poly.setAttribute("points", ptsString);
        }

        async function buyTokenStars() {
            if(!currentTokenId) return;
            const res = await fetch('/api/launcher/buy-stars', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({user_id: uid, token_id: currentTokenId})});
            const data = await res.json();
            if(data.ok) tg.openInvoice(data.link, (status) => { if(status==='paid') show('profil'); });
        }

        async function sellToken() {
            const qty = prompt("Amount to sell?");
            if (!qty || isNaN(qty) || qty <= 0) return;
            const res = await fetch('/api/launcher/sell', {method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({user_id: uid, token_id: currentTokenId, amount: qty})});
            const data = await res.json();
            if (res.ok) { tg.showAlert(`Sold! +${data.gain.toFixed(2)} Genesis points`); show('profil'); }
            else { tg.showAlert(data.error || "Error"); }
        }

        function processFile(type) {
            const file = document.getElementById('f-' + type).files[0];
            const reader = new FileReader();
            reader.onloadend = () => { if(type==='logo') b64_logo=reader.result; else b64_banner=reader.result; };
            if(file) reader.readAsDataURL(file);
        }

        async function deployStars() {
            const name = document.getElementById('tk-name').value;
            if(!name || !b64_logo) return tg.showAlert("Logo & Name Required!");
            const save = await fetch('/api/launcher/save-pending', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({user_id:uid, name:name, symbol:document.getElementById('tk-sym').value, desc:document.getElementById('tk-desc').value, logo:b64_logo, banner:b64_banner})});
            const sData = await save.json();
            const res = await fetch('/api/launcher/create-invoice', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({temp_id: sData.temp_id})});
            const data = await res.json();
            if(data.ok) tg.openInvoice(data.link, (status) => { if(status==='paid') show('launcher'); });
        }

        async function loadMarket() {
            const r = await fetch('/api/launcher/list');
            const tokens = await r.json();
            let h = "";
            tokens.forEach(t => {
                h += `<div class="card" onclick='openToken(${JSON.stringify(t)})'><div style="display:flex; align-items:center; gap:12px;"><img src="${t.logo}" style="width:40px;height:40px;border-radius:10px;object-fit:cover;"><div><b>${t.name}</b><br><small style="color:var(--text)">$${t.sym}</small></div></div><b style="color:var(--green)">${t.price.toFixed(6)}</b></div>`;
            });
            document.getElementById('token-list').innerHTML = h || "<center style='color:#444'>No tokens active</center>";
        }

        function show(pageId) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));
            document.getElementById('p-' + pageId).classList.add('active-page');
            document.querySelectorAll('.n-i').forEach(nav => nav.classList.remove('active'));
            document.getElementById('n-' + (pageId === 'details' ? 'launcher' : pageId)).classList.add('active');
            if(pageId === 'launcher') loadMarket();
            refresh();
        }

        tg.expand(); refresh(); setInterval(refresh, 8000);
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
    payload = update.message.successful_payment.invoice_payload
    
    # Si c'est un ACHAT (format buy|uid|tid|qty)
    if payload.startswith("buy|"):
        _, uid, tid, qty = payload.split('|')
        # On ajoute les assets dans la DB
        database.buy_token(int(uid), int(tid), float(qty))
        await update.message.reply_text("✅ Tokens ajoutés à ton portefeuille !")
        
    # Si c'est un DÉPLOIEMENT (temp_id)
    else:
        data = pending_tokens.get(payload)
        if data:
            database.deploy_token(data['user_id'], data['name'], data['symbol'], data['desc'], data['logo'], data['banner'], "", "")
            del pending_tokens[payload]
            await update.message.reply_text(f"🚀 {data['name']} est en ligne !")

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