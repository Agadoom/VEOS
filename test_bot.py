import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, LabeledPrice, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, PreCheckoutQueryHandler, MessageHandler, filters, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = os.getenv("WEBAPP_URL")

app = FastAPI()

# --- 🤖 LOGIQUE TELEGRAM (Paiements) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Si l'URL contient "boost_genesis", on envoie la facture
    if context.args and "boost" in context.args[0]:
        token_type = context.args[0].split('_')[1]
        price = 50 # Prix en Telegram Stars
        
        await update.message.reply_invoice(
            title=f"🚀 Boost {token_type.upper()}",
            description=f"Get +10.00 {token_type.upper()} tokens immediately!",
            payload=f"boost_{token_type}",
            provider_token="", # Vide pour les Telegram Stars
            currency="XTR",    # Code pour Telegram Stars
            prices=[LabeledPrice("Boost Extra", price)]
        )
        return

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text("Welcome to OWPC Hub. High-speed mining active.", reply_markup=kb)

# Validation du paiement (étape obligatoire)
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

# Crédit des points après succès
async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload # ex: boost_genesis
    token = payload.split('_')[1]
    uid = update.effective_user.id
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    col = f"points_{token}"
    c.execute(f"UPDATE users SET {col} = {col} + 10.0 WHERE user_id = ?", (uid,))
    conn.commit(); conn.close()
    
    await update.message.reply_text(f"✅ Payment Successful! +10.00 {token.upper()} added to your balance.")

# --- 🌐 WEB APP (Lien vers le Boost) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {{ background: #000; color: #fff; font-family: sans-serif; text-align: center; }}
        .boost-btn {{ background: #0f0; color: #000; border: none; padding: 15px; border-radius: 10px; width: 90%; font-weight: bold; margin: 10px; }}
    </style>
    </head>
    <body>
        <h2>PREMIUM BOOSTS</h2>
        <button class="boost-btn" onclick="pay('genesis')">⭐ BOOST GENESIS (50 Stars)</button>
        <button class="boost-btn" onclick="pay('unity')">⭐ BOOST UNITY (50 Stars)</button>
        <script>
            let tg = window.Telegram.WebApp;
            function pay(t) {{
                // Redirige vers le bot avec le paramètre de boost
                tg.openTelegramLink("https://t.me/OWPCsbot?start=boost_" + t);
                tg.close();
            }}
        </script>
    </body></html>
    """

# --- SERVER ---
async def main():
    bot = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers pour les paiements
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
