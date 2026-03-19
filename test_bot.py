import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
# L'URL de ton projet Railway (ex: https://veos-production.up.railway.app)
WEBAPP_URL = os.getenv("WEBAPP_URL")
# L'username de ton bot sans le @
BOT_USERNAME = "OWPCsbot" 

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# --- 🗄️ DATABASE (Extension Parrainage) ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # On ajoute referred_by (qui a invité) et ref_count (combien d'invités)
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0, points_unity REAL DEFAULT 0, 
                  points_veo REAL DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()
    logging.info("✅ Database Initialized")

# --- 🤖 BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    
    # Gestion du parrainage via Deep Link (?start=REFERRER_ID)
    ref_id = None
    if context.args:
        try:
            ref_id = int(context.args[0])
            if ref_id == uid: ref_id = None # Pas d'auto-parrainage
        except: pass

    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # On vérifie si l'utilisateur est NOUVEAU pour donner le bonus au parrain
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (uid, name, ref_id))
        if ref_id:
            # ⭐ BONUS : +5.00 Unity pour le parrain !
            c.execute("UPDATE users SET points_unity = points_unity + 5.0, ref_count = ref_count + 1 WHERE user_id = ?", (ref_id,))
            logging.info(f"🎁 Bonus Unity donné à {ref_id} pour avoir invité {uid}")
    conn.commit(); conn.close()

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC Ecosystem, {name}!", reply_markup=kb)

# --- 🌐 WEB APP (Onglet FRIENDS) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body {{ background: #000; color: #fff; font-family: 'Segoe UI', sans-serif; text-align: center; padding: 20px; }}
            .ref-card {{ background: #111; border: 1px solid #333; border-radius: 15px; padding: 20px; margin-bottom: 15px; }}
            .invite-btn {{ width: 100%; padding: 15px; border-radius: 10px; border: none; background: #0f0; color: #000; font-weight: bold; font-size: 1.1em; cursor: pointer; }}
            .stat-val {{ color: #0f0; font-size: 2em; font-weight: bold; font-family: monospace; }}
        </style>
    </head>
    <body>
        <h2 style="color:#0f0">FRIENDS HUB</h2>
        
        <div class="ref-card">
            <p>Your Total Referrals</p>
            <div class="stat-val" id="ref_count">...</div>
            <p style="font-size: 0.8em; opacity: 0.7;">Get +5.00 UNITY for every friend who joins!</p>
        </div>

        <button class="invite-btn" onclick="shareInvite()">🔗 INVITE FRIENDS</button>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            const uid = tg.initDataUnsafe.user.id;
            const inviteLink = "https://t.me/{BOT_USERNAME}?start=" + uid;

            // Fonction pour charger le nombre de parrainages
            async function loadRefs() {{
                const res = await fetch('/api/user_info/' + uid);
                const data = await res.json();
                document.getElementById('ref_count').innerText = data.ref_count;
            }}

            // Fonction pour ouvrir l'interface de partage de Telegram
            function shareInvite() {{
                const text = "🚀 Join me on OWPC Protocol! Mine Genesis, Unity and VEO tokens for free.";
                const fullUrl = "https://t.me/share/url?url=" + encodeURIComponent(inviteLink) + "&text=" + encodeURIComponent(text);
                tg.openTelegramLink(fullUrl);
            }}
            
            loadRefs();
        </script>
    </body></html>
    """

@app.get("/api/user_info/{{uid}}")
async def user_info(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT ref_count FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return {{"ref_count": r[0] if r else 0}}

# --- SERVER ---
async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
