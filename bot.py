import os
import sqlite3
import asyncio
from multiprocessing import Process
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = "https://veos-production.up.railway.app"

# --- PARTIE 1 : LE SERVEUR WEB ---
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def home():
    return "<html><body style='background:#000;color:#0f0;text-align:center;'><h1>🚀 TERMINAL OWPC CONNECTÉ</h1></body></html>"

def run_web():
    print(f"🌐 [WEB] Démarrage sur le port {PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)

# --- PARTIE 2 : LE BOT TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"📩 [BOT] Commande /start reçue de {update.effective_user.first_name}")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")]
    ])
    await update.message.reply_text("🕊️ **SYSTÈME OWPC OPÉRATIONNEL**", reply_markup=kb, parse_mode="Markdown")

def run_bot():
    print("🤖 [BOT] Initialisation du bot...")
    if not TOKEN:
        print("❌ [BOT] ERREUR : Pas de TOKEN trouvé !")
        return
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    
    print("✅ [BOT] Le bot écoute maintenant les messages...")
    bot_app.run_polling(drop_pending_updates=True)

# --- LANCEMENT TOTAL ---
if __name__ == "__main__":
    # On lance le Web dans un processus
    p1 = Process(target=run_web)
    p1.start()
    
    # On lance le Bot dans un autre processus
    p2 = Process(target=run_bot)
    p2.start()
    
    p1.join()
    p2.join()
