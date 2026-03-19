import os, sqlite3, asyncio, uvicorn, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = os.getenv("BOT_USERNAME", "OWPCsbot")

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "owpc_pro_v40.db")

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
    c.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    conn.commit(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome back to the Hub, {name}!", reply_markup=kb)

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
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "history": history, "clicks": r[5], "name": r[6], "top": top}

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.05
    col = "p_genesis" if t == 'genesis' else "p_unity" if t == 'unity' else "p_veo"
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET {col} = {col} + ?, total_clicks = total_clicks + 1 WHERE user_id = ?", (gain, uid))
    c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (?, ?, ?, ?)", (uid, t.upper(), gain, int(time.time())))
    conn.commit(); conn.close()
    return {"ok": True}

@app.post("/api/donate/{uid}")
async def donate_reward(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE users SET p_unity = p_unity + 10.0 WHERE user_id = ?", (uid,))
    c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (?, ?, ?, ?)", (uid, "STARS_BUY", 10.0, int(time.time())))
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
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; padding-bottom: 90px; overflow-x: hidden; }
        
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #161618; border-radius: 15px; margin-bottom: 20px; border: 1px solid #2c2c2e; }
        .user-info { display: flex; align-items: center; gap: 10px; }
        .avatar { width: 35px; height: 35px; background: var(--blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 14px; }
        
        /* New Stars Button Style */
        .donate-btn { 
            background: linear-gradient(135deg, #FFD700, #FFA500); 
            color: #000; border: none; padding: 7px 12px; border-radius: 12px; 
            font-size: 11px; font-weight: 900; cursor: pointer; 
            display: flex; align-items: center; gap: 5px;
            box-shadow: 0 0 10px rgba(255, 215, 0, 0.3);
        }

        .balance { text-align: center; margin-bottom: 10px; border: 1px solid #222; padding: 20px; border-radius: 25px; background: linear-gradient(145deg, #050505, #111); }
        .energy-container { width: 100%; height: 8px; background: #222; border-radius: 4px; margin-bottom: 15px; overflow: hidden; }
        .energy-fill { height: 100%; background: linear-gradient(90deg, var(--gold), #FFA500); width: 100%; transition: width 0.2s; }
        
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1C1C1E; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 15px; border-radius: 10px; font-weight: 700; cursor: pointer; min-width: 85px; }
        .btn:disabled { background: #333; color: #666; }
        
        .section-title { font-size: 12px; font-weight: 700; color: var(--text); margin: 20px 0 10px 5px; text-transform: uppercase; }
        .history-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #1c1c1e; font-size: 12px; color: var(--text); }
        
        .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(15,15,15,0.9); backdrop-filter: blur(15px); padding: 10px 30px; border-radius: 35px; display: flex; gap: 40px; border: 1px solid #333; }
        .nav-item { font-size: 24px; opacity: 0.3; }
        .nav-item.active { opacity: 1; transform: scale(1.2); }
    </style>
</head>
<body>
    <div class="profile-bar">
        <div class="user-info">
            <div class="avatar" id="u-avatar">?</div>
            <div style="font-size: 12px; font-weight: 700;" id="u-name">User</div>
        </div>
        <button class="donate-btn" onclick="buyStars()">50 ⭐ BUY UNITY</button>
    </div>

    <div id="p-mine">
        <div class="balance"><span>TOTAL ASSETS</span><h1 id="tot" style="font-size:42px; margin:5px 0">0.00</h1></div>
        <div style="display:flex; justify-content:space-between; font-size:10px; color:var(--gold); margin-bottom:5px">
            <span>⚡ ENERGY</span><span id="energy-text">100/100</span>
        </div>
        <div class="energy-container"><div id="energy-fill" class="energy-fill"></div></div>

        <div class="section-title">Mining Units</div>
        <div class="card">
            <div><small style="color:var(--green)">GENESIS</small><div id="gv" style="font-size:18px; font-weight:700">0.00</div></div>
            <button class="btn mine-btn" onclick="mine('genesis', event)" style="background:var(--green)">CLAIM</button>
        </div>
        <div class="card">
            <div><small style="color:#FFF">UNITY</small><div id="uv" style="font-size:18px; font-weight:700">0.00</div></div>
            <button class="btn mine-btn" onclick="mine('unity', event)">SYNC</button>
        </div>

        <div class="section-title">Recent History</div>
        <div id="history-list"></div>
    </div>

    <div class="nav"><div class="nav-item active">🏠</div><div class="nav-item" style="opacity:0.3">🏆</div></div>

    <script>
        let tg = window.Telegram.WebApp; tg.expand();
        const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;
        let energy = 100;

        async function buyStars() {
            tg.showConfirm("Are you sure you want to donate 50 ⭐ for 10.0 UNITY Points?", async (confirm) => {
                if(confirm) {
                    await fetch('/api/donate/' + uid, {method:'POST'});
                    tg.HapticFeedback.notificationOccurred('success');
                    tg.showAlert("🎉 FÉLICITATIONS !\n\nVotre achat de 50 Stars a été validé. 10.0 points UNITY ont été ajoutés à votre compte.");
                    setTimeout(() => { tg.close(); }, 2000);
                }
            });
        }

        setInterval(() => { if(energy < 100) { energy++; updateEnergyUI(); } }, 1500);

        function updateEnergyUI() {
            document.getElementById('energy-text').innerText = energy + "/100";
            document.getElementById('energy-fill').style.width = energy + "%";
            document.querySelectorAll('.mine-btn').forEach(b => b.disabled = energy <= 0);
        }

        async function refresh() {
            const r = await fetch('/api/user/' + uid);
            const d = await r.json();
            document.getElementById('u-name').innerText = d.name;
            document.getElementById('u-avatar').innerText = d.name.charAt(0).toUpperCase();
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('tot').innerText = (d.g + d.u + d.v).toFixed(2);

            // Updated History view
            let h_html = "";
            d.history.forEach(h => {
                let timeStr = new Date(h.ts * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                let color = h.t.includes('STARS') ? 'var(--gold)' : 'var(--text)';
                h_html += `<div class="history-item"><span style="color:${color}">${h.t}</span><b>+${h.a.toFixed(2)}</b><span>${timeStr}</span></div>`;
            });
            document.getElementById('history-list').innerHTML = h_html;
        }

        async function mine(t, e) {
            if(energy <= 0) return;
            energy--; updateEnergyUI();
            tg.HapticFeedback.impactOccurred('light');
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            refresh();
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
