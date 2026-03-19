import os, sqlite3, asyncio, uvicorn, random, logging
from datetime import date, datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://veos-production.up.railway.app")
LOGO_PATH = "media/owpc_logo.png"

app = FastAPI()

# --- 🧠 STEALTH ENGINE (Calculs en arrière-plan) ---
def process_referral_logic(user_id, ref_id):
    """Gère le parrainage de manière invisible"""
    if not ref_id or user_id == ref_id: return
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # On vérifie si l'utilisateur est nouveau
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (user_id, ref_id))
        # Optionnel : Donner un bonus de bienvenue au parrain ici
    conn.commit(); conn.close()

def get_user_data(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, streak FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    conn.close()
    return res

# --- 🤖 BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    # 1. Traitement invisible du lien de parrainage (Deep Link)
    ref_id = None
    if context.args:
        try:
            ref_id = int(context.args[0])
            process_referral_logic(uid, ref_id)
        except: pass

    # 2. Initialisation silencieuse du compte
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, user.first_name))
    conn.commit(); conn.close()

    # 3. Interface simplifiée (On met en avant le Terminal)
    s = get_user_data(uid)
    bal = sum(s[:3]) if s else 0.0
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📊 My Stats", callback_data="st_stats"), InlineKeyboardButton("🔗 Invite", callback_data="st_ref")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="st_set")]
    ])
    
    txt = f"🕊️ **OWPC PROTOCOL**\n\nWelcome back, `{user.first_name}`\nBalance: `{bal:.2f}` OWPC"
    
    # Envoi direct du menu propre
    await update.message.reply_photo(photo=open(LOGO_PATH, 'rb'), caption=txt, reply_markup=kb, parse_mode="Markdown")

# --- 🌐 WEB APP (Invisible Calculations Backend) ---
@app.post("/api/sync")
async def sync_data(request: Request):
    """Le Terminal envoie des données, le bot calcule tout derrière"""
    data = await request.json()
    uid = data.get("user_id")
    action = data.get("action")
    
    if uid and action == "mine":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        # Calcul automatique des gains + commissions parrains
        c.execute("UPDATE users SET points_genesis = points_genesis + 0.05 WHERE user_id = ?", (uid,))
        
        # Logique de commission automatique 2-niveaux (invisible pour l'user)
        c.execute("SELECT referred_by FROM users WHERE user_id = ?", (uid,))
        ref = c.fetchone()
        if ref and ref[0]:
            c.execute("UPDATE users SET points_genesis = points_genesis + 0.005 WHERE user_id = ?", (ref[0],))
            
        conn.commit(); conn.close()
        return {"status": "synced"}

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    """Interface Web épurée"""
    return """
    <html>
    <body style="background:#000; color:#0f0; font-family:sans-serif; text-align:center;">
        <h1 style="margin-top:20vh;">OWPC TERMINAL</h1>
        <div id="display" style="font-size:2em; margin:20px;">0.00</div>
        <button onclick="mine()" style="padding:20px; border-radius:50%; border:2px solid #0f0; background:transparent; color:#0f0; width:150px; height:150px; font-weight:bold;">MINE</button>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <script>
            let tg = window.Telegram.WebApp;
            function mine() {
                fetch('/api/sync', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: tg.initDataUnsafe.user.id, action: 'mine'})
                });
                let d = document.getElementById('display');
                d.innerText = (parseFloat(d.innerText) + 0.05).toFixed(2);
            }
        </script>
    </body></html>
    """

async def main():
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
