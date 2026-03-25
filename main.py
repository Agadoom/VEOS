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

# Variable globale pour le bot
bot_instance = None

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
    
    # Récupérer les assets du profil
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT t.name, t.symbol, a.amount FROM user_community_assets a JOIN community_tokens t ON a.token_id = t.id WHERE a.user_id = %s AND a.amount > 0", (uid,))
    assets = [{"n": x[0], "s": x[1], "a": float(x[2])} for x in c.fetchall()]
    c.close(); conn.close()

    return {
        "uid": uid, "name": r[4], "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0,
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "score": round(score, 2),
        "badge": badge, "assets": assets
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    # Utilisation de la logique de mine avec énergie
    conn = database.get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT energy, last_energy_update FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        now = int(time.time())
        if res:
            cur_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now - (res[1] or now))/60)*config.REGEN_RATE)
            if cur_e >= 1:
                c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+0.05, energy=%s, last_energy_update=%s WHERE user_id=%s", (cur_e-1, now, uid))
                conn.commit(); return {"ok": True}
        return JSONResponse(status_code=400, content={"error": "No energy"})
    finally: c.close(); conn.close()

@app.get("/api/launcher/list")
async def api_list_tokens():
    return database.get_community_tokens()

@app.get("/api/launcher/activity/{tid}")
async def api_get_activity(tid: int):
    return {"activity": database.get_token_activity(tid), "holders": database.get_token_holders(tid)}

@app.post("/api/launcher/create-invoice")
async def api_create_invoice(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    # On génère un payload simple pour identifier le paiement
    payload = f"deploy_{uid}_{int(time.time())}"
    try:
        link = await bot_instance.bot.create_invoice_link(
            title=f"Deploy {data.get('name')[:15]}",
            description=f"Launch fee for ${data.get('symbol')}",
            payload=payload,
            provider_token="", currency="XTR",
            prices=[LabeledPrice("Launch Fee", config.DEPLOY_FEE_STARS)]
        )
        return {"ok": True, "link": link}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.post("/api/launcher/buy")
async def api_buy_token(request: Request):
    data = await request.json()
    success, msg = database.buy_token(data.get("user_id"), data.get("token_id"), float(data.get("amount", 10)))
    return {"ok": success, "error": msg if not success else None}

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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --green: #34C759; --red: #FF3B30; --text: #8E8E8E; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 120px; overflow-x: hidden; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 15px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 11px; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.95); padding: 12px 25px; border-radius: 40px; display: flex; gap: 30px; border: 1px solid #333; z-index: 1000; backdrop-filter: blur(10px); }
        .n-i { font-size: 22px; opacity: 0.3; transition: 0.3s; }
        .n-i.active { opacity: 1; color: var(--gold); transform: scale(1.1); }
        .l-input { background: #000; border: 1px solid #333; color: #fff; padding: 12px; border-radius: 12px; width: 100%; margin-bottom: 10px; box-sizing: border-box; }
        .energy-bar { background: #222; height: 6px; border-radius: 3px; margin: 10px 0; overflow: hidden; }
        .energy-fill { background: var(--gold); height: 100%; width: 0%; transition: 0.3s; }
    </style>
</head>
<body>

    <div id="p-mine">
        <div style="text-align:center; padding:30px 0;">
            <small id="u-badge" style="color:var(--gold); letter-spacing:2px;"></small>
            <h1 id="tot" style="font-size:45px; margin:10px 0;">0.00</h1>
            <div class="energy-bar"><div id="e-f" class="energy-fill"></div></div>
            <small id="e-t" style="color:var(--text)">Energy: 0/100</small>
        </div>
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div><b>Genesis</b><br><small id="gv" style="color:var(--green)">0.00</small></div>
                <button class="btn" onclick="mine('genesis')">MINE</button>
            </div>
        </div>
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div><b>Unity</b><br><small id="uv" style="color:var(--blue)">0.00</small></div>
                <button class="btn" onclick="mine('unity')">SYNC</button>
            </div>
        </div>
    </div>

    <div id="p-launcher" style="display:none">
        <h3 style="text-align:center;">🚀 TOKEN LAUNCHER</h3>
        <div class="card">
            <input type="text" id="tk-name" class="l-input" placeholder="Token Name">
            <input type="text" id="tk-sym" class="l-input" placeholder="Symbol (ex: BTC)">
            <textarea id="tk-desc" class="l-input" placeholder="Description..."></textarea>
            <button class="btn" style="width:100%; background:var(--gold);" onclick="deployStars()">LAUNCH (★ STARS)</button>
        </div>
        <h4 style="margin:20px 0 10px 5px;">MARKET</h4>
        <div id="token-list"></div>
    </div>

    <div id="p-details" style="display:none; padding-bottom:100px;">
        <div style="position:relative; height:120px; background:#222; border-radius:15px; background-size:cover;" id="det-banner">
            <button class="btn" onclick="show('launcher')" style="position:absolute; top:10px; left:10px; background:rgba(0,0,0,0.5); color:#fff; border-radius:50%; width:30px; height:30px; padding:0;">←</button>
        </div>
        <div style="padding:10px;">
            <h2 id="det-name" style="margin:5px 0;"></h2>
            <p id="det-desc" style="font-size:12px; color:var(--text);"></p>
            <div class="card" style="background:#000;">
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:10px;">
                    <span>Price: <b id="det-price" style="color:var(--green)"></b></span>
                    <span>Holders: <b id="det-holders" style="color:var(--blue)">0</b></span>
                </div>
                <svg viewBox="0 0 100 30" style="width:100%; height:50px;"><path d="M0 25 Q 20 20, 40 5 T 80 15 T 100 2" fill="none" stroke="var(--green)" stroke-width="2"/></svg>
            </div>
            <button class="btn" style="width:100%; background:var(--green); color:#fff; padding:15px;" onclick="quickBuy(10)">BUY 10 WPT</button>
        </div>
    </div>

    <div id="p-profil" style="display:none">
        <h3 style="text-align:center;">👤 MY PROFILE</h3>
        <div class="card" style="text-align:center;">
            <div style="font-size:40px; margin-bottom:10px;">💎</div>
            <h2 id="prof-name" style="margin:0;">User</h2>
            <small id="prof-badge" style="color:var(--gold)"></small>
        </div>
        <h4 style="margin:20px 0 10px 5px;">MY TOKENS</h4>
        <div id="prof-assets"></div>
    </div>

    <nav class="nav">
        <div onclick="show('mine')" id="n-mine" class="n-i active">🏠</div>
        <div onclick="show('launcher')" id="n-launcher" class="n-i">🚀</div>
        <div onclick="show('profil')" id="n-profil" class="n-i">👤</div>
    </nav>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let activeTokenId = null;

        async function refresh() {
            const r = await fetch(`/api/user/${uid}`);
            const d = await r.json();
            document.getElementById('tot').innerText = d.score.toFixed(2);
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('u-badge').innerText = d.badge.toUpperCase();
            document.getElementById('e-f').style.width = (d.energy/d.max_energy*100) + "%";
            document.getElementById('e-t').innerText = `Energy: ${Math.floor(d.energy)}/${d.max_energy}`;
            
            // Profil
            document.getElementById('prof-name').innerText = d.name;
            document.getElementById('prof-badge').innerText = d.badge;
            let ah = ""; d.assets.forEach(a => {
                ah += `<div class="card"><span>${a.n} ($${a.s})</span><b>${a.a.toFixed(2)}</b></div>`;
            });
            document.getElementById('prof-assets').innerHTML = ah || "<small style='color:#444'>No assets</small>";
        }

        async function mine(t) {
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('light'); refresh(); }
        }

        async function deployStars() {
            const name = document.getElementById('tk-name').value;
            if(!name) return tg.showAlert("Name required");
            const res = await fetch('/api/launcher/create-invoice', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({user_id:uid, name:name, symbol:document.getElementById('tk-sym').value, desc:document.getElementById('tk-desc').value})
            });
            const data = await res.json();
            if(data.ok) tg.openInvoice(data.link, (status) => { if(status==='paid') show('launcher'); });
        }

        async function loadLauncher() {
            const r = await fetch('/api/launcher/list');
            const tokens = await r.json();
            let h = "";
            tokens.forEach(t => {
                h += `<div class="card" onclick='openToken(${JSON.stringify(t)})' style="display:flex; justify-content:space-between;">
                    <b>${t.name} <small style="color:#555">$${t.sym}</small></b>
                    <b style="color:var(--green)">${t.price.toFixed(6)}</b>
                </div>`;
            });
            document.getElementById('token-list').innerHTML = h;
        }

        async function openToken(t) {
            activeTokenId = t.id;
            show('details');
            document.getElementById('det-name').innerText = t.name;
            document.getElementById('det-desc').innerText = t.desc;
            document.getElementById('det-price').innerText = t.price.toFixed(6);
            const res = await fetch(`/api/launcher/activity/${t.id}`);
            const data = await res.json();
            document.getElementById('det-holders').innerText = data.holders;
        }

        async function quickBuy(amt) {
            const res = await fetch('/api/launcher/buy', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({user_id:uid, token_id:activeTokenId, amount:amt})
            });
            if(res.ok) { tg.showAlert("Bought!"); refresh(); }
        }

        function show(p) {
            ['mine', 'launcher', 'details', 'profil'].forEach(id => {
                document.getElementById('p-' + id).style.display = (id === p ? 'block' : 'none');
                const nav = document.getElementById('n-' + id);
                if(nav) nav.classList.toggle('active', id === p);
            });
            if(p === 'launcher') loadLauncher();
            refresh();
        }

        tg.expand(); refresh();
    </script>
</body>
</html>
"""

# --- BOT ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text("Welcome to WPT HUB!", reply_markup=kb)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Payment Success! Your token is now live.")

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
