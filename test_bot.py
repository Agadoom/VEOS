import os
import asyncio
import sqlite3
import nest_asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

nest_asyncio.apply()

# --- CONFIG TEST ---
TOKEN = os.getenv("TOKEN") # Ton TOKEN de bot de test
PORT = int(os.environ.get("PORT", 8080)) # Port Railway

app = FastAPI()

# --- 🌐 PARTIE MINI APP (Le Visuel) ---
@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <html>
        <head>
            <title>OWPC Mini App</title>
            <style>
                body { background-color: #0a0a12; color: gold; text-align: center; font-family: sans-serif; padding-top: 50px; }
                .card { border: 2px solid gold; border-radius: 15px; padding: 20px; margin: 20px; background: #161626; }
                button { background: gold; color: black; border: none; padding: 10px 20px; border-radius: 5px; font-weight: bold; }
            </style>
        </head>
        <body>
            <h1>🕊️ OWPC HIVE</h1>
            <div class="card">
                <h2>Welcome to Phase 2</h2>
                <p>Status: <span style="color: lime;">CONNECTED</span></p>
                <button onclick="alert('Staking coming soon!')">CHECK MY ASSETS</button>
            </div>
        </body>
    </html>
    """

# --- 🤖 PARTIE BOT (Les Commandes) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Railway te donne une URL publique, on l'utilise pour le bouton Mini App
    webapp_url = f"https://{os.getenv('RAILWAY_STATIC_URL')}"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Open OWPC App", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton("🏛️ Menu Classique", callback_data="menu")]
    ])
    
    await update.message.reply_text(
        "Welcome to the **OWPC Phase 2 Test Bot**!\n\nClick the button below to test the Mini App interface.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

# --- ⚙️ LANCEMENT ---
async def run_bot():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    
    # On lance le bot en mode polling
    async with bot_app:
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        # On garde le bot en vie pendant que FastAPI tourne
        while True:
            await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    # Lance le bot Telegram en arrière-plan
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    # Lance le serveur Web sur le port Railway
    uvicorn.run(app, host="0.0.0.0", port=PORT)
