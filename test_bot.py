import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, PreCheckoutQueryHandler, MessageHandler, filters, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = "OWPCsbot" 

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# --- 🗄️ DATABASE (Structure Complète) ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0, points_unity REAL DEFAULT 0, 
                  points_veo REAL DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

# --- 🤖 BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    
    # 1. Gestion Parrainage
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    # 2. Inscription / Update
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (uid, name, ref_id))
        if ref_id and ref_id != uid:
            c.execute("UPDATE users SET points_unity = points_unity + 5.0, ref_count = ref_count + 1 WHERE user_id = ?", (ref_id,))
    conn.commit(); conn.close()

    # 3. Facture Stars (si demandé via lien)
    if context.args and "boost" in context.args[0]:
        token = context.args[0].split('_')[1]
        await update.message.reply_invoice(
            title=f"🚀 BOOST {token.upper()}", description=f"Get +10 {token.upper()}",
            payload=f"boost_{token}", provider_token="", currency="XTR",
            prices=[LabeledPrice("Boost", 50)]
        )
        return

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC, {name}!\nYour terminal is ready for extraction.", reply_markup=kb)

# --- 🌐 WEB APP INTERFACE (Visuel Fixé) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body {{ background: #000; color: #fff; font-family: 'Courier New', monospace; text-align: center; margin: 0; padding: 15px; }}
            .header {{ color: #0f0; border-bottom: 1px solid #0f0; padding-bottom: 10px; margin-bottom: 20px; }}
            .token-card {{ background: #111; border: 1px solid #333; border-radius: 12px; padding: 15px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }}
            .token-name {{ color: #0f0; font-weight: bold; }}
            .token-val {{ font-size: 1.2em; }}
            .btn-mine {{ width: 100%; padding: 15px; border-radius: 8px; border: none; font-weight: bold; margin-top: 5px; cursor: pointer; }}
            .btn-boost {{ background: gold; color: #000; padding: 10px; border-radius: 5px; font-size: 0.8em; border: none; margin-top: 10px; width: 100%; font-weight:bold; }}
            .nav {{ display: flex; justify-content: space-around; margin-top: 20px; border-top: 1px solid #333; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="header">OWPC PROTOCOL v1.0</div>
        
        <div class="token-card">
            <span class="token-name">🧬 GENESIS</span>
            <span class="token-val" id="bal_genesis">0.00</span>
        </div>
        <button class="btn-mine" style="background:#0f0; color:#000;" onclick="mine('genesis')">EXTRACT GENESIS (+0.05)</button>

        <div class="token-card" style="margin-top:20px;">
            <span class="token-name">⚙️ UNITY</span>
            <span class="token-val" id="bal_unity">0.00</span>
        </div>
        <button class="btn-mine" style="background:#fff; color:#000;" onclick="mine('unity')">EXTRACT UNITY (+0.05)</button>

        <div class="token-card" style="margin-top:20px;">
            <span class="token-name">🤖 VEO AI</span>
            <span class="token-val" id="bal_veo">0.00</span>
        </div>
        <button class="btn-mine" style="background:#00bcd4; color:#fff;" onclick="mine('veo')">EXTRACT VEO (+0.01)</button>

        <button class="btn-boost" onclick="tg.openTelegramLink('https://t.me/{BOT_USERNAME}?start=boost_veo')">⭐ BUY VEO BOOST (50 Stars)</button>

        <div class="nav">
            <button onclick="alert('Friends: ' + window.refCount)" style="background:transparent; color:#0f0; border:1px solid #0f0; border-radius:5px; padding:5px;">👥 Friends</button>
            <button onclick="shareInvite()" style="background:transparent; color:#0f0; border:1px solid #0f0; border-radius:5px; padding:5px;">🔗 Invite</button>
        </div>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            const uid = tg.initDataUnsafe.user.id;
            window.refCount = 0;

            async function loadData() {{
                const r = await fetch('/api/user/' + uid);
                const d = await r.json();
                document.getElementById('bal_genesis').innerText = d.g.toFixed(2);
                document.getElementById('bal_unity').innerText = d.u.toFixed(2);
                document.getElementById('bal_veo').innerText = d.v.toFixed(2);
                window.refCount = d.rc;
            }}

            async function mine(t) {{
                tg.HapticFeedback.impactOccurred('medium');
                await fetch('/api/mine', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{user_id: uid, token: t}})
                }});
                let el = document.getElementById('bal_' + t);
                let gain = (t === 'veo') ? 0.01 : 0.05;
                el.innerText = (parseFloat(el.innerText) + gain).toFixed(2);
            }}

            function shareInvite() {{
                const link = "https://t.me/{BOT_USERNAME}?start=" + uid;
                tg.openTelegramLink("https://t.me/share/url?url=" + encodeURIComponent(link) + "&text=Join OWPC!");
            }}

            loadData();
        </script>
    </body></html>
    """

# --- 🛰️ API ENDPOINTS ---
@app.get("/api/user/{uid}")
async def get_user_api(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, ref_count FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3]} if r else {"g":0,"u":0,"v":0,"rc":0}

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET points_{t} = points_{t} + ? WHERE user_id = ?", (gain, uid))
    conn.commit(); conn.close()
    return {"ok": True}

# --- 🛠️ MAIN ---
async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
