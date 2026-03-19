import os
import sqlite3
import asyncio
from multiprocessing import Process
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = "https://veos-production.up.railway.app"

# --- PARTIE 1 : WEB ---
app = FastAPI()
@app.get("/", response_class=HTMLResponse)
async def home():
    return "<html><body style='background:#000;color:#0f0;text-align:center;'><h1>🚀 TERMINAL CONNECTÉ</h1></body></html>"

def run_web():
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="error")

# --- PARTIE 2 : BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Menu ultra-simple pour tester
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 OPEN APP", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📊 TEST STATS", callback_data="test_click")]
    ])
    await update.message.reply_text("🕊️ **OWPC READY**\nClique sur le bouton Stats pour tester.", reply_markup=kb)

async def handle_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Indispensable pour que le bouton ne reste pas figé
    
    if query.data == "test_click":
        await query.message.edit_text("✅ LE BOUTON FONCTIONNE !\n\nSi tu vois ce message, la synchro est parfaite.", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Retour", callback_data="back")]]))
    elif query.data == "back":
        # Retour au menu de départ
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 OPEN APP", web_app=WebAppInfo(url=WEBAPP_URL))],
            [InlineKeyboardButton("📊 TEST STATS", callback_data="test_click")]
        ])
        await query.message.edit_text("🕊️ **OWPC READY**", reply_markup=kb)

def run_bot():
    if not TOKEN: return
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    bot_app = ApplicationBuilder().token(TOKEN).build()
    
    # On enregistre les commandes
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_click))
    
    print("✅ BOT EN ECOUTE...")
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    # On lance les deux processus
    p1 = Process(target=run_web)
    p2 = Process(target=run_bot)
    p1.start()
    p2.start()
    p1.join()
    p2.join()
