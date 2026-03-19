import os
import asyncio
import sqlite3
import nest_asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

nest_asyncio.apply()

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app"
PORT = int(os.getenv("PORT", 8080))

app = FastAPI()

# --- WEBAPP (L'écran que tu vois sur ta photo) ---
@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
        <body style="background:#000;color:#0f0;text-align:center;font-family:monospace;padding-top:100px;">
            <h1 style="border:2px solid #0f0;display:inline-block;padding:20px;">🚀 OWPC TERMINAL ONLINE</h1>
            <p style="font-size:20px;">Protocol Status: <span style="color:white;">STABLE</span></p>
            <p>Le bot Telegram est maintenant synchronisé.</p>
        </body>
    </html>
    """

# --- LOGIQUE DU BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Cette fonction DOIT être appelée quand tu fais /start
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily"), InlineKeyboardButton("📊 Stats", callback_data="view_stats")]
    ])
    await update.message.reply_text("🕊️ **BIENVENUE COMMANDER**\n\nLe terminal OWPC est prêt.", reply_markup=kb, parse_mode="Markdown")

async def run_bot():
    try:
        # On force la création de l'application avec le TOKEN
        bot_app = ApplicationBuilder().token(TOKEN).build()
        bot_app.add_handler(CommandHandler("start", start))
        
        await bot_app.initialize()
        await bot_app.start()
        # drop_pending_updates est CRUCIAL ici pour débloquer le conflit
        print("✅ BOT TELEGRAM: OK (Listening...)")
        await bot_app.updater.start_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"❌ ERREUR BOT: {e}")

# --- LANCEMENT ---
async def main():
    # Lancement du bot en tâche de fond
    asyncio.create_task(run_bot())
    
    # Lancement du serveur Web
    print(f"🌐 SERVEUR WEB: OK (Port {PORT})")
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERREUR: Le TOKEN n'est pas configuré dans les variables Railway !")
    else:
        asyncio.run(main())
