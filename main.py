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

pending_tokens = {}
bot_instance = None

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
    
    online, _, jk = (1, 1, score * 0.1) # Fallback stats simple
    
    conn = database.get_db_conn(); c = conn.cursor()
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
    uid = data.get("user_id")
    # On vérifie l'énergie côté serveur avant d'accepter le minage
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT energy, last_energy_update FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    now = int(time.time())
    if res:
        cur_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now - (res[1] or now))/60)*config.REGEN_RATE)
        if cur_e >= 1:
            database.mine_points(uid, data.get("token"))
            return {"ok": True, "energy": cur_e - 1}
    return JSONResponse(status_code=400, content={"error": "Low energy"})

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
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 0; overflow: hidden; }
        
        /* Ticker */
        .ticker { background: #1a1a1c; padding: 8px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; font-size: 11px; }
        .t-wrap { display: inline-block; animation: scroll 20s linear infinite; }
        @keyframes scroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        .container { padding: 15px; padding-bottom: 100px; height: 90vh; overflow-y: auto; }
        
        /* Dashboard Profile */
        .prof-header { background: linear-gradient(135deg, #1c1c1e 0%, #050505 100%); border-radius: 30px; padding: 30px 20px; border: 1px solid #222; margin-bottom: 20px; text-align: center; }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 20px; }
        .stat-card { background: #161618; padding: 15px; border-radius: 20px; border: 1px solid #222; }
        
        /* Common Cards */
        .card { background: var(--card); border-radius: 20px; padding: 15px; margin-bottom: 12px; border: 1px solid #1c1c1e; display: flex; justify-content: space-between; align-items: center; }
        .btn { background: #FFF; color: #000; border: none; padding: 12px 20px; border-radius: 14px; font-weight: 800; cursor: pointer; }
        .btn:disabled { opacity: 0.3; cursor: not-allowed; }

        /* Nav */
        .nav { position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.95); backdrop-filter: blur(15px); padding: 12px 35px; border-radius: 50px; display: flex; gap: 40px; border: 1px solid #333; z-index: 999; }
        .n-i { font-size: 24px; opacity: 0.3; transition: 0.3s; }
        .n-i.active { opacity: 1; color: var(--gold); transform: scale(1.1); }

        .page { display: none; }
        .active-page { display: block; }
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
                <div style="background:#222; height:6px; border-radius:10px; margin:15px 0;">
                    <div id="e-f" style="background:var(--gold); height:100%; width:0%; border-radius:10px; transition:0.3s;"></div>
                </div>
                <small id="e-t" style="color:var(--text)">Energy: 0/100</small>
            </div>
            <div class="card"><div><b>Genesis</b><br><small id="gv">0.00</small></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
            <div class="card"><div><b>Unity</b><br><small id="uv">0.00</small></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
            <div class="card"><div><b style="color:var(--purple)">Veo AI</b><br><small id="vv">0.00</small></div><button class="btn" style="background:var(--purple); color:#fff;" onclick="mine('veo')">COMPUTE</button></div>
        </div>

        <div id="p-launcher" class="page">
            <h2 style="text-align:center;">🚀 LAUNCHPAD</h2>
            <div class="card" style="flex-direction:column; align-items:stretch; gap:10px;">
                <input type="text" id="tk-name" style="background:#000; border:1px solid #333; color:#fff; padding:12px; border-radius:12px;" placeholder="Token Name">
                <input type="text" id="tk-sym" style="background:#000; border:1px solid #333; color:#fff; padding:12px; border-radius:12px;" placeholder="Symbol">
                <button class="btn" style="background:var(--gold);" onclick="deployStars()">LAUNCH TOKEN</button>
            </div>
            <div id="token-list"></div>
        </div>

        <div id="p-profil" class="page">
            <div class="prof-header">
                <div style="font-size:50px;">💎</div>
                <h2 id="prof-name" style="margin:5px 0;">User</h2>
                <div id="prof-badge" style="color:var(--gold); font-size:12px; font-weight:bold;">RANK: NOVICE</div>
                
                <div class="stat-grid">
                    <div class="stat-card"><small style="color:var(--text)">TOTAL SCORE</small><div id="prof-score" style="font-size:18px; font-weight:bold;">0</div></div>
                    <div class="stat-card"><small style="color:var(--text)">RANKING</small><div style="font-size:18px; font-weight:bold; color:var(--blue)">#124</div></div>
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

                let ah = ""; d.assets.forEach(a => {
                    ah += `<div class="card"><span>${a.n} ($${a.s})</span><b>${a.a.toFixed(2)}</b></div>`;
                });
                document.getElementById('prof-assets').innerHTML = ah || "<center style='color:#444; padding:20px;'>No tokens yet</center>";
            } catch(e) {}
        }

        async function mine(t) {
            const res = await fetch('/api/mine', {
                method:'POST', 
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({user_id:uid, token:t})
            });
            if(res.ok) {
                tg.HapticFeedback.impactOccurred('medium');
                refresh();
            } else {
                tg.showAlert("Not enough energy!");
            }
        }

        function show(pageId) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));
            document.getElementById('p-' + pageId).classList.add('active-page');
            
            document.querySelectorAll('.n-i').forEach(nav => nav.classList.remove('active'));
            document.getElementById('n-' + pageId).classList.add('active');
            
            if(pageId === 'launcher') loadMarket();
            refresh();
        }

        tg.expand();
        refresh();
        setInterval(refresh, 8000);
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
