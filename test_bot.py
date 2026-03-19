import os, sqlite3, asyncio, uvicorn, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "owpc_pro_v41.db")

logging.basicConfig(level=logging.INFO)
app = FastAPI()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  p_genesis REAL DEFAULT 0, p_unity REAL DEFAULT 0, 
                  p_veo REAL DEFAULT 0, ref_count INTEGER DEFAULT 0,
                  total_clicks INTEGER DEFAULT 0,
                  last_daily INTEGER DEFAULT 0, referred_by INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                  token TEXT, amount REAL, timestamp INTEGER)''')
    conn.commit(); conn.close()

# --- BOT FUNCTIONS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    conn.commit(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC HUB, {name}!", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_daily, total_clicks, name FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    c.execute("SELECT token, amount, timestamp FROM logs WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,))
    history = [{"t": x[0], "a": x[1], "ts": x[2]} for x in c.fetchall()]
    c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    conn.close()
    if not r: return None
    can_daily = (int(time.time()) - r[4]) > 86400
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "can_daily": can_daily, "history": history, "clicks": r[5], "name": r[6], "top": top}

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    col = {"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}.get(t)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET {col} = {col} + ?, total_clicks = total_clicks + 1 WHERE user_id = ?", (gain, uid))
    c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (?, ?, ?, ?)", (uid, t.upper(), gain, int(time.time())))
    conn.commit(); conn.close()
    return {"ok": True}

@app.post("/api/buy-veo/{uid}")
async def buy_veo_reward(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE users SET p_veo = p_veo + 10.0 WHERE user_id = ?", (uid,))
    c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (?, 'VEO_BOOST', 10.0, ?)", (uid, int(time.time())))
    conn.commit(); conn.close()
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
        :root { --bg: #000; --card: #111; --blue: #007AFF; --green: #34C759; --gold: #FFD700; --text: #8E8E93; }
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 90px; }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #161618; border-radius: 15px; margin-bottom: 20px; border: 1px solid #2c2c2e; }
        .user-info { display: flex; align-items: center; gap: 10px; }
        .avatar { width: 35px; height: 35px; background: var(--blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; }
        
        /* Star Payment Button Style (Photo style) */
        .payer-btn { 
            background: #87a05e; color: #FFF; border: none; width: 100%; padding: 12px; 
            border-radius: 12px; font-weight: 600; font-size: 16px; cursor: pointer;
            display: flex; justify-content: center; align-items: center; gap: 8px; margin-top: 10px;
        }

        .balance { text-align: center; border: 1px solid #222; padding: 20px; border-radius: 25px; background: linear-gradient(145deg, #050505, #111); margin-bottom: 10px; }
        .energy-container { width: 100%; height: 8px; background: #222; border-radius: 4px; margin: 10px 0; overflow: hidden; }
        .energy-fill { height: 100%; background: linear-gradient(90deg, var(--gold), #FFA500); width: 100%; transition: width 0.2s; }
        
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1C1C1E; }
        .btn { background: #FFF; color: #000; border: none; padding: 8px 15px; border-radius: 10px; font-weight: 700; cursor: pointer; }
        .btn:disabled { background: #333; color: #666; }
        .section-title { font-size: 11px; font-weight: 700; color: var(--text); margin: 15px 0 8px 5px; text-transform: uppercase; }
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.9); backdrop-filter: blur(15px); padding: 10px 30px; border-radius: 35px; display: flex; gap: 40px; border: 1px solid #333; }
        .nav-item { font-size: 22px; opacity: 0.3; }
        .nav-item.active { opacity: 1; }
        .history-item { display: flex; justify-content: space-between; font-size: 12px; color: var(--text); padding: 5px 0; border-bottom: 1px solid #1c1c1e; }
    </style>
</head>
<body>
    <div class="profile-bar">
        <div class="user-info">
            <div class="avatar" id="u-avatar">?</div>
            <div style="font-size: 13px; font-weight: 700;" id="u-name">User</div>
        </div>
        <div style="text-align:right"><small style="color:var(--text); font-size:9px">CLICKS</small><div id="u-clicks" style="color:var(--gold); font-weight:bold">0</div></div>
    </div>

    <div id="p-mine">
        <div class="balance">
            <small>VEO BOOST 🚀</small>
            <div style="font-size:14px; margin: 10px 0;">Add +10.00 VEO to your account!</div>
            <button class="payer-btn" onclick="initPurchase()">Payer ⚡ 50</button>
        </div>

        <div class="balance"><span>TOTAL ASSETS</span><h1 id="tot" style="font-size:38px; margin:5px 0">0.00</h1></div>
        
        <div style="display:flex; justify-content:space-between; font-size:10px; color:var(--gold)">
            <span>⚡ ENERGY</span><span id="energy-text">100/100</span>
        </div>
        <div class="energy-container"><div id="energy-fill" class="energy-fill"></div></div>

        <div class="section-title">Mining Units</div>
        <div class="card">
            <div><small style="color:var(--green)">GENESIS</small><div id="gv" style="font-size:16px; font-weight:700">0.00</div></div>
            <button class="btn mine-btn" onclick="mine('genesis', event)" style="background:var(--green)">CLAIM</button>
        </div>
        <div class="card">
            <div><small style="color:#FFF">UNITY</small><div id="uv" style="font-size:16px; font-weight:700">0.00</div></div>
            <button class="btn mine-btn" onclick="mine('unity', event)">SYNC</button>
        </div>
        <div class="card">
            <div><small style="color:var(--blue)">VEO AI</small><div id="vv" style="font-size:16px; font-weight:700">0.00</div></div>
            <button class="btn mine-btn" onclick="mine('veo', event)" style="background:var(--blue);color:#FFF">COMPUTE</button>
        </div>

        <div class="section-title">History</div>
        <div id="history-list" style="margin-bottom:20px"></div>
    </div>

    <div id="p-leader" style="display:none">
        <div class="section-title">Leaderboard</div>
        <div id="rank-list"></div>
    </div>

    <div class="nav">
        <div onclick="show('mine')" id="n-mine" class="nav-item active">🏠</div>
        <div onclick="show('leader')" id="n-leader" class="nav-item">🏆</div>
    </div>

    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;
        let energy = 100;

        // Vraie méthode d'achat Telegram Stars
        function initPurchase() {
            // Dans une version de production, l'invoice_url est générée par votre backend via Telegram Bot API
            // Ici nous utilisons l'interface WebApp pour déclencher le paiement
            tg.openInvoice("https://t.me/stars_invoice_link_placeholder", function(status) {
                if(status == 'paid') {
                    fetch('/api/buy-veo/' + uid, {method:'POST'}).then(() => {
                        tg.showAlert("🚀 BOOST ACTIVÉ ! +10.00 VEO ajoutés.");
                        refresh();
                    });
                } else if(status == 'failed') {
                    tg.showAlert("L'achat a échoué.");
                }
                // Si l'utilisateur ferme simplement la fenêtre, rien ne se passe (pas de triche possible)
            });
            
            // Simulation pour test local (à retirer en prod) :
            if(!uid) { 
                tg.showConfirm("Simuler un paiement réussi ?", (ok) => {
                    if(ok) fetch('/api/buy-veo/0', {method:'POST'}).then(refresh);
                });
            }
        }

        setInterval(() => { if(energy < 100) { energy++; updateUI(); } }, 1500);

        function updateUI() {
            document.getElementById('energy-text').innerText = energy + "/100";
            document.getElementById('energy-fill').style.width = energy + "%";
            document.querySelectorAll('.mine-btn').forEach(b => b.disabled = energy <= 0);
        }

        async function refresh() {
            if(!uid && uid !== 0) return;
            const r = await fetch('/api/user/' + uid);
            const d = await r.json();
            document.getElementById('u-name').innerText = d.name;
            document.getElementById('u-clicks').innerText = d.clicks;
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('vv').innerText = d.v.toFixed(2);
            document.getElementById('tot').innerText = (d.g + d.u + d.v).toFixed(2);

            let h_html = "";
            d.history.forEach(h => {
                let color = h.t === 'VEO_BOOST' ? 'var(--gold)' : 'var(--text)';
                h_html += `<div class="history-item"><span style="color:${color}">${h.t}</span><b>+${h.a}</b></div>`;
            });
            document.getElementById('history-list').innerHTML = h_html;

            let r_html = "";
            d.top.forEach((u, i) => { r_html += `<div class="card"><span>${i+1}. ${u.n}</span><b>${u.p}</b></div>`; });
            document.getElementById('rank-list').innerHTML = r_html;
        }

        async function mine(t, e) {
            if(energy <= 0) return;
            energy--; updateUI();
            tg.HapticFeedback.impactOccurred('light');
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            refresh();
        }

        function show(p) {
            document.getElementById('p-mine').style.display = p=='mine'?'block':'none';
            document.getElementById('p-leader').style.display = p=='leader'?'block':'none';
            document.getElementById('n-mine').classList.toggle('active', p=='mine');
            document.getElementById('n-leader').classList.toggle('active', p=='leader');
        }

        refresh();
    </script>
</body>
</html>
    """

async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
