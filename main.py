import asyncio, uvicorn, time, random
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# --- AJOUTE CES LIGNES ICI ---
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
# -----------------------------

import database, config, missions


app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- LOGIQUE STATS ---
def get_network_stats():
    try:
        conn = database.get_db_conn(); c = conn.cursor()
        now = int(time.time())
        # Utilisateurs actifs ces 5 dernières minutes
        c.execute("SELECT COUNT(*) FROM users WHERE last_energy_update > %s", (now - 300,))
        online = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users")
        total = c.fetchone()[0]
        c.close(); conn.close()
        return (online if online > 0 else 1), total
    except: return 1, 1

# --- ROUTES API ---
@app.get("/api/user/{uid}")
async def api_get_user(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={})
    now = int(time.time())
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, rank_idx, next_goal = missions.get_badge_info(score)
    online_c, total_u = get_network_stats()
    
    return {
        "uid": uid, "name": r[4], "g": round(r[0] or 0, 2), "u": round(r[1] or 0, 2), "v": round(r[2] or 0, 2),
        "score": round(score, 2), "energy": int(r[5] or 0), "max_energy": config.MAX_ENERGY,
        "badge": badge, "multiplier": round(1.0 + (score/5000), 2),
        "online": online_c, "total_users": total_u, "staked": r[8] or 0, "streak": r[7] or 0,
        "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "next_goal": next_goal
    }

@app.post("/api/launcher/deploy")
async def api_deploy_token(request: Request):
    data = await request.json()
    uid, name, symbol = data.get("user_id"), data.get("name"), data.get("symbol")
    logo, banner = data.get("logo"), data.get("banner")
    
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    if not res or res[0] < 500:
        c.close(); conn.close(); return JSONResponse(status_code=400, content={"error": "Need 500 WPT"})
    
    c.execute("UPDATE users SET p_genesis = p_genesis - 500 WHERE user_id = %s", (uid,))
    c.execute("""INSERT INTO community_tokens (creator_id, name, symbol, logo, banner, reserve_wpt, created_at) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s)""", (uid, name, symbol, logo, banner, 500, int(time.time())))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.get("/api/launcher/list")
async def api_list_tokens():
    conn = database.get_db_conn(); c = conn.cursor()
    c.execute("SELECT name, symbol, logo, price, holders, reserve_wpt, banner FROM community_tokens ORDER BY id DESC")
    tokens = c.fetchall()
    c.close(); conn.close()
    return [{"name": t[0], "symbol": t[1], "logo": t[2], "price": t[3], "holders": t[4], "mcap": round(t[5]*2, 2), "banner": t[6]} for t in tokens]

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
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; }
        .ticker { background: #111; margin: -15px -15px 15px -15px; padding: 10px; border-bottom: 1px solid #222; font-size: 10px; display: flex; justify-content: space-around; color: var(--gold); font-weight: bold; }
        .b-card { text-align: center; padding: 25px; border-radius: 20px; background: linear-gradient(180deg, #151515, #000); border: 1px solid #222; margin-bottom: 15px; }
        .card { background: var(--card); padding: 15px; border-radius: 15px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 15px; border-radius: 10px; font-weight: bold; font-size: 11px; cursor: pointer; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.95); backdrop-filter: blur(10px); padding: 12px 25px; border-radius: 30px; display: flex; gap: 20px; border: 1px solid #333; z-index: 100; }
        .n-i { font-size: 20px; opacity: 0.3; transition: 0.3s; } .n-i.active { opacity: 1; color: var(--purple); transform: scale(1.2); }
        .input-group { background: #000; padding: 10px; border-radius: 10px; border: 1px solid #222; margin-bottom: 10px; }
        input { background: transparent; border: none; color: #FFF; width: 100%; outline: none; padding: 5px 0; }
        .modal { position: fixed; inset: 0; background: rgba(0,0,0,0.9); z-index: 200; display: none; align-items: center; justify-content: center; padding: 20px; }
        .preview-box { width: 100%; border-radius: 15px; overflow: hidden; margin: 10px 0; border: 1px solid #333; }
        .pre-logo { width: 50px; height: 50px; border-radius: 50%; object-fit: cover; border: 2px solid var(--purple); margin: -25px auto 0 auto; display: block; position: relative; }
        .pre-ban { width: 100%; height: 80px; object-fit: cover; background: #222; }
    </style>
</head>
<body>
    <div class="ticker">
        <span>🟢 LIVE: <span id="on-v">0</span></span>
        <span>👥 TOTAL: <span id="tot-v">0</span></span>
        <span>💎 POOL: <span id="jk-v">0</span></span>
    </div>

    <div id="p-mine">
        <div class="b-card">
            <h1 id="tot" style="font-size:40px; margin:0;">0.00</h1>
            <small style="color:var(--text)">TOTAL WPT BALANCE</small>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine('unity')">MINE</button></div>
        <div class="card"><div><small style="color:var(--purple)">VEO AI</small><div id="vv">0.00</div></div><button class="btn" onclick="mine('veo')">MINE</button></div>
    </div>

    <div id="p-opps" style="display:none">
        <h3 style="text-align:center; color:var(--blue)">ORACLE PREDICT</h3>
        <div class="card" style="flex-direction:column; gap:15px; text-align:center;">
            <b>Will GENESIS Price go UP or DOWN?</b>
            <div style="display:flex; gap:10px; width:100%;">
                <button class="btn" style="flex:1; background:var(--green); color:#FFF" onclick="predict('UP')">UP ↑</button>
                <button class="btn" style="flex:1; background:var(--red); color:#FFF" onclick="predict('DOWN')">DOWN ↓</button>
            </div>
            <small style="color:var(--text)">Win 2.0x if your prediction is correct in 60s</small>
        </div>
    </div>

    <div id="p-launcher" style="display:none">
        <div id="launch-form">
            <h3 style="text-align:center; color:var(--purple)">TOKEN LAUNCHER</h3>
            <div class="input-group"><small>Name</small><input type="text" id="tk-name"></div>
            <div class="input-group"><small>Symbol</small><input type="text" id="tk-sym"></div>
            <div class="input-group"><small>Logo</small><input type="file" id="f-logo" onchange="previewFile('f-logo', 'pre-logo-v')"></div>
            <div class="input-group"><small>Banner</small><input type="file" id="f-ban" onchange="previewFile('f-ban', 'pre-ban-v')"></div>
            <button class="btn" style="width:100%; background:var(--purple); color:#FFF; padding:15px;" onclick="openCheckout()">DEPLOY (500 WPT)</button>
            <hr style="border:0; border-top:1px solid #222; margin:20px 0;">
            <div id="community-tokens-list"></div>
        </div>

        <div id="token-live-view" style="display:none;">
            <button class="btn" style="background:#222; color:#FFF; margin-bottom:10px;" onclick="backToLauncher()">< BACK</button>
            <div class="card" style="flex-direction:column; align-items:flex-start; padding:0; overflow:hidden;">
                <img id="live-tk-ban" src="" style="width:100%; height:80px; object-fit:cover;">
                <div style="padding:15px; display:flex; align-items:center; gap:10px; margin-top:-30px;">
                    <img id="live-tk-logo" src="" style="width:50px; height:50px; border-radius:50%; border:3px solid #000;">
                    <div><b id="live-tk-name">---</b><br><small id="live-tk-price" style="color:var(--green)">0.0001 WPT</small></div>
                </div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px;">
                <button class="btn" style="background:var(--green); color:#FFF; padding:15px;" onclick="trade('buy')">BUY</button>
                <button class="btn" style="background:var(--red); color:#FFF; padding:15px;" onclick="trade('sell')">SELL</button>
            </div>
        </div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="text-align:center;">WPT PILLARS</h3>
        <div class="card" onclick="tg.openLink('https://t.me/blum')"><b>Genesis Gold Index</b><span>GO ➔</span></div>
        <div class="card" onclick="tg.openLink('https://t.me/blum')"><b>Unity Silver Index</b><span>GO ➔</span></div>
        <div class="card" onclick="tg.openLink('https://t.me/blum')"><b>Veo AI Compute</b><span>GO ➔</span></div>
    </div>

    <div id="p-profile" style="display:none">
        <div class="b-card">
            <h2 id="pr-n">...</h2>
            <div id="pr-b" style="color:var(--gold)">RANK: ...</div>
        </div>
        <div class="card"><span>Power Multiplier</span><b id="pr-m">x1.0</b></div>
        <div class="card"><span>Mining Streak</span><b id="pr-s">0 Days</b></div>
    </div>

    <div id="m-check" class="modal">
        <div style="background:var(--card); width:90%; padding:20px; border-radius:20px; text-align:center; border:1px solid var(--purple);">
            <h3 style="margin:0">TOKEN PREVIEW</h3>
            <div class="preview-box">
                <img id="pre-ban-v" class="pre-ban" src="">
                <img id="pre-logo-v" class="pre-logo" src="">
            </div>
            <div id="check-info" style="margin-bottom:20px;"></div>
            <div style="display:flex; gap:10px;">
                <button class="btn" style="flex:1; background:#333; color:#FFF" onclick="closeCheckout()">EDIT</button>
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
        let lastClick = 0; let currentTk = null;

        function show(p) {
            ['mine','opps','launcher','pillars','profile'].forEach(id => {
                document.getElementById('p-'+id).style.display = (id === p ? 'block' : 'none');
                document.getElementById('n-'+id).classList.toggle('active', id === p);
            });
            if(p === 'launcher') loadTokens();
        }

        async function refresh() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('gv').innerText = d.g;
            document.getElementById('uv').innerText = d.u;
            document.getElementById('vv').innerText = d.v;
            document.getElementById('tot').innerText = d.score;
            document.getElementById('on-v').innerText = d.online;
            document.getElementById('tot-v').innerText = d.total_users;
            document.getElementById('jk-v').innerText = d.jackpot;
            document.getElementById('pr-n').innerText = d.name;
            document.getElementById('pr-b').innerText = d.badge;
            document.getElementById('pr-m').innerText = "x"+d.multiplier;
        }

        async function mine(t) {
            if(Date.now() - lastClick < 100) return; lastClick = Date.now();
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('light'); refresh(); }
        }

        function previewFile(inputId, imgId) {
            const file = document.getElementById(inputId).files[0];
            const reader = new FileReader();
            reader.onloadend = () => { document.getElementById(imgId).src = reader.result; }
            if (file) reader.readAsDataURL(file);
        }

        function openCheckout() {
            const name = document.getElementById('tk-name').value;
            const sym = document.getElementById('tk-sym').value;
            if(!name || !sym) return tg.showAlert("Need Name & Symbol!");
            document.getElementById('check-info').innerHTML = `<b>${name}</b> ($${sym})`;
            document.getElementById('m-check').style.display = 'flex';
        }
        function closeCheckout() { document.getElementById('m-check').style.display = 'none'; }

        async function confirmLaunch() {
            const name = document.getElementById('tk-name').value;
            const sym = document.getElementById('tk-sym').value;
            const logo = document.getElementById('pre-logo-v').src;
            const banner = document.getElementById('pre-ban-v').src;
            const res = await fetch('/api/launcher/deploy', {method:'POST', body:JSON.stringify({user_id:uid, name, symbol:sym, logo, banner})});
            if(res.ok) { tg.showAlert("Deployed!"); closeCheckout(); show('launcher'); }
            else tg.showAlert("Insufficient WPT!");
        }

        async function loadTokens() {
            const r = await fetch('/api/launcher/list'); const tokens = await r.json();
            let html = "";
            tokens.forEach(t => {
                html += `<div class="card" onclick='openLive(${JSON.stringify(t)})'>
                    <img src="${t.logo}" style="width:30px; border-radius:50%;">
                    <div style="flex:1; margin-left:10px;"><b>${t.name}</b></div>
                    <div style="color:var(--green)">${t.price} WPT</div>
                </div>`;
            });
            document.getElementById('community-tokens-list').innerHTML = html;
        }

        function openLive(t) {
            currentTk = t;
            document.getElementById('launch-form').style.display = 'none';
            document.getElementById('token-live-view').style.display = 'block';
            document.getElementById('live-tk-name').innerText = t.name + " ($"+t.symbol+")";
            document.getElementById('live-tk-logo').src = t.logo;
            document.getElementById('live-tk-ban').src = t.banner || '';
        }

        function backToLauncher() {
            document.getElementById('launch-form').style.display = 'block';
            document.getElementById('token-live-view').style.display = 'none';
        }

        function predict(side) {
            tg.showConfirm(`Predict GOLD will go ${side}?`, (ok) => {
                if(ok) tg.showAlert("Oracle Locked. Checking price...");
            });
        }

        tg.expand(); refresh(); setInterval(refresh, 5000);
    </script>
</body>
</html>
    """



# --- BOT SETUP ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message
    keyboard = [
        [InlineKeyboardButton("🚀 Launch WPT HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.reply_text(f"Welcome to WPT HUB!\n\nStart mining and creating tokens now.", reply_markup=reply_markup)

# Fonction pour lancer le Bot et FastAPI en même temps
def run_all():
    # Setup du bot
    if config.BOT_TOKEN:
        apps = ApplicationBuilder().token(config.BOT_TOKEN).build()
        apps.add_handler(CommandHandler("start", start_cmd))
        
        # Ici on lance FastAPI
        import threading
        def start_fastapi():
            uvicorn.run(app, host="0.0.0.0", port=8000)
        
        threading.Thread(target=start_fastapi, daemon=True).start()
        
        # On lance le bot
        print("🤖 Bot & API are running...")
        apps.run_polling()
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run_all()

