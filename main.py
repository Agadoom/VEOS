import asyncio, uvicorn, time, random
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import config, database, missions 

# Initialisation forcée
database.init_db_structure()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- API ROUTES ---

@app.get("/api/user/{uid}")
async def api_get_user(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={})
    
    # Ordre SELECT de database.py : 
    # 0:p_genesis, 1:p_unity, 2:p_veo, 3:ref_count, 4:name, 5:energy, 6:last_upd, 7:streak, 8:staked
    p_gen = float(r[0] or 0)
    p_uni = float(r[1] or 0)
    p_veo = float(r[2] or 0)
    
    now = int(time.time())
    last_upd = r[6] if r[6] else now
    energy_now = int(min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_upd)/60)*config.REGEN_RATE))
    
    total_score = p_gen + p_uni + p_veo
    badge, next_goal, _ = missions.get_badge_info(total_score)
    
    return {
        "uid": uid, "name": r[4], 
        "g": round(p_gen, 2), "u": round(p_uni, 2), "v": round(p_veo, 2),
        "energy": energy_now, "max_energy": config.MAX_ENERGY, 
        "score": round(total_score, 2), "badge": badge, "next_goal": next_goal,
        "jackpot": round(database.get_total_network_score() * 0.1, 2),
        "top": [{"n": x[0], "p": round(x[1], 2), "b": missions.get_badge_info(x[1])[0]} for x in database.get_leaderboard()]
    }

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    conn = database.get_db_conn(); c = conn.cursor()
    try:
        now_ms = int(time.time()*1000)
        c.execute("SELECT energy, last_click_time FROM users WHERE user_id=%s", (uid,))
        res = c.fetchone()
        if res and (now_ms - (res[1] or 0)) >= 85 and res[0] >= 1:
            c.execute(f"UPDATE users SET p_{t}=p_{t}+0.05, energy=energy-1, last_energy_update=%s, last_click_time=%s WHERE user_id=%s", 
                      (int(time.time()), now_ms, uid))
            conn.commit(); return {"ok": True}
        return JSONResponse(status_code=400)
    except: conn.rollback(); return JSONResponse(status_code=500)
    finally: c.close(); conn.close()

@app.get("/api/launcher/list/{sort}")
async def api_list_tokens(sort: str):
    tokens = database.get_tokens_ordered(sort)
    # Retourne une liste propre pour le JS
    return [{"name": t[0], "symbol": t[1], "logo": t[2], "price": t[3], "holders": t[4], "mcap": round(t[5]*2, 2), "vol": t[6]} for t in tokens]

@app.post("/api/launcher/deploy")
async def api_deploy_token(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    conn = database.get_db_conn(); c = conn.cursor()
    try:
        # On vérifie précisément la colonne p_genesis (index 0 de notre SELECT habituel)
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        current_bal = float(res[0] or 0)
        
        print(f"DEBUG: User {uid} tente de deployer. Solde Genesis: {current_bal}")

        if current_bal < 500:
            return JSONResponse(status_code=400, content={"error": f"Solde insuffisant: {current_bal}/500"})
        
        # Déduction
        c.execute("UPDATE users SET p_genesis = p_genesis - 500 WHERE user_id = %s", (uid,))
        # Insertion avec toutes les valeurs par défaut pour éviter le NULL
        c.execute("""INSERT INTO community_tokens 
                     (creator_id, name, symbol, logo, price, reserve_wpt, holders, volume, created_at) 
                     VALUES (%s, %s, %s, %s, 0.0001, 500, 1, 0, %s)""", 
                  (uid, data.get("name"), data.get("symbol"), data.get("logo"), int(time.time())))
        
        conn.commit()
        print(f"DEBUG: Token {data.get('name')} crée avec succès !")
        return {"ok": True}
    except Exception as e:
        print(f"DEBUG ERROR: {e}")
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
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --green: #34C759; --purple: #A259FF; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; }
        .b-card { text-align: center; padding: 25px; border-radius: 20px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; }
        .card { background: var(--card); padding: 12px; border-radius: 15px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 8px 15px; border-radius: 10px; font-weight: bold; cursor: pointer; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(15px); padding: 10px 20px; border-radius: 30px; display: flex; gap: 20px; border: 1px solid #333; }
        .n-i { font-size: 18px; opacity: 0.3; } .n-i.active { opacity: 1; color: var(--purple); }
        .tabs { display: flex; gap: 10px; margin-bottom: 15px; border-bottom: 1px solid #222; }
        .tab { font-size: 11px; color: #555; padding: 8px 5px; cursor: pointer; }
        .tab.active { color: var(--purple); border-bottom: 2px solid var(--purple); font-weight: bold; }
        .modal { position: fixed; inset: 0; background: rgba(0,0,0,0.9); z-index: 200; display: none; align-items: center; justify-content: center; padding: 20px; }
        .input-group { background: #000; padding: 10px; border-radius: 10px; border: 1px solid #333; margin-bottom: 10px; width: 100%; box-sizing: border-box; }
        input { background: transparent; border: none; color: #FFF; width: 100%; outline: none; }
    </style>
</head>
<body>
    <div id="p-mine">
        <div class="b-card"><h1 id="tot">0.00</h1><small>TOTAL WPT</small></div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn" onclick="mine('genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine('unity')">MINE</button></div>
        <div class="card"><div><small style="color:var(--purple)">VEO AI</small><div id="vv">0.00</div></div><button class="btn" onclick="mine('veo')">MINE</button></div>
    </div>

    <div id="p-launcher" style="display:none">
        <button class="btn" style="width:100%; background:var(--purple); color:#FFF; margin-bottom:15px; padding:15px;" onclick="document.getElementById('m-create').style.display='flex'">🚀 LAUNCH TOKEN</button>
        <div class="tabs">
            <div id="t-new" class="tab active" onclick="switchTab(this, 'new')">NEW</div>
            <div class="tab" onclick="switchTab(this, 'mcap')">MARKET CAP</div>
        </div>
        <div id="tk-list"></div>
    </div>

    <div id="p-pillars" style="display:none"><h3 style="text-align:center;">🏛️ CORE PILLARS</h3></div>
    <div id="p-profile" style="display:none"><div class="b-card"><h2 id="pr-n">...</h2><div id="pr-b">...</div></div><div id="rank-list"></div></div>

    <div id="m-create" class="modal">
        <div style="background:var(--card); width:100%; padding:20px; border-radius:20px;">
            <h3>New Token</h3>
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
        <div onclick="show('pillars')" id="n-pillars" class="n-i">🏛️</div>
        <div onclick="show('profile')" id="n-profile" class="n-i">👤</div>
    </nav>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;

        async function refresh() {
            try {
                const r = await fetch(`/api/user/${uid}?t=${Date.now()}`);
                const d = await r.json();
                document.getElementById('tot').innerText = d.score.toFixed(2);
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('pr-n').innerText = d.name;
                document.getElementById('pr-b').innerText = d.badge;
                
                let lhtml = ""; d.top.forEach(x => { 
                    lhtml += `<div class="card"><div>${x.n}</div><b>${x.p}</b></div>`; 
                });
                document.getElementById('rank-list').innerHTML = lhtml;
            } catch(e) {}
        }

        async function loadTokens(sort) {
            const r = await fetch(`/api/launcher/list/${sort}?t=${Date.now()}`);
            const tokens = await r.json();
            let html = "";
            tokens.forEach(t => {
                html += `<div class="card">
                    <img src="${t.logo}" style="width:30px; height:30px; border-radius:50%; background:#333; object-fit:cover;">
                    <div style="flex:1; margin-left:10px;"><b>${t.name}</b><br><small>$${t.mcap}</small></div>
                    <div style="text-align:right"><b style="color:var(--green)">${t.price}</b></div>
                </div>`;
            });
            document.getElementById('tk-list').innerHTML = html || "<center style='opacity:0.5'>No tokens found</center>";
        }

        async function deploy() {
            const n = document.getElementById('tk-name').value;
            const s = document.getElementById('tk-sym').value;
            const l = document.getElementById('tk-logo').value;
            const res = await fetch('/api/launcher/deploy', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id:uid, name:n, symbol:s, logo:l})
            });
            if(res.ok) { 
                tg.showAlert("🚀 Token Live!"); 
                document.getElementById('m-create').style.display='none';
                loadTokens('new'); refresh();
            } else { 
                const err = await res.json();
                tg.showAlert("❌ " + (err.error || "Need 500 Genesis")); 
            }
        }

        function show(p) {
            ['mine','launcher','pillars','profile'].forEach(id => {
                document.getElementById('p-'+id).style.display = (id===p?'block':'none');
                document.getElementById('n-'+id).classList.toggle('active',id===p);
            });
            if(p==='launcher') loadTokens('new');
        }

        function switchTab(el, sort) {
            document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
            el.classList.add('active'); loadTokens(sort);
        }

        tg.expand(); refresh(); setInterval(refresh, 6000);
    </script>
</body>
</html>
    """

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
