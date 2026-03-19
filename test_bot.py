import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, PreCheckoutQueryHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURATION DU STOCKAGE PERMANENT ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = "OWPCsbot"

# Utilisation du volume Railway monté sur /app/data
DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_PATH = os.path.join(DATA_DIR, "owpc_data.db")
logging.basicConfig(level=logging.INFO)
logging.info(f"💾 Database path: {DB_PATH}")

app = FastAPI()

# --- 🗄️ DATABASE (Initialisation) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0, points_unity REAL DEFAULT 0, 
                  points_veo REAL DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

# --- 🤖 BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    
    # Gestion du parrainage (Deep Link)
    ref_id = None
    if context.args and context.args[0].isdigit():
        ref_id = int(context.args[0])

    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (uid, name, ref_id))
        if ref_id and ref_id != uid:
            c.execute("UPDATE users SET points_unity = points_unity + 5.0, ref_count = ref_count + 1 WHERE user_id = ?", (ref_id,))
    conn.commit(); conn.close()

    # Facture Stars (si l'utilisateur clique sur Boost dans l'app)
    if context.args and "boost" in context.args[0]:
        token_type = context.args[0].split('_')[1]
        await update.message.reply_invoice(
            title=f"🚀 {token_type.upper()} BOOST",
            description=f"Add +10.00 {token_type.upper()} to your account!",
            payload=f"boost_{token_type}",
            provider_token="", currency="XTR",
            prices=[LabeledPrice("Boost Extra", 50)]
        )
        return

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC Protocol.\nMining Terminal is Active.", reply_markup=kb)

# --- 🛰️ API ENDPOINTS (CORRIGÉS) ---
@app.get("/api/user/{uid}")
async def get_user_api(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, ref_count FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    if r:
        return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3]}
    return {"g": 0.0, "u": 0.0, "v": 0.0, "rc": 0}

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    t = data.get("token")
    
    gain = 0.01 if t == 'veo' else 0.05
    col = f"points_{t}" # points_genesis, points_unity ou points_veo
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    try:
        query = f"UPDATE users SET {col} = {col} + ? WHERE user_id = ?"
        c.execute(query, (gain, uid))
        conn.commit()
    except Exception as e:
        logging.error(f"SQL Error: {e}")
    finally:
        conn.close()
    return {"ok": True}

# --- 🌐 MINI APP (Interface Unifiée) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body {{ background: #000; color: #0f0; font-family: 'Courier New', monospace; text-align: center; margin: 0; padding: 15px; }}
            .card {{ background: #111; border: 1px solid #333; border-radius: 12px; padding: 15px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }}
            .btn-mine {{ width: 100%; padding: 15px; border-radius: 8px; border: none; font-weight: bold; margin-bottom: 20px; cursor: pointer; }}
            .btn-boost {{ background: gold; color: #000; padding: 12px; border-radius: 8px; width: 100%; font-weight: bold; border: none; cursor: pointer; }}
        </style>
    </head>
    <body>
        <h3>OWPC TERMINAL v2.0</h3>
        
        <div class="card"><span>GENESIS</span><span id="bal_genesis">0.00</span></div>
        <button class="btn-mine" style="background:#0f0; color:#000;" onclick="mine('genesis')">EXTRACT GENESIS</button>

        <div class="card"><span>UNITY</span><span id="bal_unity">0.00</span></div>
        <button class="btn-mine" style="background:#fff; color:#000;" onclick="mine('unity')">EXTRACT UNITY</button>

        <div class="card"><span>VEO AI</span><span id="bal_veo">0.00</span></div>
        <button class="btn-mine" style="background:#00bcd4; color:#fff;" onclick="mine('veo')">EXTRACT VEO</button>

        <button class="btn-boost" onclick="buyBoost('veo')">⭐ BOOST VEO (50 Stars)</button>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            const uid = tg.initDataUnsafe.user.id;

            async function loadData() {{
                const r = await fetch('/api/user/' + uid);
                const d = await r.json();
                document.getElementById('bal_genesis').innerText = d.g.toFixed(2);
                document.getElementById('bal_unity').innerText = d.u.toFixed(2);
                document.getElementById('bal_veo').innerText = d.v.toFixed(2);
            }}

            async function mine(t) {{
                tg.HapticFeedback.impactOccurred('light');
                await fetch('/api/mine', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{user_id: uid, token: t}})
                }});
                loadData();
            }}

            function buyBoost(t) {{
                tg.openTelegramLink("https://t.me/{BOT_USERNAME}?start=boost_" + t);
                setTimeout(() => {{ tg.close(); }}, 100);
            }}

            loadData();
            setInterval(loadData, 5000); // Refresh auto toutes les 5s
        </script>
    </body></html>
    """

# --- SERVER START ---
async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(PreCheckoutQueryHandler(lambda u, c: u.pre_checkout_query.answer(ok=True)))
    
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
