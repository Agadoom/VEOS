import os, asyncio, uvicorn, logging, time, random, datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from data_conx import init_db, get_db_conn

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
RAW_URL = os.getenv("WEBAPP_URL", "")
WEBAPP_URL = RAW_URL if RAW_URL.startswith("http") else f"https://{RAW_URL}"

logging.basicConfig(level=logging.INFO)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MAX_ENERGY = 100
REGEN_RATE = 1 
PASSIVE_RATE = 0.01 

# --- AUTO-PATCH DB ---
def patch_db():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        for col, dtype in [
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"), 
            ("streak", "INTEGER DEFAULT 0"), 
            ("last_streak_date", "TEXT"),
            ("wallet_address", "TEXT"),
            ("last_claim", "INTEGER")
        ]:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit(); c.close(); conn.close()
patch_db()

# --- BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id, name, referred_by, energy, last_energy_update, last_claim) VALUES (%s, %s, %s, %s, %s, %s)", 
                      (uid, name, ref_id, MAX_ENERGY, int(time.time()), int(time.time())))
            if ref_id:
                c.execute("UPDATE users SET p_unity = COALESCE(p_unity,0) + 10.0, ref_count = COALESCE(ref_count,0) + 1 WHERE user_id = %s", (ref_id,))
        conn.commit(); c.close(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text("✨ Node Synchronized.", reply_markup=kb)

# --- API ---
@app.get("/tonconnect-manifest.json")
async def manifest():
    return {
        "url": WEBAPP_URL,
        "name": "OWPC Hub",
        "iconUrl": "https://raw.githubusercontent.com/ton-blockchain/tutorials/main/03-client/test/public/ton.png"
    }

@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_streak_date, name, energy, last_energy_update, streak, staked_amount, wallet_address, last_claim FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    last_c = r[11] or now
    minutes_away = (now - last_c) // 60
    passive_gain = round(minutes_away * PASSIVE_RATE, 4) if minutes_away > 5 else 0
    current_e = min(MAX_ENERGY, (r[6] or 0) + ((now - (r[7] or now)) // 60) * REGEN_RATE)
    
    c.execute("SELECT name, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) as total FROM users ORDER BY total DESC LIMIT 8")
    top = [{"n": x[0], "p": round(x[1], 2), "b": "Node"} for x in c.fetchall()]
    
    c.execute("SELECT SUM(COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users")
    total_net = c.fetchone()[0] or 0
    c.close(); conn.close()

    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[5],
        "energy": int(current_e), "max_energy": MAX_ENERGY, "top": top,
        "jackpot": round(total_net * 0.1, 2), "staked": r[9] or 0, "wallet": r[10], 
        "passive": passive_gain, "multiplier": round(1.0 + ((r[9] or 0)/100)*0.1, 2)
    }

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json(); uid, t = data.get("user_id"), data.get("token")
    conn = get_db_conn(); c = conn.cursor()
    c.execute(f"UPDATE users SET p_{t}=p_{t}+0.05, energy=energy-1, last_energy_update=%s, last_claim=%s WHERE user_id=%s AND energy > 0", (int(time.time()), int(time.time()), uid))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

@app.post("/api/connect-wallet")
async def connect_wallet(request: Request):
    data = await request.json(); uid, addr = data.get("user_id"), data.get("address")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("UPDATE users SET wallet_address = %s WHERE user_id = %s", (addr, uid))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

@app.post("/api/claim-afk")
async def claim_afk(request: Request):
    data = await request.json(); uid = data.get("user_id")
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT last_claim FROM users WHERE user_id=%s", (uid,))
    mins = (int(time.time()) - c.fetchone()[0]) // 60
    gain = mins * PASSIVE_RATE
    c.execute("UPDATE users SET p_genesis=p_genesis+%s, last_claim=%s WHERE user_id=%s", (gain, int(time.time()), uid))
    conn.commit(); c.close(); conn.close(); return {"ok": True}

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
        body { background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 15px; padding-bottom: 100px; overflow-x: hidden; }
        
        .header-ticker { background: #1a1a1c; margin: -15px -15px 15px -15px; padding: 10px; font-size: 10px; display: flex; justify-content: space-between; border-bottom: 1px solid #333; }
        .machine-status { font-size: 9px; color: var(--text); margin-bottom: 12px; display: flex; justify-content: space-between; background: #111; padding: 8px; border-radius: 10px; border: 1px solid #222; align-items: center; }
        .status-led { height: 7px; width: 7px; background: var(--green); border-radius: 50%; display: inline-block; box-shadow: 0 0 8px var(--green); animation: pulse 1.5s infinite; margin-right:5px; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 15px; border: 1px solid #2c2c2e; }
        .balance { text-align: center; padding: 30px; border-radius: 25px; background: radial-gradient(circle at top, #1a1a1a, #000); border: 1px solid #222; margin-bottom: 15px; }
        
        .energy-bar { background: #222; border-radius: 10px; height: 8px; margin: 15px 0; overflow: hidden; position: relative; border: 1px solid #333; }
        .energy-fill { background: linear-gradient(90deg, #FFD700, #FFA500); height: 100%; width: 0%; transition: width 0.5s; }
        
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1c1c1e; position: relative; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 18px; border-radius: 12px; font-weight: 800; cursor: pointer; font-size: 11px; }
        
        /* Style Wallet Connecté */
        .wallet-box { background: #1a1a1c; border-radius: 15px; padding: 12px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border: 1px solid #333; }
        .wallet-info { display: flex; align-items: center; gap: 10px; }
        .wallet-icon { width: 30px; height: 30px; background: #007AFF; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
        
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,10,10,0.9); padding: 12px 25px; border-radius: 40px; display: flex; gap: 20px; border: 1px solid #333; z-index: 999; }
        .nav-item { font-size: 20px; opacity: 0.4; cursor: pointer; } .nav-item.active { opacity: 1; color: var(--gold); }
        
        .floating-text { position: absolute; color: var(--gold); font-weight: bold; pointer-events: none; animation: floatUp 0.8s ease-out forwards; font-size: 14px; }
        @keyframes floatUp { from { transform: translateY(0); opacity: 1; } to { transform: translateY(-40px); opacity: 0; } }
        
        #afk-modal { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 2000; display: none; align-items: center; justify-content: center; text-align: center; }
    </style>
</head>
<body>
    <div id="afk-modal">
        <div style="background:#111; padding:30px; border-radius:25px; border:1px solid var(--gold); width:80%;">
            <h2 style="color:var(--gold)">WELCOME BACK</h2>
            <h1 id="afk-val" style="font-size:40px; margin:10px 0;">0.00</h1>
            <button class="btn" onclick="claimAFK()" style="width:100%; padding:15px; background:var(--gold)">RECOVER ASSETS</button>
        </div>
    </div>

    <div class="header-ticker"><span>$WPT: $0.00045</span><span style="color:var(--gold)">JACKPOT: <span id="jack-val">0</span></span></div>
    <div class="machine-status"><span><span class="status-led"></span> NODE: ONLINE</span><span>LOAD: 98%</span></div>

    <div class="profile-bar">
        <div style="display:flex; align-items:center; gap:8px; margin-left:10px;">
            <div id="u-name" style="font-weight:700; font-size:13px;">...</div>
            <div style="font-size:9px; background:#222; color:var(--gold); padding:2px 6px; border-radius:5px;">NODE</div>
        </div>
        <div id="u-ref" style="font-weight:bold; font-size:11px; color:var(--gold); margin-right:10px;">0 REFS</div>
    </div>

    <div id="p-mine">
        <div class="balance">
            <small style="color:var(--text)">TOTAL ASSETS</small>
            <h1 id="tot" style="font-size:45px; margin:8px 0;">0.00</h1>
            <div class="energy-bar"><div id="e-bar" class="energy-fill"></div></div>
            <div id="e-text" style="font-size:11px; color:var(--gold);">⚡ 0 / 100</div>
        </div>
        <div class="card"><div><small style="color:var(--green)">GENESIS</small><div id="gv">0.00</div></div><button class="btn" onclick="mine(event, 'genesis')">MINE</button></div>
        <div class="card"><div><small style="color:var(--blue)">UNITY</small><div id="uv">0.00</div></div><button class="btn" onclick="mine(event, 'unity')">SYNC</button></div>
        <div class="card"><div><small style="color:#A259FF">VEO AI</small><div id="vv">0.00</div></div><button class="btn" onclick="mine(event, 'veo')" style="background:#A259FF; color:#FFF">COMPUTE</button></div>
    </div>

    <div id="p-pillars" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">$WPT PILLARS</h3>
        <div class="card"><b>World Peace Token</b><a href="https://t.me/blum/app?startapp=memepadjetton_WPT_a8MAF-ref_6VRKyJ9MZA" target="_blank" class="btn">CLAIM</a></div>
        <div class="card"><b>Unity Asset</b><a href="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA" target="_blank" class="btn">CLAIM</a></div>
        <div class="card"><b>Genesis Asset</b><a href="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA" target="_blank" class="btn">CLAIM</a></div>
    </div>

    <div id="p-mission" style="display:none">
        <h3 style="text-align:center; color:var(--gold)">STAKING & WALLET</h3>
        
        <div id="wallet-section">
             <div id="ton-connect-button" style="display:flex; justify-content:center; margin-bottom:15px;"></div>
             <div id="wallet-connected" class="wallet-box" style="display:none;">
                <div class="wallet-info">
                    <div class="wallet-icon"><img src="https://raw.githubusercontent.com/ton-blockchain/tutorials/main/03-client/test/public/ton.png" width="18"></div>
                    <div>
                        <div style="font-size:12px; font-weight:bold;">TON Wallet</div>
                        <div id="wallet-addr" style="font-size:10px; color:var(--text);">UQ...</div>
                    </div>
                </div>
                <button onclick="disconnectWallet()" style="background:none; border:none; color:#FF3B30; font-size:18px; cursor:pointer;">✕</button>
             </div>
        </div>

        <div class="card" style="border-color:var(--gold)">
            <div><b>Stake 100 Assets</b><br><small>Get +0.1x Multiplier</small></div>
            <button class="btn" onclick="stake()">LOCK</button>
        </div>
        <button class="btn" style="width:100%; margin-top:20px; background:var(--blue); color:#FFF; padding:15px;" onclick="share()">🚀 INVITE FRIENDS</button>
    </div>

    <div id="p-leader" style="display:none"><div id="rank-list"></div></div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('pillars')" id="n-pillars" class="nav-item">📊</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
        <div onclick="show('mission')" id="n-mission" class="nav-item">⚙️</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; const uid = tg.initDataUnsafe.user?.id || 0;
        const tonUI = new TONConnectUI.TonConnectUI({ 
            manifestUrl: window.location.origin + '/tonconnect-manifest.json', 
            buttonRootId: 'ton-connect-button' 
        });

        tonUI.onStatusChange(async (w) => {
            if(w) {
                const addr = w.account.address;
                document.getElementById('ton-connect-button').style.display = 'none';
                document.getElementById('wallet-connected').style.display = 'flex';
                document.getElementById('wallet-addr').innerText = addr.substring(0,4) + "..." + addr.substring(addr.length-4);
                await fetch('/api/connect-wallet', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, address:addr})});
            } else {
                document.getElementById('ton-connect-button').style.display = 'flex';
                document.getElementById('wallet-connected').style.display = 'none';
            }
            refresh();
        });

        async function disconnectWallet() { await tonUI.disconnect(); }

        async function refresh() {
            const r = await fetch(`/api/user/${uid}`); const d = await r.json();
            document.getElementById('u-name').innerText = d.name;
            document.getElementById('u-ref').innerText = d.rc + " REFS";
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('tot').innerText = (d.g+d.u+d.v).toFixed(2);
            document.getElementById('e-bar').style.width = (d.energy/d.max_energy*100)+"%";
            document.getElementById('e-text').innerText = `⚡ ${d.energy} / ${d.max_energy}`;
            document.getElementById('jack-val').innerText = d.jackpot;
            
            if(d.passive > 0.1 && document.getElementById('afk-modal').style.display !== 'flex') {
                document.getElementById('afk-val').innerText = "+" + d.passive.toFixed(2);
                document.getElementById('afk-modal').style.display = 'flex';
            }
        }

        async function mine(e, t) {
            const rect = e.target.getBoundingClientRect();
            const txt = document.createElement('div'); txt.className = 'floating-text';
            txt.innerText = '+0.05'; txt.style.left = (rect.left + 20) + 'px'; txt.style.top = rect.top + 'px';
            document.body.appendChild(txt); setTimeout(() => txt.remove(), 800);
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            refresh(); tg.HapticFeedback.impactOccurred('light');
        }

        async function claimAFK() {
            await fetch('/api/claim-afk', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid})});
            document.getElementById('afk-modal').style.display = 'none'; confetti(); refresh();
        }

        function share() {
            const url = `https://t.me/owpcsbot?start=${uid}`;
            tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=Join my DePIN Node!`);
        }

        function show(p) { ['mine','pillars','leader','mission'].forEach(id=>{document.getElementById('p-'+id).style.display=(id===p?'block':'none'); document.getElementById('n-'+id).classList.toggle('active',id===p);}); }
        refresh(); setInterval(refresh, 5000);
    </script>
</body>
</html>
"""

async def main():
    init_db(); bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize(); await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
