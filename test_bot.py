import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, LabeledPrice, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, PreCheckoutQueryHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = os.getenv("WEBAPP_URL")

app = FastAPI()

# --- ⭐️ LOGIQUE BOOST (STARS) ---
@app.post("/api/boost")
async def api_boost(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    token_type = data.get("token") # 'genesis', 'unity' ou 'veo'
    
    # Ici, on génère un lien de paiement (Invoice) via le bot
    # Pour simplifier, on va dire que 50 Stars = +10.00 Tokens
    # Note: Dans une version réelle, on envoie un sendInvoice via le bot Telegram
    return {"invoice_url": f"https://t.me/OWPCsbot?start=boost_{token_type}"}

# --- 🤖 BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Gestion du retour de paiement ou Boost
    if context.args and "boost" in context.args[0]:
        token = context.args[0].split('_')[1]
        await update.message.reply_text(f"🚀 Preparation of the {token.upper()} Boost with Telegram Stars...")
        # Ici tu enverrais : await context.bot.send_invoice(...)
        return

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text("Welcome to OWPC Hub. Use Stars to boost your extraction.", reply_markup=kb)

# --- 🌐 WEB APP (Boutons Boost avec Stars) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body {{ background: #000; color: #fff; font-family: sans-serif; text-align: center; }}
            .card {{ background: #111; border: 1px solid #333; border-radius: 15px; padding: 15px; margin: 10px; }}
            .boost-btn {{ background: gold; color: #000; border: none; padding: 10px; border-radius: 5px; font-weight: bold; cursor: pointer; }}
            .token-val {{ color: #0f0; font-size: 1.5em; }}
        </style>
    </head>
    <body>
        <h2>OWPC PREMIUM MINING</h2>
        
        <div class="card">
            <p>GENESIS: <span class="token-val" id="g">0.00</span></p>
            <button class="boost-btn" onclick="buyBoost('genesis')">⭐ BOOST WITH STARS</button>
        </div>

        <div class="card">
            <p>UNITY: <span class="token-val" id="u">0.00</span></p>
            <button class="boost-btn" onclick="buyBoost('unity')">⭐ BOOST WITH STARS</button>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            function buyBoost(token) {{
                // On ferme la webapp pour aller sur le paiement du bot
                tg.openTelegramLink("https://t.me/OWPCsbot?start=boost_" + token);
                tg.close();
            }}
        </script>
    </body></html>
    """

# --- SERVER ---
async def main():
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
