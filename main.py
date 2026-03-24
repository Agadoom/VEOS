import asyncio, uvicorn, time, random, threading
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import config, database, missions 

database.init_db_structure()
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@@app.get("/api/user/{uid}")
async def api_get_user(uid: int):
    # On récupère les données
    r = database.get_user_full(uid)
    if not r: 
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    # IMPORTANT : L'ordre doit correspondre au SELECT dans database.get_user_full
    # r[0]=p_genesis, r[1]=p_unity, r[2]=p_veo, r[3]=ref_count, r[4]=name...
    
    p_gen = r[0] or 0.0
    p_uni = r[1] or 0.0
    p_veo = r[2] or 0.0
    
    now = int(time.time())
    last_upd = r[6] if r[6] else now
    
    # Calcul de l'énergie avec les variables de config
    current_energy = int(min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_upd)/60)*config.REGEN_RATE))
    
    score_total = p_gen + p_uni + p_veo
    badge, next_goal, _ = missions.get_badge_info(score_total)
    
    return {
        "uid": uid, 
        "name": r[4], 
        "g": round(p_gen, 2), 
        "u": round(p_uni, 2), 
        "v": round(p_veo, 2),
        "energy": current_energy, 
        "max_energy": config.MAX_ENERGY, 
        "score": round(score_total, 2), 
        "badge": badge,
        "next_goal": next_goal, 
        "staked": r[8] or 0, 
        "streak": r[7] or 0,
        "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "top": [{"n": x[0], "p": round(x[1], 2), "b": missions.get_badge_info(x[1])[0]} for x in database.get_leaderboard()]
    }


@app.post("/api/launcher/deploy")
async def api_deploy_token(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = database.get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        bal = c.fetchone()
        if not bal or bal[0] < 500: return JSONResponse(status_code=400, content={"error": "Need 500 Genesis"})
        
        c.execute("UPDATE users SET p_genesis = p_genesis - 500 WHERE user_id = %s", (uid,))
        c.execute("""INSERT INTO community_tokens (creator_id, name, symbol, logo, reserve_wpt, created_at) 
                     VALUES (%s, %s, %s, %s, 500, %s)""", 
                  (uid, data.get("name"), data.get("symbol"), data.get("logo"), int(time.time())))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback(); return JSONResponse(status_code=500, content={"error": str(e)})
    finally: c.close(); conn.close()

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --green: #34C759; --purple: #A259FF; --red: #FF3B30; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; }
        .ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; font-size: 10px; }
        .t-wrap { display: inline-block; animation: scroll 25s linear infinite; }
        @keyframes scroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
        .b-card { text-align: center; padding: 25px; border-radius: 20px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; }
        .card { background: var(--card); padding: 12px; border-radius: 15px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 8px 15px; border-radius: 10px; font-weight: bold; cursor: pointer; font-size: 11px; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(15px); padding: 10px 20px; border-radius: 30px; display: flex; gap: 20px; border: 1px solid #333; z-index: 100; }
        .n-i { font-size: 18px; opacity: 0.3; } .n-i.active { opacity: 1; color: var(--purple); }
        .tabs { display: flex; gap: 10px; margin-bottom: 15px; border-bottom: 1px solid #222; }
        .tab { font-size: 10px; color: #555; padding: 8px 5px; cursor: pointer; }
        .tab.active { color: var(--purple); border-bottom: 2px solid var(--purple); font-weight: bold; }
        .modal { position: fixed; inset: 0; background: rgba(0,0,0,0.95); z-index: 200; display: none; align-items: center; justify-content: center; padding: 20px; flex-direction: column; }
        .input-group { background: #000; padding: 10px; border-radius: 10px; border: 1px solid #333; margin-bottom: 10px; width: 100%; box-sizing: border-box; }
        input { background: transparent; border: none; color: #FFF; width: 100%; outline: none; }
    </style>
</head>
<body>
    <div class="ticker"><div class="t-wrap">
        <span style="margin-right:30px; color:var(--gold)">🔥 NETWORK JACKPOT: <span id="jk-v">0</span> WPT</span>
        <span style="color:var(--green)">🟢 PILLARS ONLINE</span>
    </div></div>

    <div id="p-mine">
        <div class="b-card">
            <h1 id="tot">0.00</h1>
            <small style="color:var(--purple)">TOTAL WPT BALANCE</small>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
        <div class="card"><div><small style="color:var(--purple)">VEO AI</small><div id="vv">0.00</div></div><button class="btn" onclick="mine('veo')" style="background:var(--purple); color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="text-align:center; color:var(--green)">🏛️ CORE PILLARS</h3>
        <div class="card"><div><b>Genesis Asset</b><br><small>Main Liquidity</small></div><button class="btn" onclick="tg.openLink('https://t.me/blum')">STAKE</button></div>
        <div class="card"><div><b>Unity Asset</b><br><small>Community Power</small></div><button class="btn" onclick="tg.openLink('https://t.me/blum')">VOTE</button></div>
        <div class="card"><div><b>Veo AI</b><br><small>Compute Power</small></div><button class="btn" onclick="tg.openLink('https://t.me/blum')">UPGRADE</button></div>
    </div>

    <div id="p-launcher" style="display:none">
        <button class="btn" style="width:100%; background:var(--purple); color:#FFF; margin-bottom:15px; padding:15px;" onclick="document.getElementById('m-create').style.display='flex'">🚀 LAUNCH NEW TOKEN</button>
        <div class="tabs">
            <div id="t-new" class="tab active" onclick="switchTab(this, 'new')">NEW</div>
            <div id="t-mcap" class="tab" onclick="switchTab(this, 'mcap')">MARKET CAP</div>
            <div id="t-vol" class="tab" onclick="switchTab(this, 'vol')">VOLUME</div>
        </div>
        <div id="tk-list"></div>
    </div>

    <div id="p-profile" style="display:none">
        <div class="b-card">
            <div style="font-size:30px;">👤</div>
            <h2 id="pr-n" style="margin:5px 0;">...</h2>
            <div id="pr-b" style="color:var(--gold); font-size:12px;">...</div>
        </div>
        <h3 style="text-align:center;">🏆 TOP HOLDERS</h3>
        <div id="rank-list"></div>
    </div>

    <div id="m-create" class="modal">
        <div style="background:var(--card); width:100%; padding:20px; border-radius:20px; border:1px solid var(--purple);">
            <h3>Deploy Token</h3>
            <div class="input-group"><input type="text" id="tk-name" placeholder="Token Name"></div>
            <div class="input-group"><input type="text" id="tk-sym" placeholder="Symbol (ex: SOL)"></div>
            <div class="input-group"><input type="text" id="tk-logo" placeholder="Logo URL (https://...)"></div>
            <button class="btn" style="width:100%; background:var(--green); color:#FFF; padding:12px;" onclick="deploy()">DEPLOY (500 WPT)</button>
            <button class="btn" style="width:100%; background:#222; color:#FFF; margin-top:10px;" onclick="document.getElementById('m-create').style.display='none'">CANCEL</button>
        </div>
    </div>

    <div id="m-trade" class="modal">
        <div style="background:var(--card); width:100%; padding:20px; border-radius:20px;">
            <h3 id="tr-title">Trade</h3>
            <div class="input-group"><input type="number" id="tr-amt" oninput="calcTrade()" placeholder="WPT Amount"></div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-bottom:15px;">
                <button class="btn" style="background:#222; color:#FFF" onclick="setAmt(25)">25%</button>
                <button class="btn" style="background:#222; color:#FFF" onclick="setAmt(50)">50%</button>
                <button class="btn" style="background:var(--purple); color:#FFF" onclick="setAmt(100)">MAX</button>
            </div>
            <div id="tr-res" style="background:#000; padding:15px; border-radius:10px; color:var(--green); text-align:center;">Receive: 0 tokens</div>
            <button class="btn" style="width:100%; background:var(--green); color:#FFF; margin-top:15px; padding:12px;" onclick="tg.showAlert('Trade Executed!')">CONFIRM TRADE</button>
            <button class="btn" style="width:100%; background:#222; color:#FFF; margin-top:10px;" onclick="document.getElementById('m-trade').style.display='none'">CLOSE</button>
        </div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="n-i active">🏠</div>
        <div onclick="show('launcher')" id="n-launcher" class="n-i">🚀</div>
        <div onclick="show('pillars')" id="n-pillars" class="n-i">🏛️</div>
        <div onclick="show('profile')" id="n-profile" class="n-i">👤</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let userBalance = 0; let currentPrice = 0.0001;

        function show(p) {
            ['mine','launcher','pillars','profile'].forEach(id=>{
                document.getElementById('p-'+id).style.display=(id===p?'block':'none');
                document.getElementById('n-'+id).classList.toggle('active',id===p);
            });
            if(p==='launcher') loadTokens('new');
        }

        async function refresh() {
            try {
                // Anti-cache technique
                const r = await fetch(`/api/user/${uid}?t=${Date.now()}`); 
                const d = await r.json();
                userBalance = d.score;
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('pr-n').innerText = d.name;
                document.getElementById('pr-b').innerText = d.badge;
                document.getElementById('jk-v').innerText = d.jackpot.toLocaleString();
                
                let lhtml = ""; d.top.forEach(x => { 
                    lhtml += `<div class="card"><div>${x.n} <small style="color:var(--text)">${x.b}</small></div><b>${x.p}</b></div>`; 
                });
                document.getElementById('rank-list').innerHTML = lhtml;
            } catch(e) {}
        }

        async function loadTokens(sort) {
            // Anti-cache technique sur la liste
            const r = await fetch(`/api/launcher/list/${sort}?t=${Date.now()}`);
            const tokens = await r.json();
            let html = "";
            tokens.forEach(t => {
                html += `<div class="card" onclick="openTrade('${t.name}', ${t.price})">
                    <img src="${t.logo || ''}" style="width:35px; height:35px; border-radius:50%; background:#333; object-fit:cover;">
                    <div style="flex:1; margin-left:12px;"><b>${t.name}</b><br><small style="color:#888;">$${t.mcap}</small></div>
                    <div style="text-align:right"><b style="color:var(--green)">${t.price}</b><br><small style="color:var(--purple)">VOL: ${t.vol}</small></div>
                </div>`;
            });
            document.getElementById('tk-list').innerHTML = html || "<center style='margin-top:20px;'><small>No tokens found</small></center>";
        }

        async function deploy() {
            const n = document.getElementById('tk-name').value;
            const s = document.getElementById('tk-sym').value;
            const l = document.getElementById('tk-logo').value;
            if(!n || !s) return tg.showAlert("Name and Symbol required!");

            const res = await fetch('/api/launcher/deploy', {
                method: 'POST',
                body: JSON.stringify({user_id:uid, name:n, symbol:s, logo:l})
            });

            if(res.ok) {
                tg.showAlert("🚀 Token Live!");
                document.getElementById('m-create').style.display='none';
                document.getElementById('tk-name').value=""; document.getElementById('tk-sym').value="";
                switchTab(document.getElementById('t-new'), 'new'); // Recharge direct les nouveaux
                refresh();
            } else {
                tg.showAlert("❌ Need 500 Genesis WPT");
            }
        }

        function switchTab(el, sort) {
            document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
            el.classList.add('active'); loadTokens(sort);
        }

        function openTrade(name, price) {
            currentPrice = price; 
            document.getElementById('tr-title').innerText = "Trade " + name;
            document.getElementById('m-trade').style.display = 'flex';
        }

        function setAmt(pct) {
            document.getElementById('tr-amt').value = (userBalance * (pct/100)).toFixed(2);
            calcTrade();
        }

        function calcTrade() {
            const amt = document.getElementById('tr-amt').value || 0;
            document.getElementById('tr-res').innerText = "Receive: " + Math.floor(amt / currentPrice).toLocaleString() + " tokens";
        }

        async function mine(t) {
            const res = await fetch('/api/mine', {method:'POST', body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) { tg.HapticFeedback.impactOccurred('light'); refresh(); }
        }

        tg.expand(); refresh(); setInterval(refresh, 8000);
    </script>
</body>
</html>
    """


# --- BOT SETUP ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    await missions.register_user(uid, name, ref)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome {name}!", reply_markup=kb)

async def main_loop():
    bot = ApplicationBuilder().token(config.TOKEN).build()
    bot.add_handler(CommandHandler("start", start_cmd))
    await bot.initialize()
    await bot.bot.delete_webhook(drop_pending_updates=True)
    await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    c = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    await uvicorn.Server(c).serve()

if __name__ == "__main__":
    asyncio.run(main_loop())