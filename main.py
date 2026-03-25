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
    
    # Calcul de l'énergie et score
    now = int(time.time())
    last_update = r[6] if r[6] is not None else now
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_update) / 60) * config.REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, _, _ = missions.get_badge_info(score)
    
    # RÉCUPÉRATION DE TOUS LES ASSETS (Correction My Wallet)
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("""
        SELECT t.name, t.symbol, a.amount 
        FROM user_community_assets a 
        JOIN community_tokens t ON a.token_id = t.id 
        WHERE a.user_id = %s AND a.amount > 0
    """, (uid,))
    assets = [{"n": x[0], "s": x[1], "a": float(x[2])} for x in c.fetchall()]
    c.close(); conn.close()
    
    return {
        "uid": uid, "name": r[4], "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, 
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, 
        "score": round(score, 2), "badge": badge, "assets": assets
    }

@app.post("/api/launcher/buy-request")
async def api_buy_request(request: Request):
    data = await request.json()
    uid, tid = data.get("user_id"), data.get("token_id")
    qty = 100
    cost_wpt = 50 # Le prix en points Genesis/WPT
    
    # Vérification du solde WPT (Genesis)
    r = database.get_user_full(uid)
    if (r[0] or 0) < cost_wpt:
        return JSONResponse(status_code=400, content={"error": f"Il vous faut {cost_wpt} WPT"})

    # Facture Stars pour les FRAIS de service (ex: 10 Stars)
    payload = f"buy|{uid}|{tid}|{qty}|{cost_wpt}"
    try:
        link = await bot_instance.bot.create_invoice_link(
            title="Frais d'achat",
            description=f"Frais de réseau pour {qty} tokens",
            payload=payload, provider_token="", currency="XTR",
            prices=[LabeledPrice("Frais de service", 10)]
        )
        return {"ok": True, "link": link}
    except Exception as e: return JSONResponse(status_code=400, content={"error": str(e)})

@app.get("/api/launcher/chart/{tid}")
async def get_chart_data(tid: int):
    points = [random.uniform(0.0001, 0.0008) for _ in range(15)]
    points.sort() 
    return {"points": points}

@app.get("/api/launcher/list")
async def api_list_tokens():
    return database.get_community_tokens()

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
        .prof-header { background: linear-gradient(135deg, #1c1c1e 0%, #050505 100%); border-radius: 30px; padding: 25px 20px; border: 1px solid #222; margin-bottom: 20px; text-align: center; }
        .card { background: var(--card); border-radius: 20px; padding: 15px; margin-bottom: 12px; border: 1px solid #1c1c1e; display: flex; justify-content: space-between; align-items: center; }
        .btn { background: #FFF; color: #000; border: none; padding: 12px 20px; border-radius: 14px; font-weight: 800; cursor: pointer; }
        .nav { position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.95); backdrop-filter: blur(15px); padding: 12px 35px; border-radius: 50px; display: flex; gap: 40px; border: 1px solid #333; z-index: 999; }
        .n-i { font-size: 24px; opacity: 0.3; transition: 0.3s; cursor:pointer; }
        .n-i.active { opacity: 1; color: var(--gold); transform: scale(1.1); }
        .page { display: none; }
        .active-page { display: block; }
        .l-input { background: #000; border: 1px solid #333; color: #fff; padding: 12px; border-radius: 12px; width: 100%; box-sizing: border-box; }
    </style>
</head>
<body>
    <div class="ticker"><div class="t-wrap"><span style="color:var(--gold)">🏆 NETWORK ACTIVE ● TRADING ENABLED ● </span></div></div>

    <div class="container">
        <div id="p-mine" class="page active-page">
            <div class="prof-header">
                <small id="u-badge" style="color:var(--gold); font-weight:bold;"></small>
                <h1 id="tot" style="font-size:45px; margin:10px 0;">0.00</h1>
                <div style="background:#222; height:6px; border-radius:10px; margin:10px 0;"><div id="e-f" style="background:var(--gold); height:100%; width:0%; transition:0.3s;"></div></div>
                <small id="e-t" style="color:var(--text)">Energy: 0/100</small>
            </div>
            <div class="card"><div><b>Genesis (WPT)</b><br><small id="gv">0.00</small></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        </div>

        <div id="p-launcher" class="page">
            <h2 style="text-align:center;">🚀 LAUNCHPAD</h2>
            <div id="token-list"></div>
        </div>

        <div id="p-details" class="page">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <button class="btn" onclick="show('launcher')" style="background:#222; color:#fff;">←</button>
                <b id="det-price-top" style="color:var(--green); font-family:monospace;">0.000000</b>
            </div>
            <div id="det-banner" style="height:120px; border-radius:20px; background-size:cover; position:relative; background-color:#1a1a1c;">
                <img id="det-logo" style="width:60px; height:60px; border-radius:15px; border:3px solid #000; position:absolute; bottom:-20px; left:20px;">
            </div>
            <div style="margin-top:30px; padding:0 15px;">
                <h2 id="det-name" style="margin:0;"></h2>
                <b id="det-sym" style="color:var(--gold)"></b>
            </div>
            <div style="padding:15px;">
                <svg id="price-chart" viewBox="0 0 300 100" style="width:100%; height:100px; background:#000; border-radius:15px;">
                    <polyline id="chart-line" fill="none" stroke="#34C759" stroke-width="2" points="0,100 300,100" />
                </svg>
            </div>
            <div style="display:flex; flex-direction:column; gap:10px; padding:15px;">
                <div style="display:flex; gap:10px;">
                    <button class="btn" style="flex:1; background:var(--green); color:#fff;" onclick="buyTokenStars()">BUY</button>
                    <button class="btn" style="flex:1; background:var(--red); color:#fff;" onclick="sellToken()">SELL</button>
                </div>
                <button class="btn" style="background:#111; color:var(--blue); border:1px solid #333;" onclick="withdrawToken()">📤 WITHDRAW TO WALLET</button>
            </div>
            <center><small style="color:var(--text)">Liquidity Locked ● Holders: <span id="det-holders">1</span></small></center>
        </div>

        <div id="p-profil" class="page">
            <div class="prof-header">
                <h2 id="prof-name">User</h2>
                <div id="prof-badge" style="color:var(--gold); font-size:12px;">RANK: NOVICE</div>
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
        let currentTokenId = null;

        async function refresh() {
            const r = await fetch(`/api/user/${uid}`);
            const d = await r.json();
            document.getElementById('tot').innerText = d.score.toFixed(2);
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('u-badge').innerText = d.badge.toUpperCase();
            document.getElementById('prof-name').innerText = d.name;
            document.getElementById('e-f').style.width = (d.energy/d.max_energy*100) + "%";
            document.getElementById('e-t').innerText = `Energy: ${Math.floor(d.energy)}/100`;
            
            // AFFICHAGE DES TOKENS DANS LE WALLET
            let ah = ""; 
            d.assets.forEach(a => { 
                ah += `<div class="card"><span>${a.n} ($${a.s})</span><b>${a.a.toFixed(2)}</b></div>`; 
            });
            document.getElementById('prof-assets').innerHTML = ah || "<center style='color:#444'>Empty Wallet</center>";
        }

        async function openToken(t) {
            currentTokenId = t.id;
            show('details');
            document.getElementById('det-banner').style.backgroundImage = `url(${t.banner})`;
            document.getElementById('det-logo').src = t.logo;
            document.getElementById('det-name').innerText = t.name;
            document.getElementById('det-sym').innerText = "$" + t.sym;
            document.getElementById('det-price-top').innerText = t.price.toFixed(6);
            const cRes = await fetch(`/api/launcher/chart/${t.id}`);
            const cData = await cRes.json();
            drawChart(cData.points);
        }

        function drawChart(points) {
            const poly = document.getElementById('chart-line');
            const max = Math.max(...points), min = Math.min(...points);
            let pts = "";
            points.forEach((p, i) => {
                const x = (i / (points.length - 1)) * 300;
                const y = 100 - ((p - min) / (max - min) * 80 + 10);
                pts += `${x},${y} `;
            });
            poly.setAttribute("points", pts);
        }

        async function buyTokenStars() {
            const res = await fetch('/api/launcher/buy-request', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({user_id: uid, token_id: currentTokenId})
            });
            const data = await res.json();
            if(data.ok) {
                tg.openInvoice(data.link, (status) => {
                    if(status === 'paid') { tg.showAlert("Achat réussi !"); show('profil'); }
                });
            } else { tg.showAlert(data.error); }
        }

        async function withdrawToken() {
            tg.showConfirm("Retrait vers wallet externe ? (Frais : 50 Stars)", (ok) => {
                if(ok) tg.showAlert("Fonctionnalité en cours de liaison avec TON Connect.");
            });
        }

        async function loadMarket() {
            const r = await fetch('/api/launcher/list');
            const tokens = await r.json();
            let h = "";
            tokens.forEach(t => {
                h += `<div class="card" onclick='openToken(${JSON.stringify(t)})'>
                    <div style="display:flex; align-items:center; gap:10px;">
                        <img src="${t.logo}" style="width:35px;height:35px;border-radius:8px;">
                        <b>${t.name}</b>
                    </div>
                    <b style="color:var(--green)">${t.price.toFixed(6)}</b>
                </div>`;
            });
            document.getElementById('token-list').innerHTML = h;
        }

        function show(p) {
            document.querySelectorAll('.page').forEach(pg => pg.classList.remove('active-page'));
            document.getElementById('p-' + p).classList.add('active-page');
            if(p === 'launcher') loadMarket();
            refresh();
        }

        async function mine(t) {
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            refresh();
        }

        tg.expand(); refresh();
    </script>
</body>
</html>
"""

# --- BOT LOGIC ---
async def success_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    if payload.startswith("buy|"):
        _, uid, tid, qty, cost_wpt = payload.split('|')
        conn = database.get_db_conn(); c = conn.cursor()
        # On déduit les WPT (Genesis) et on ajoute les tokens
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (float(cost_wpt), int(uid)))
        database.buy_token(int(uid), int(tid), float(qty))
        conn.commit(); c.close(); conn.close()
        await update.message.reply_text("✅ Transaction réussie !")
    else:
        # Logique pour déploiement initial...
        data = pending_tokens.get(payload)
        if data:
            database.deploy_token(data['user_id'], data['name'], data['symbol'], data['desc'], data['logo'], data['banner'], "", "")
            await update.message.reply_text(f"🚀 {data['name']} est en ligne !")

async def main():
    global bot_instance
    bot_instance = ApplicationBuilder().token(config.TOKEN).build()
    bot_instance.add_handler(PreCheckoutQueryHandler(lambda u, c: u.pre_checkout_query.answer(ok=True)))
    bot_instance.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, success_payment_callback))
    await bot_instance.initialize(); await bot_instance.start(); await bot_instance.updater.start_polling()
    conf = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    await uvicorn.Server(conf).serve()

if __name__ == "__main__":
    asyncio.run(main())
