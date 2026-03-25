import asyncio, uvicorn, time, random
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import config, database, missions 

# Initialisation de la DB
database.init_db_structure()

app = FastAPI()
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# --- API ROUTES ---

@app.get("/api/user/{uid}")
async def api_get_user(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={})
    
    p_gen, p_uni, p_veo = float(r[0] or 0), float(r[1] or 0), float(r[2] or 0)
    now = int(time.time())
    last_upd = r[6] if r[6] else now
    en = int(min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_upd)/60)*config.REGEN_RATE))
    
    score = p_gen + p_uni + p_veo
    badge, next_goal, color = missions.get_badge_info(score)
    
    return {
        "uid": uid, "name": r[4], "g": round(p_gen, 2), "u": round(p_uni, 2), "v": round(p_veo, 2),
        "energy": en, "max_energy": config.MAX_ENERGY, "score": round(score, 2), 
        "badge": badge, "badge_color": color,
        "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "top": [{"n": x[0], "p": round(x[1], 2), "b": missions.get_badge_info(x[1])[0]} for x in database.get_leaderboard()]
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        now_ms = int(time.time()*1000)
        c.execute("SELECT energy, last_click_time FROM users WHERE user_id=%s", (uid,))
        res = c.fetchone()
        if res and (now_ms - (res[1] or 0)) >= 85 and res[0] >= 1:
            c.execute(f"UPDATE users SET p_{t}=p_{t}+0.05, energy=energy-1, last_energy_update=%s, last_click_time=%s WHERE user_id=%s", (int(time.time()), now_ms, uid))
            conn.commit()
            return {"ok": True}
        return JSONResponse(status_code=400)
    except:
        conn.rollback()
        return JSONResponse(status_code=500)
    finally:
        c.close()
        conn.close()

@app.get("/api/launcher/list/{sort}")
async def api_list_tokens(sort: str):
    tokens = database.get_tokens_ordered(sort)
    return [{"name": t[0], "symbol": t[1], "logo": t[2], "price": t[3], "mcap": round(t[5]*2, 2), "vol": t[6]} for t in tokens]

@app.post("/api/launcher/deploy")
async def api_deploy_token(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res or float(res[0] or 0) < 500: 
            return JSONResponse(status_code=400, content={"error": "Need 500 Genesis"})
        
        c.execute("UPDATE users SET p_genesis = p_genesis - 500 WHERE user_id = %s", (uid,))
        c.execute("INSERT INTO community_tokens (creator_id, name, symbol, logo, price, reserve_wpt, holders, volume, created_at) VALUES (%s, %s, %s, %s, 0.0001, 500, 1, 0, %s)", (uid, data.get("name"), data.get("symbol"), data.get("logo"), int(time.time())))
        conn.commit()
        return {"ok": True}
    except:
        conn.rollback()
        return JSONResponse(status_code=500)
    finally:
        c.close()
        conn.close()

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --green: #34C759; --purple: #A259FF; --text: #888; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        .ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px 0; border-bottom: 1px solid #333; overflow: hidden; white-space: nowrap; font-size: 10px; font-weight: bold; }
        .t-wrap { display: inline-block; animation: scroll 20s linear infinite; }
        @keyframes scroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
        .b-card { text-align: center; padding: 30px 20px; border-radius: 25px; background: radial-gradient(circle at top, #1c1c1e, #000); border: 1px solid #222; margin-bottom: 20px; }
        .b-card h1 { font-size: 42px; margin: 10px 0; }
        .e-bar { background: #222; height: 8px; border-radius: 4px; margin: 15px 0; overflow: hidden; }
        .e-fill { background: linear-gradient(90deg, var(--gold), #FFA500); height: 100%; width: 0%; transition: width 0.4s ease; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: bold; cursor: pointer; }
        .nav { position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.85); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 35px; display: flex; gap: 25px; border: 1px solid #333; z-index: 100; }
        .n-i { font-size: 22px; opacity: 0.25; cursor: pointer; }
        .n-i.active { opacity: 1; color: var(--purple); }
        .modal { position: fixed; inset: 0; background: rgba(0,0,0,0.96); z-index: 200; display: none; align-items: center; justify-content: center; padding: 25px; }
        .m-content { background: var(--card); width: 100%; padding: 25px; border-radius: 25px; }
        .input-group { background: #000; padding: 12px; border-radius: 15px; border: 1px solid #222; margin-bottom: 12px; }
        input { background: transparent; border: none; color: #FFF; width: 100%; outline: none; }
        .tabs { display: flex; gap: 15px; margin-bottom: 15px; border-bottom: 1px solid #222; }
        .tab { font-size: 12px; color: #555; padding: 10px 5px; cursor: pointer; }
        .tab.active { color: var(--purple); border-bottom: 2px solid var(--purple); }
    </style>
</head>
<body>
    <div class="ticker"><div class="t-wrap">
        <span style="margin-right:40px; color:var(--gold)">🏆 NETWORK JACKPOT: <span id="jk-v">0</span> WPT</span>
        <span style="color:var(--green)">● ALL SYSTEMS ONLINE</span>
    </div></div>

    <div id="p-mine">
        <div class="b-card">
            <small style="color:var(--text)">Balance</small>
            <h1 id="tot">0.00</h1>
            <div class="e-bar"><div id="e-f" class="e-fill"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:10px; color:var(--gold)">
                <span>ENERGY</span><span id="e-t">0 / 100</span>
            </div>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn" onclick="mine('genesis')">Mine</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine('unity')">Sync</button></div>
        <div class="card"><div><small style="color:var(--purple)">VEO AI</small><div id="vv">0.00</div></div><button class="btn" style="background:var(--purple); color:#FFF" onclick="mine('veo')">Compute</button></div>
    </div>

    <div id="p-launcher" style="display:none">
        <button class="btn" style="width:100%; background:var(--purple); color:#FFF; padding:18px; border-radius:20px; margin-bottom:15px;" onclick="document.getElementById('m-create').style.display='flex'">🚀 LAUNCH TOKEN</button>
        <div class="tabs"><div id="t-new" class="tab active" onclick="switchTab(this, 'new')">NEWEST</div><div class="tab" onclick="switchTab(this, 'mcap')">TOP MCAP</div></div>
        <div id="tk-list"></div>
    </div>

    <div id="p-profile" style="display:none">
        <div class="b-card"><div style="font-size:50px;">🛡️</div><h2 id="pr-n">...</h2><div id="pr-b" style="color:var(--gold)">...</div></div>
        <div id="rank-list"></div>
    </div>

    <div id="m-create" class="modal">
        <div class="m-content">
            <h2>Create Token</h2>
            <div class="input-group"><input type="text" id="tk-name" placeholder="Name"></div>
            <div class="input-group"><input type="text" id="tk-sym" placeholder="Symbol"></div>
            <div class="input-group"><input type="text" id="tk-logo" placeholder="Logo URL"></div>
            <button class="btn" style="width:100%; background:var(--green); color:#FFF;" onclick="deploy()">DEPLOY (500 WPT)</button>
            <button class="btn" style="width:100%; background:#222; color:#FFF; margin-top:10px;" onclick="document.getElementById('m-create').style.display='none'">CANCEL</button>
        </div>
    </div>

    <nav class="nav">
        <div onclick="show('mine')" id="n-mine" class="n-i active">🏠</div>
        <div onclick="show('launcher')" id="n-launcher" class="n-i">🚀</div>
        <div onclick="show('profile')" id="n-profile" class="n-i">👤</div>
    </nav>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        let lastJackpot = 0; window.mineCount = 0;

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}?t=${Date.now()}`);
                const d = await r.json();
                if (lastJackpot > 0 && d.jackpot < lastJackpot) { tg.showAlert("🎉 JACKPOT DISTRIBUTED!"); }
                lastJackpot = d.jackpot;
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('e-f').style.width = (d.energy / d.max_energy * 100) + "%";
                document.getElementById('e-t').innerText = `${d.energy} / ${d.max_energy}`;
                document.getElementById('jk-v').innerText = d.jackpot.toLocaleString();
                document.getElementById('pr-n').innerText = d.name;
                document.getElementById('pr-b').innerText = d.badge;
                let lhtml = ""; d.top.forEach((x, i) => { lhtml += `<div class="card"><div>#${i+1} ${x.n}</div><b>${x.p}</b></div>`; });
                document.getElementById('rank-list').innerHTML = lhtml;
            } catch(e) {}
        }

        async function mine(t) {
            const res = await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) {
                tg.HapticFeedback.impactOccurred('medium');
                const el = document.getElementById(t === 'genesis' ? 'gv' : (t === 'unity' ? 'uv' : 'vv'));
                el.innerText = (parseFloat(el.innerText) + 0.05).toFixed(2);
                if(window.mineCount % 3 === 0) refresh();
                window.mineCount++;
            }
        }

        async function loadTokens(sort) {
            const r = await fetch(`/api/launcher/list/${sort}?t=${Date.now()}`);
            const tokens = await r.json();
            let html = "";
            tokens.forEach(t => {
                const img = t.logo || 'https://cdn-icons-png.flaticon.com/512/2584/2584687.png';
                html += `<div class="card"><img src="${img}" style="width:38px; height:38px; border-radius:12px; object-fit:cover;"><div style="flex:1; margin-left:12px;"><b>${t.name}</b><br><small>$${t.mcap.toLocaleString()}</small></div><div style="text-align:right"><b style="color:var(--green)">${t.price}</b></div></div>`;
            });
            document.getElementById('tk-list').innerHTML = html || "<center>No tokens</center>";
        }

        async function deploy() {
            const res = await fetch('/api/launcher/deploy', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, name:document.getElementById('tk-name').value, symbol:document.getElementById('tk-sym').value, logo:document.getElementById('tk-logo').value})});
            if(res.ok) { tg.showAlert("🚀 Token deployed!"); document.getElementById('m-create').style.display='none'; show('launcher'); }
        }

        function show(p) {
            ['mine','launcher','profile'].forEach(id => { document.getElementById('p-'+id).style.display = (id===p?'block':'none'); document.getElementById('n-'+id).classList.toggle('active',id===p); });
            if(p==='launcher') loadTokens('new');
            refresh();
        }

        function switchTab(el, sort) { document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active')); el.classList.add('active'); loadTokens(sort); }

        tg.expand(); refresh(); setInterval(refresh, 7000);
    </script>
</body>
</html>
    """

# --- LOGIQUE JACKPOT ---

async def distribute_jackpot():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT user_id FROM users ORDER BY (p_genesis + p_unity + p_veo) DESC LIMIT 10")
        winners = c.fetchall()
        if winners:
            share = 10000 / len(winners)
            for w in winners:
                c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (share, w[0]))
            conn.commit()
            return True
        return False
    except:
        return False
    finally:
        c.close()
        conn.close()

@app.post("/api/admin/force-jackpot")
async def api_force_jackpot(request: Request):
    success = await distribute_jackpot()
    return {"success": success}

# --- BOT SETUP ---

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    await missions.register_user(uid, name, None)
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
