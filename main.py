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
    return {
        "uid": uid, "name": r[4], "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0,
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "score": round(score, 2),
        "badge": badge
    }

@app.post("/api/launcher/create-invoice")
async def api_create_invoice(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    # On crée une référence unique pour le paiement (évite le payload trop lourd)
    # Dans un vrai projet, on stockerait 'data' en DB temporaire ici.
    # Pour l'exemple, on passe juste l'UID et le NOM (court).
    
    payload = f"deploy_{uid}_{int(time.time())}"
    
    try:
        link = await bot_instance.bot.create_invoice_link(
            title=f"Deploy {data.get('name')[:15]}",
            description="Fee for launching your community token",
            payload=payload,
            provider_token="", 
            currency="XTR",
            prices=[LabeledPrice("Launch Fee", config.DEPLOY_FEE_STARS)]
        )
        return {"ok": True, "link": link}
    except Exception as e:
        print(f"Invoice Error: {e}")
        return JSONResponse(status_code=400, content={"error": "Check bot permissions or Stars config"})

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    # Logique de mine simplifiée pour le code complet
    database.mine_points(uid, t)
    return {"ok": True}

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
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 12px 18px; border-radius: 12px; font-weight: bold; cursor: pointer; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); padding: 12px 25px; border-radius: 40px; display: flex; gap: 25px; border: 1px solid #333; z-index: 1000; }
        .n-i { font-size: 20px; opacity: 0.3; }
        .n-i.active { opacity: 1; color: var(--gold); }
        .l-input { background: #000; border: 1px solid #333; color: #fff; padding: 12px; border-radius: 12px; width: 100%; margin-bottom: 10px; box-sizing: border-box; }
        #det-banner { height: 120px; background-size: cover; border-radius: 15px; background-color: #222; }
    </style>
</head>
<body>
    <div id="p-mine">
        <div style="text-align:center; padding:20px;">
            <small id="u-badge" style="color:var(--gold)"></small>
            <h1 id="tot" style="font-size:40px; margin:5px 0;">0.00</h1>
        </div>
        <div class="card" style="display:flex; justify-content:space-between; align-items:center;">
            <span>Genesis Points</span><button class="btn" onclick="mine('genesis')">MINE</button>
        </div>
    </div>

    <div id="p-launcher" style="display:none">
        <h3 style="text-align:center;">🚀 LAUNCHER</h3>
        <div class="card">
            <input type="text" id="tk-name" class="l-input" placeholder="Token Name">
            <input type="text" id="tk-sym" class="l-input" placeholder="Symbol">
            <textarea id="tk-desc" class="l-input" placeholder="Description"></textarea>
            <button class="btn" style="width:100%; background:var(--gold)" onclick="deployStars()">LAUNCH WITH STARS</button>
        </div>
        <div id="token-list"></div>
    </div>

    <div id="p-details" style="display:none">
        <button class="btn" style="background:#222; color:#fff; margin-bottom:10px;" onclick="show('launcher')">← BACK</button>
        <div id="det-banner"></div>
        <div class="card" style="margin-top:10px;">
            <h2 id="det-name" style="margin:0;"></h2>
            <p id="det-desc" style="color:var(--text)"></p>
            <div style="display:flex; justify-content:space-between;">
                <span>Holders: <b id="det-holders">0</b></span>
                <span style="color:var(--green)" id="det-price">0.00</span>
            </div>
        </div>
    </div>

    <div id="p-profil" style="display:none">
        <h3 style="text-align:center;">👤 MY PROFILE</h3>
        <div class="card" style="text-align:center;">
            <div style="font-size:50px;">👤</div>
            <h2 id="prof-name">User</h2>
            <div id="prof-badge" style="color:var(--gold)">NOVICE</div>
        </div>
        <div class="card">
            <h4>My Assets</h4>
            <div id="prof-assets"><small style="color:#555">No tokens held yet</small></div>
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
            const r = await fetch(`/api/user/${uid}`);
            const d = await r.json();
            document.getElementById('tot').innerText = d.score.toFixed(2);
            document.getElementById('u-badge').innerText = d.badge;
            document.getElementById('prof-name').innerText = d.name || "User";
            document.getElementById('prof-badge').innerText = d.badge;
        }

        async function deployStars() {
            const name = document.getElementById('tk-name').value;
            if(!name) return tg.showAlert("Name required!");
            
            const res = await fetch('/api/launcher/create-invoice', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ user_id: uid, name: name, symbol: document.getElementById('tk-sym').value, desc: document.getElementById('tk-desc').value })
            });
            const data = await res.json();
            if(data.ok) {
                tg.openInvoice(data.link, function(status) {
                    if(status === 'paid') tg.showAlert("Success! Token will be listed.");
                });
            } else { tg.showAlert(data.error); }
        }

        async function openToken(t) {
            show('details');
            document.getElementById('det-name').innerText = t.name;
            document.getElementById('det-desc').innerText = t.desc;
            document.getElementById('det-price').innerText = t.price.toFixed(6);
            // On peut appeler l'API pour les holders ici
        }

        async function mine(t) {
            await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            refresh();
        }

        function show(p) {
            ['mine', 'launcher', 'details', 'profil'].forEach(id => {
                document.getElementById('p-' + id).style.display = (id === p ? 'block' : 'none');
                if(document.getElementById('n-' + id)) document.getElementById('n-' + id).classList.toggle('active', id === p);
            });
            if(p === 'launcher') loadLauncher();
            refresh();
        }

        async function loadLauncher() {
            const r = await fetch('/api/launcher/list');
            const tokens = await r.json();
            let html = "";
            tokens.forEach(t => {
                html += `<div class="card" onclick='openToken(${JSON.stringify(t)})'><b>${t.name}</b> <span>${t.price.toFixed(6)}</span></div>`;
            });
            document.getElementById('token-list').innerHTML = html;
        }

        tg.expand(); refresh();
    </script>
</body>
</html>
"""

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text("Welcome!", reply_markup=kb)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ici tu enregistres le token final en DB
    await update.message.reply_text("✅ Payment Received! Token is live.")

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
