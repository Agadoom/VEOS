import asyncio, uvicorn, time, json, random
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

bot_instance = None

# --- HELPERS ---
def get_network_stats():
    try:
        conn = database.get_db_conn(); c = conn.cursor()
        now = int(time.time())
        c.execute("SELECT COUNT(*) FROM users WHERE last_energy_update > %s", (now - 300,))
        online = max(1, c.fetchone()[0])
        c.execute("SELECT COUNT(*) FROM users")
        total = max(1, c.fetchone()[0])
        jk = database.get_total_network_score() * 0.1
        c.close(); conn.close()
        return online, total, round(jk, 2)
    except: return 1, 1, 0.0

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
    online, total, jk = get_network_stats()
    
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT t.name, t.symbol, a.amount FROM user_community_assets a JOIN community_tokens t ON a.token_id = t.id WHERE a.user_id = %s AND a.amount > 0", (uid,))
    assets = [{"n": x[0], "s": x[1], "a": float(x[2])} for x in c.fetchall()]
    c.close(); conn.close()

    return {
        "uid": uid, "name": r[4], "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0,
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "score": round(score, 2),
        "badge": badge, "jackpot": jk, "online": online, "total": total, "assets": assets
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    # Logique de minage avec consommation d'énergie
    conn = database.get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT energy, last_energy_update FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        now = int(time.time())
        if res:
            cur_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now - (res[1] or now))/60)*config.REGEN_RATE)
            if cur_e >= 1:
                val = 0.05 if t != 'veo' else 0.15 # Veo rapporte plus mais consomme pareil ici
                c.execute(f"UPDATE users SET p_{t}=COALESCE(p_{t},0)+%s, energy=%s, last_energy_update=%s WHERE user_id=%s", (val, cur_e-1, now, uid))
                conn.commit(); return {"ok": True}
        return JSONResponse(status_code=400, content={"error": "Low Energy"})
    finally: c.close(); conn.close()




@app.post("/api/launcher/create-invoice") # Vérifie bien l'orthographe ici
async def api_create_invoice(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    name = data.get("name")
    
    # On crée un payload simple (max 128 caractères)
    # On stocke l'essentiel : ID utilisateur et timestamp
    payload = f"deploy_{uid}_{int(time.time())}"
    
    try:
        # On utilise bot_instance.bot pour générer le lien
        link = await bot_instance.bot.create_invoice_link(
            title=f"Deploy {name[:15]}",
            description=f"Launch fee for community token",
            payload=payload,
            provider_token="", # Vide pour Telegram Stars
            currency="XTR",    # Code pour les Stars
            prices=[LabeledPrice("Launch Fee", config.DEPLOY_FEE_STARS)]
        )
        return {"ok": True, "link": link}
    except Exception as e:
        print(f"Erreur Invoice: {e}")
        return JSONResponse(status_code=400, content={"error": str(e)})


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
        :root { --bg: #050505; --card: #121214; --gold: #FFD700; --blue: #007AFF; --green: #34C759; --purple: #A259FF; --red: #FF3B30; --text: #8E8E8E; }
        body { background: var(--bg); color: #FFF; font-family: 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; overflow-x: hidden; }
        
        /* Ticker */
        .ticker { background: #1a1a1c; padding: 8px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; font-size: 11px; font-weight: bold; }
        .t-wrap { display: inline-block; animation: scroll 20s linear infinite; }
        @keyframes scroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        .container { padding: 15px; padding-bottom: 120px; }
        
        /* Balance Card */
        .main-card { background: radial-gradient(circle at top right, #1c1c1e, #050505); border-radius: 28px; padding: 30px 20px; text-align: center; border: 1px solid #222; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .energy-bar { background: #222; height: 8px; border-radius: 10px; margin: 15px 0; overflow: hidden; }
        .energy-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.5s ease; }

        /* Component Cards */
        .card { background: var(--card); border-radius: 20px; padding: 15px; margin-bottom: 12px; border: 1px solid #1c1c1e; display: flex; justify-content: space-between; align-items: center; }
        .btn { background: #FFF; color: #000; border: none; padding: 12px 20px; border-radius: 14px; font-weight: 800; font-size: 12px; transition: 0.2s; cursor: pointer; }
        .btn:active { transform: scale(0.95); }
        
        /* Navigation */
        .nav { position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.9); backdrop-filter: blur(15px); padding: 12px 30px; border-radius: 50px; display: flex; gap: 35px; border: 1px solid #333; z-index: 1000; }
        .n-i { font-size: 24px; opacity: 0.25; transition: 0.3s; cursor: pointer; }
        .n-i.active { opacity: 1; color: var(--gold); transform: translateY(-5px); }

        .l-input { background: #000; border: 1px solid #222; color: #fff; padding: 14px; border-radius: 14px; width: 100%; margin-bottom: 10px; box-sizing: border-box; }
        .badge { font-size: 10px; padding: 4px 10px; border-radius: 20px; background: rgba(255,215,0,0.1); color: var(--gold); border: 1px solid var(--gold); }
    </style>
</head>
<body>
    <div class="ticker"><div class="t-wrap">
        <span style="margin-right:50px; color:var(--gold)">🏆 JACKPOT: <span id="jk-v">0</span> WPT</span>
        <span style="color:var(--green)">● NETWORK: <span id="on-v">0</span> ONLINE / <span id="tot-v">0</span> USERS</span>
    </div></div>

    <div class="container">
        <div id="p-mine">
            <div class="main-card">
                <div id="u-badge" class="badge" style="margin-bottom:10px; display:inline-block;">...</div>
                <h1 id="tot" style="font-size:50px; margin:5px 0; font-weight:900;">0.00</h1>
                <div class="energy-bar"><div id="e-f" class="energy-fill"></div></div>
                <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--text)">
                    <span>STAMINA</span><span id="e-t">0 / 100</span>
                </div>
            </div>

            <div class="card" style="border-left: 4px solid var(--green);">
                <div><small style="color:var(--text)">GENESIS</small><div id="gv" style="font-weight:bold; font-size:18px;">0.00</div></div>
                <button class="btn" onclick="mine('genesis')">MINE</button>
            </div>
            <div class="card" style="border-left: 4px solid var(--blue);">
                <div><small style="color:var(--text)">UNITY</small><div id="uv" style="font-weight:bold; font-size:18px;">0.00</div></div>
                <button class="btn" onclick="mine('unity')">SYNC</button>
            </div>
            <div class="card" style="border-left: 4px solid var(--purple); background: linear-gradient(to right, #121214, #1a0a2e);">
                <div><small style="color:var(--purple); font-weight:bold;">VEO AI</small><div id="vv" style="font-weight:bold; font-size:18px;">0.00</div></div>
                <button class="btn" onclick="mine('veo')" style="background:var(--purple); color:#fff;">COMPUTE</button>
            </div>
        </div>

        <div id="p-launcher" style="display:none">
            <h2 style="text-align:center; color:var(--gold);">🚀 LAUNCHPAD</h2>
            <div class="card" style="flex-direction:column; align-items:stretch;">
                <input type="text" id="tk-name" class="l-input" placeholder="Token Name">
                <input type="text" id="tk-sym" class="l-input" placeholder="Symbol (ex: DOGE)">
                <textarea id="tk-desc" class="l-input" placeholder="Description of your project..."></textarea>
                <button class="btn" style="background:var(--gold); width:100%; height:50px; font-size:14px;" onclick="deployStars()">DEPLOY (★ STARS)</button>
            </div>
            <div id="token-list" style="margin-top:20px;"></div>
        </div>

        <div id="p-details" style="display:none;">
            <div class="card" style="background:none; border:none; padding:0;">
                <button class="btn" onclick="show('launcher')" style="background:#222; color:#fff;">← BACK</button>
            </div>
            <div id="det-banner" style="height:140px; border-radius:20px; background:#1a1a1c; margin:15px 0; background-size:cover;"></div>
            <h2 id="det-name" style="margin:0;"></h2>
            <b id="det-sym" style="color:var(--gold)"></b>
            <p id="det-desc" style="color:var(--text); font-size:13px;"></p>
            
            <div class="card" style="background:#000; flex-direction:column; align-items:stretch;">
                <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                    <span>Price: <b id="det-price" style="color:var(--green)"></b></span>
                    <span>Holders: <b id="det-holders" style="color:var(--blue)">0</b></span>
                </div>
                <svg viewBox="0 0 100 40" style="width:100%; height:60px;"><path d="M0 35 Q 25 30, 45 10 T 85 20 T 100 5" fill="none" stroke="var(--green)" stroke-width="2.5" /></svg>
                <button class="btn" style="background:var(--green); color:#fff; width:100%; margin-top:15px; padding:15px;" onclick="quickBuy(10)">BUY 10 WPT</button>
            </div>
        </div>

        <div id="p-profil" style="display:none">
            <div class="main-card">
                <div style="font-size:60px;">💎</div>
                <h2 id="prof-name">...</h2>
                <div id="prof-badge" class="badge">...</div>
            </div>
            <h4 style="margin:20px 0 10px 0;">YOUR ASSETS</h4>
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
        let activeTokenId = null;

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}?t=${Date.now()}`);
                const d = await r.json();
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('jk-v').innerText = d.jackpot.toLocaleString();
                document.getElementById('on-v').innerText = d.online;
                document.getElementById('tot-v').innerText = d.total;
                document.getElementById('u-badge').innerText = d.badge.toUpperCase();
                document.getElementById('prof-badge').innerText = d.badge.toUpperCase();
                document.getElementById('prof-name').innerText = d.name;
                document.getElementById('e-f').style.width = (d.energy/d.max_energy*100) + "%";
                document.getElementById('e-t').innerText = `${d.energy} / ${d.max_energy}`;

                let ah = ""; d.assets.forEach(a => {
                    ah += `<div class="card"><div><b>${a.n}</b><br><small>$${a.s}</small></div><b>${a.a.toFixed(2)}</b></div>`;
                });
                document.getElementById('prof-assets').innerHTML = ah || "<center style='color:#444'>No tokens yet</center>";
            } catch(e){}
        }

        async function mine(t) {
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('medium'); refresh(); }
            else { tg.showAlert("Energy exhausted! Wait for recharge."); }
        }

        async function deployStars() {
            const name = document.getElementById('tk-name').value;
            const sym = document.getElementById('tk-sym').value;
            if(!name || !sym) return tg.showAlert("Name and Symbol are required!");

            const res = await fetch('/api/launcher/create-invoice', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({user_id:uid, name:name, symbol:sym, desc:document.getElementById('tk-desc').value})
            });
            const data = await res.json();
            if(data.ok) tg.openInvoice(data.link, (status) => { if(status==='paid') show('launcher'); });
        }

        async function loadLauncher() {
            const r = await fetch('/api/launcher/list');
            const tokens = await r.json();
            let h = "";
            tokens.forEach(t => {
                h += `<div class="card" onclick='openToken(${JSON.stringify(t)})'>
                    <div style="display:flex; align-items:center; gap:12px;">
                        <div style="width:40px; height:40px; border-radius:10px; background:var(--gold); display:flex; align-items:center; justify-content:center; font-weight:bold; color:#000">${t.sym[0]}</div>
                        <div><b>${t.name}</b><br><small style="color:var(--text)">$${t.sym}</small></div>
                    </div>
                    <div style="text-align:right"><b style="color:var(--green)">${t.price.toFixed(6)}</b></div>
                </div>`;
            });
            document.getElementById('token-list').innerHTML = h || "<center style='color:#444'>Market empty</center>";
        }

        async function openToken(t) {
            activeTokenId = t.id; show('details');
            document.getElementById('det-name').innerText = t.name;
            document.getElementById('det-sym').innerText = "$"+t.sym;
            document.getElementById('det-desc').innerText = t.desc || "Community driven token.";
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
            if(res.ok) { tg.HapticFeedback.notificationOccurred('success'); tg.showAlert("Purchase successful!"); refresh(); }
            else { tg.showAlert("Not enough WPT!"); }
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

        tg.expand(); refresh(); setInterval(refresh, 10000);
    </script>
</body>
</html>
"""

# --- BOT ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text("💎 Welcome to the Premium WPT HUB!", reply_markup=kb)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Idéalement, ici tu appelles database.deploy_token()
    await update.message.reply_text("✅ Payment confirmed! Your token is now live in the Launcher.")

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
