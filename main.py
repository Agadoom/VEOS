import asyncio, uvicorn, os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters

# Import de tes configurations et modules
import config, database
from routes import mine, launcher, user

# --- INITIALIZATION ---
database.init_db_structure()

app = FastAPI(title="WPT Hub API")

# Middleware pour éviter les erreurs de connexion depuis le Webview
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instance globale pour que les routes puissent y accéder
bot_instance = None

# --- INDEXATION DES ROUTES ---
app.include_router(user.router)     # /api/user
app.include_router(mine.router)     # /api/mine
app.include_router(launcher.router) # /api/launcher

# --- SERVING THE FRONTEND ---
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    # On lit le fichier index.html que tu as créé
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Frontend index.html not found!</h1>"

# --- TELEGRAM BOT LOGIC ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler pour /start"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 OPEN APP", web_app=WebAppInfo(url=config.WEBAPP_URL))]
    ])
    await update.message.reply_text(
        "<b>Welcome to WPT Ecosystem!</b>\n\n"
        "Mine Genesis, Unity, and Veo AI. Launch your own tokens or trade community assets.",
        parse_mode="HTML",
        reply_markup=keyboard
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Réponse obligatoire de Telegram avant le paiement final"""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestion après réception des Stars"""
    payment = update.message.successful_payment
    payload = payment.invoice_payload

    # Logique Achat de Token (WPT + Stars)
    if payload.startswith("buy|"):
        _, uid, tid, qty, cost_wpt = payload.split('|')
        conn = database.get_db_conn()
        c = conn.cursor()
        
        # 1. Déduire le prix en WPT (Genesis)
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (float(cost_wpt), int(uid)))
        
        # 2. Ajouter le Token au Wallet
        database.buy_token(int(uid), int(tid), float(qty))
        
        conn.commit()
        c.close()
        conn.close()
        await update.message.reply_text("✅ Purchase Confirmed! Your tokens are now in your wallet.")

    # Logique Création de Token (500 Stars)
    else:
        # On récupère les données temporaires stockées dans launcher.py
        from routes.launcher import pending_tokens
        data = pending_tokens.get(payload)
        if data:
            database.deploy_token(
                data['user_id'], data['name'], data['symbol'], 
                data['desc'], data['logo'], data['banner'], "", ""
            )
            del pending_tokens[payload]
            await update.message.reply_text(f"🚀 Success! <b>{data['name']}</b> has been deployed to the market.")

# --- MAIN SERVER RUNNER ---

async def run_server():
    config_uvicorn = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    server = uvicorn.Server(config_uvicorn)
    await server.serve()

async def main():
    global bot_instance
    # Initialisation du Bot
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    bot_instance = bot_app # Partage l'instance

    # Handlers
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    bot_app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Lancement simultané du Bot et du Serveur Web
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    
    print(f"Server started on port {config.PORT}")
    await run_server()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
