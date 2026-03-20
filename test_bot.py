import os, asyncio, uvicorn, logging, time, random, datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import Forbidden

from data_conx import init_db, get_db_conn

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 1414016840 
PORT = int(os.getenv("PORT", 8080))
RAW_URL = os.getenv("WEBAPP_URL", "")
WEBAPP_URL = RAW_URL if RAW_URL.startswith("http") else f"https://{RAW_URL}"

logging.basicConfig(level=logging.INFO)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MAX_ENERGY = 100
REGEN_RATE = 1 

# --- AUTO-PATCH DB ---
def patch_db():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        for col, dtype in [
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"), 
            ("streak", "INTEGER DEFAULT 0"), 
            ("last_streak_date", "TEXT"),
            ("wallet_address", "TEXT")
        ]:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit(); c.close(); conn.close()

patch_db()

# --- UTILS ---
def get_badge(score, streak=0):
    if streak >= 7: return "🔥 Streak Master"
    if score >= 500: return "💎 Diamond"
    if score >= 150: return "🥇 Gold"
    if score >= 50:  return "🥈 Silver"
    return "🥉 Bronze"

# --- BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    if update.effective_chat.type in ['group', 'supergroup']: return 
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id, name, referred_by, energy, last_energy_update, staked_amount, streak) VALUES (%s, %s, %s, %s, %s, 0, 0)", 
                      (uid, name, ref_id, MAX_ENERGY, int(time.time())))
        conn.commit(); c.close(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text("✨ Welcome to OWPC DePIN Hub.\nNode Synchronized.", reply_markup=kb)

# --- API ---
@app.get("/tonconnect-manifest.json")
async def manifest():
    return {
        "url": WEBAPP_URL, "name": "One World Peace Coins",
        "iconUrl": "https://raw.githubusercontent.com/ton-blockchain/tutorials/main/03-client/test/public/ton.png"
    }

@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_streak_date, name, energy, last_energy_update, streak, staked_amount, wallet_address FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    now = int(time.time())
    last_upd = r[7] if r[7] else now
    current_e = min(MAX_ENERGY, (r[6] or 0) + ((now - last_upd) // 60) * REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    
    c.execute("SELECT name, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) as total FROM users ORDER BY total DESC LIMIT 8")
    top = [{"n": x[0], "p": round(x[1], 2), "b": get_badge(x[1])} for x in c.fetchall()]
    c.close(); conn.close()
    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[5],
        "energy": int(current_e), "max_energy": MAX_ENERGY, "badge": get_badge(score, r[8] or 0),
        "top": top, "multiplier": round(1.0 + ((r[9] or 0) / 100) * 0.1 + (score / 1000), 2),
        "can_claim": (r[4] != datetime.date.today().isoformat()), "streak": r[8] or 0, "staked": r[9] or 0,
        "wallet": r[10], "machine_load": random.randint(88, 99)
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    try:
        data = await request.json()
        uid, t = data.get("user_id"), data.get("token")
        conn = get_db_conn(); c = conn.cursor()
        
        # On récupère les valeurs avec COALESCE pour éviter les None
        c.execute("""
            SELECT energy, last_energy_update, 
                   COALESCE(staked_amount, 0), 
                   (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) 
            FROM users WHERE user_id = %s
        """, (uid,))
        
        res = c.fetchone()
        if not res: 
            return JSONResponse(status_code=404, content={"ok": False, "msg": "User not found"})
        
        energy = res[0]
        if energy < 1:
            return JSONResponse(status_code=400, content={"ok": False, "msg": "No energy"})

        # Calcul sécurisé du multiplicateur
        staked = res[2]
        total_assets = res[3]
        mult = 1.0 + (staked / 100) * 0.1 + (total_assets / 1000)
        gain = 0.05 * mult
        
        now = int(time.time())
        c.execute(f"UPDATE users SET p_{t} = COALESCE(p_{t},0) + %s, energy = energy - 1, last_energy_update = %s WHERE user_id = %s", (gain, now, uid))
        conn.commit(); c.close(); conn.close()
        
        return {"ok": True, "gain": round(gain, 3)}
    except Exception as e:
        logging.error(f"Mine error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

# --- WEB UI ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
    <script src="https://unpkg.com/@tonconnect/ui@latest/dist/tonconnect-ui.min.js"></script>
    <style>
        :root { --bg: #050505; --card: #111; --gold: #FFD700; --blue: #007AFF; --text: #8E8E93; --green: #34C759; }
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; }
        .header-ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px; font-size: 10px; display: flex; justify-content: space-between; border-bottom: 1px solid #333; }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2c2c2e; }
        .balance { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; position: relative; }
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; border: 1px solid #333; }
        .energy-fill { background: linear-gradient(90deg, #FFD700, #FFA500); height: 100%; width: 0%; transition: width 0.5s; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 11px; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); backdrop-filter: blur(20px); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 999; }
        .nav-item { font-size: 20px; opacity: 0.4; cursor: pointer; } 
        .nav-item.active { opacity: 1; color: var(--gold); }
        .gain-anim { position: absolute; color: var(--gold); font-weight: bold; pointer-events: none; animation: floatUp 1s forwards; z-index: 1000; }
        @keyframes floatUp { 0% { transform: translateY(0); opacity: 1; } 100% { transform: translateY(-50px); opacity: 0; } }
    </style>
</head>
<body>
    <div class="header-ticker"><span>$WPT: $0.00045</span><span style="color:var(--gold)">NODE ACTIVE</span></div>
    
    <div class="profile-bar">
        <div style="display:flex; align-items:center; gap:8px;">
            <div id="u-name" style="font-weight:bold; font-size:13px;">Loading...</div>
            <div id="u-badge" style="font-size:9px; padding:2px 6px; background:#222; color:var(--gold); border-radius:5px;">-</div>
        </div>
        <div id="u-ref" style="font-weight:bold; font-size:11px; color:var(--gold);">0 REFS</div>
    </div>

    <div id="p-mine">
        <div class="balance">
            <small style="color:var(--text)">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:45px; margin:8px 0;">0.00</h1>
            <div id="u-mult" style="font-size:10px; color:var(--green)">⚡ Multiplier: x1.0</div>
            <div class="energy-bar"><div id="e-bar" class="energy-fill"></div></div>
            <div id="e-text" style="font-size:11px; color:var(--gold);">⚡ 0 / 100</div>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn" onclick="mine('genesis', event)">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine('unity', event)">SYNC</button></div>
        <div class="card"><div><small style="color:#A259FF">VEO AI</small><div id="vv">0.00</div></div><button class="btn" onclick="mine('veo', event)" style="background:#A259FF; color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">$WPT PILLARS</h3>
        <div class="card"><b>World Peace Token</b><a href="https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA" target="_blank" class="btn">CLAIM</a></div>
        <div class="card"><b>Unity Asset</b><a href="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA" target="_blank" class="btn">CLAIM</a></div>
        <div class="card"><b>Veo AI Asset</b><a href="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA" target="_blank" class="btn">CLAIM</a></div>
        <div class="card"><b>Genesis Asset</b><a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" target="_blank" class="btn">CLAIM</a></div>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div id="p-mission" style="display:none">
        <h3 style="color:var(--gold)">WALLET & NODES</h3>
        <div id="ton-connect-button" style="display:flex; justify-content:center; margin-bottom:10px;"></div>
        <div id="wallet-status" style="text-align:center; font-size:11px; color:var(--text); margin-bottom:20px;">Checking...</div>
        <button id="change-wallet" class="btn" style="width:100%; margin-bottom:15px; display:none; background:#cc2929; color:white;" onclick="disconnectWallet()">CHANGE WALLET</button>
        <div class="card"><div><b>Active Nodes</b><br><small>Streak: <span id="u-streak">0</span> Days</small></div><div id="staked-val" style="color:var(--gold)">0 Staked</div></div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('mission')" id="n-mission" class="nav-item">⚙️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        const uid = tg.initDataUnsafe.user?.id || 0;

        const tonConnectUI = new TONConnectUI.TonConnectUI({
            manifestUrl: window.location.origin + '/tonconnect-manifest.json',
            buttonRootId: 'ton-connect-button'
        });

        tonConnectUI.onStatusChange(async (wallet) => {
            if (wallet) {
                await fetch('/api/connect-wallet', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ user_id: uid, address: wallet.account.address })
                });
                refresh();
            }
        });

        async function disconnectWallet() {
            await tonConnectUI.disconnect();
            await fetch('/api/connect-wallet', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ user_id: uid, address: null })
            });
            refresh();
        }

        async function refresh() {
            if(!uid) return;
            try {
                const r = await fetch(`/api/user/${uid}`); 
                const d = await r.json();
                if(!d.name) return;
                document.getElementById('u-name').innerText = d.name;
                document.getElementById('u-badge').innerText = d.badge;
                document.getElementById('u-ref').innerText = d.rc + " REFS";
                document.getElementById('gv').innerText = d.g.toFixed(2);
                document.getElementById('uv').innerText = d.u.toFixed(2);
                document.getElementById('vv').innerText = d.v.toFixed(2);
                document.getElementById('tot').innerText = (d.g+d.u+d.v).toFixed(2);
                document.getElementById('u-mult').innerText = `⚡ Multiplier: x${d.multiplier}`;
                document.getElementById('e-bar').style.width = (d.energy / d.max_energy * 100) + "%";
                document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
                
                if(d.wallet) {
                    document.getElementById('wallet-status').innerText = "✅ Connected: " + d.wallet.substring(0,6)+"..."+d.wallet.substring(d.wallet.length-4);
                    document.getElementById('wallet-status').style.color = "var(--green)";
                    document.getElementById('change-wallet').style.display = "block";
                } else {
                    document.getElementById('wallet-status').innerText = "Not Connected";
                    document.getElementById('change-wallet').style.display = "none";
                }

                let r_html = ""; 
                d.top.forEach((u, i) => { r_html += `<div class="card"><div>${i+1}. ${u.n}</div><b>${u.p}</b></div>`; });
                document.getElementById('rank-list').innerHTML = r_html;
            } catch(e) {}
        }

        async function mine(t, e) {
            const res = await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            if(res.ok) {
                const data = await res.json();
                showGainAnim(e, data.gain);
                tg.HapticFeedback.impactOccurred('light');
                refresh();
            }
        }

        function showGainAnim(e, val) {
            const anim = document.createElement('div');
            anim.className = 'gain-anim';
            anim.innerText = '+' + val;
            anim.style.left = e.pageX + 'px';
            anim.style.top = e.pageY + 'px';
            document.body.appendChild(anim);
            setTimeout(() => anim.remove(), 1000);
        }

        function show(p) {
            ['mine', 'pillars', 'leader', 'mission'].forEach(id => {
                document.getElementById('p-'+id).style.display = (id===p?'block':'none');
                document.getElementById('n-'+id).classList.toggle('active', id===p);
            });
        }
        
        // CORRECTION DÉMARRAGE : Forcer plusieurs tentatives de refresh
        window.onload = () => {
            let attempts = 0;
            let check = setInterval(() => {
                refresh();
                attempts++;
                if (attempts > 5) clearInterval(check);
            }, 1000);
            setInterval(refresh, 5000);
        };
    </script>
</body>
</html>
"""

async def main():
    global bot_app
    init_db()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize(); await bot_app.start()
    await bot_app.bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")).serve()

if __name__ == "__main__":
    asyncio.run(main())
