import os, sqlite3, asyncio, uvicorn, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = os.getenv("BOT_USERNAME", "OWPCsbot")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "owpc_pro_v39.db")

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
    conn.commit(); conn.close()

# --- BOT PAYMENTS & LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    conn.commit(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome {name}! Support us with Stars to get Unity points!", reply_markup=kb)

async def donate_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Cette fonction est appelée via un lien telegram (ex: /donate) ou bouton
    chat_id = update.effective_chat.id
    title = "Support OWPC Ecosystem"
    description = "Get +10 UNITY Points instantly!"
    payload = "donate_10_unity"
    currency = "XTR" # Telegram Stars
    price = [LabeledPrice("10 Unity Points", 50)] # 50 Stars

    await context.bot.send_invoice(chat_id, title, description, payload, "", currency, price)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE users SET p_unity = p_unity + 10.0 WHERE user_id = ?", (uid,))
    conn.commit(); conn.close()
    await update.message.reply_text("🎉 Thank you! +10 UNITY points added to your balance. Re-open the app to see changes!")

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_daily, total_clicks, name FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    if not r: return None
    return {"g": r[0], "u": r[1], "v": r[2], "clicks": r[5], "name": r[6]}

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    col = {"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}.get(t)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET {col} = {col} + ?, total_clicks = total_clicks + 1 WHERE user_id = ?", (gain, uid))
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
        body { background: var(--bg); color: #FFF; font-family: -apple-system, sans-serif; margin: 0; padding: 15px; }
        .profile-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #161618; border-radius: 15px; margin-bottom: 20px; border: 1px solid #2c2c2e; }
        .balance { text-align: center; margin-bottom: 10px; border: 1px solid #222; padding: 20px; border-radius: 25px; background: linear-gradient(145deg, #050505, #111); }
        .energy-container { width: 100%; height: 8px; background: #222; border-radius: 4px; margin-bottom: 10px; overflow: hidden; }
        .energy-fill { height: 100%; background: var(--gold); width: 100%; transition: 0.2s; }
        .card { background: var(--card); padding: 15px; border-radius: 18px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1C1C1E; }
        .btn { background: #FFF; color: #000; border: none; padding: 10px 15px; border-radius: 10px; font-weight: 700; cursor: pointer; }
        .btn-star { background: var(--gold); color: #000; width: 100%; margin-top: 10px; padding: 12px; border-radius: 12px; font-weight: 800; border: none; }
    </style>
</head>
<body>
    <div class="profile-bar">
        <div id="u-name" style="font-weight:700">User</div>
        <div style="font-size:12px; color:var(--gold)">Clicks: <span id="total-clicks">0</span></div>
    </div>

    <div class="balance"><span>TOTAL ASSETS</span><h1 id="tot">0.00</h1></div>
    
    <div class="energy-container"><div id="energy-fill" class="energy-fill"></div></div>
    <div style="text-align:center; font-size:10px; color:var(--gold); margin-bottom:20px">⚡ ENERGY: <span id="energy-val">100</span>/100</div>

    <div class="card">
        <div><small>GENESIS</small><div id="gv">0.00</div></div>
        <button class="btn" onclick="mine('genesis', event)">CLAIM</button>
    </div>
    <div class="card">
        <div><small>UNITY</small><div id="uv">0.00</div></div>
        <button class="btn" onclick="mine('unity', event)">SYNC</button>
    </div>

    <div style="margin-top:30px; border-top: 1px solid #222; padding-top:20px">
        <div style="text-align:center; font-size:12px; color:var(--text); margin-bottom:10px">WANT MORE POINTS?</div>
        <button class="btn-star" onclick="buyStars()">🌟 BUY 10 UNITY (50 STARS)</button>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;
        let energy = 100;

        function buyStars() {
            // Ferme l'app et envoie la commande de don au bot
            tg.sendData("donate_stars"); // Alternativement, on peut utiliser un lien direct :
            tg.openTelegramLink("https://t.me/""" + BOT_USERNAME + r"""?start=donate");
            tg.close();
        }

        async function refresh() {
            const r = await fetch('/api/user/' + uid);
            const d = await r.json();
            document.getElementById('u-name').innerText = d.name;
            document.getElementById('total-clicks').innerText = d.clicks;
            document.getElementById('gv').innerText = d.g.toFixed(2);
            document.getElementById('uv').innerText = d.u.toFixed(2);
            document.getElementById('tot').innerText = (d.g + d.u + d.v).toFixed(2);
        }

        async function mine(t, e) {
            if(energy <= 0) return;
            energy--;
            document.getElementById('energy-val').innerText = energy;
            document.getElementById('energy-fill').style.width = energy + '%';
            await fetch('/api/mine', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:uid, token:t})});
            refresh();
        }

        setInterval(() => { if(energy < 100) { energy++; updateUI(); } }, 2000);
        function updateUI() { 
            document.getElementById('energy-val').innerText = energy; 
            document.getElementById('energy-fill').style.width = energy + '%';
        }
        refresh();
    </script>
</body>
</html>
    """

async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers pour les paiements
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # Handler spécial pour le bouton de don via deep link
    async def handle_donate_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.args and context.args[0] == "donate":
            await donate_stars(update, context)
    bot.add_handler(CommandHandler("start", handle_donate_link, filters=filters.Regex("donate")))

    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
