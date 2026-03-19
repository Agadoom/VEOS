import os
import sqlite3
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- 1. CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
# Remplace par ton URL Railway réelle pour la Mini App
WEBAPP_URL = "https://veos-production.up.railway.app" 

app = FastAPI()

# --- 2. BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis INTEGER DEFAULT 0, 
                  points_unity INTEGER DEFAULT 0, 
                  points_veo REAL DEFAULT 0.0)''')
    conn.commit()
    conn.close()

def get_stats(uid):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
        res = c.fetchone(); conn.close()
        if res:
            total = (res[0] or 0) + (res[1] or 0) + (res[2] or 0.0)
            return {"total": int(total), "g": res[0] or 0, "u": res[1] or 0, "v": res[2] or 0.0}
    except: pass
    return {"total": 0, "g": 0, "u": 0, "v": 0.0}

# --- 3. CLAVIER PRINCIPAL (Menu Riche) ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")]
    ])

# --- 4. LOGIQUE DU BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    
    # Enregistrement de l'utilisateur
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()
    
    s = get_stats(user.id)
    msg = (f"🕊️ **OWPC PROTOCOL**\n\n"
           f"👤 **Commander:** {user.first_name}\n"
           f"💰 **Balance:** {s['total']:,} OWPC\n\n"
           f"System Status: `OPERATIONAL` ✅")
    
    # Si c'est un message texte (/start)
    if update.message:
        await update.message.reply_text(msg, reply_markup=main_menu_kb(), parse_mode="Markdown")
    # Si c'est un retour au menu via bouton
    elif update.callback_query:
        await update.callback_query.message.edit_text(msg, reply_markup=main_menu_kb(), parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    s = get_stats(uid)

    if query.data == "main_menu":
        await start(update, context)
    
    elif query.data == "stats":
        txt = f"📊 **ASSETS OVERVIEW**\n\nGenesis: `{s['g']}`\nUnity: `{s['u']}`\nVeo AI: `{s['v']:.2f}`\n\nTotal: `{s['total']}`"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")
    
    elif query.data == "passport":
        txt = f"🆔 **PASSPORT**\n\nHolder: `{query.from_user.first_name}`\nStatus: `VERIFIED ✅`"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")
    
    elif query.data == "invest":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
        ])
        await query.message.edit_text("💰 **INVEST HUB**", reply_markup=kb)
    
    elif query.data in ["hof", "lucky", "invite"]:
        await query.message.edit_text(f"🚧 Sector **{query.data.upper()}** under construction.", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

# --- 5. INTERFACE MINI APP (Serveur Web) ---
@app.get("/", response_class=HTMLResponse)
async def mini_app():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OWPC Terminal</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { background: #000; color: #00ff00; font-family: 'Courier New', monospace; text-align: center; margin: 0; padding: 20px; overflow: hidden; }
            .terminal { border: 2px solid #00ff00; padding: 20px; border-radius: 10px; height: 80vh; display: flex; flex-direction: column; justify-content: center; }
            .btn-mine { background: #00ff00; color: #000; border: none; padding: 20px; font-size: 1.2em; font-weight: bold; border-radius: 50%; width: 150px; height: 150px; margin: 20px auto; cursor: pointer; box-shadow: 0 0 20px #00ff00; }
            .btn-mine:active { transform: scale(0.95); background: #00cc00; }
            h1 { font-size: 1.5em; text-shadow: 0 0 10px #00ff00; }
        </style>
    </head>
    <body>
        <div class="terminal">
            <h1>> OWPC TERMINAL</h1>
            <p>STATUS: ACTIVE</p>
            <div id="counter">0.00</div>
            <button class="btn-mine" onclick="mine()">MINE</button>
            <p id="msg">READY TO EXTRACT</p>
        </div>
        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            let count = 0;
            function mine() {
                count += 0.01;
                document.getElementById('counter').innerText = count.toFixed(2);
                document.getElementById('msg').innerText = "EXTRACTING...";
                tg.HapticFeedback.impactOccurred('medium');
            }
        </script>
    </body>
    </html>
    """

# --- 6. LANCEMENT ---
async def main():
    if not TOKEN:
        print("❌ ERREUR: TOKEN manquant dans les variables d'environnement")
        return

    # Initialisation du Bot
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_callbacks))
    
    await bot_app.initialize()
    await bot_app.start()
    # On lance le bot en tâche de fond avec nettoyage des vieux messages
    asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    print("✅ Bot Telegram : Actif")

    # Lancement du serveur Web FastAPI
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    print(f"🌐 Serveur Mini App : Port {PORT}")
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
