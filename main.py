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

# --- INDEXATION DES ROUTES ---
app.include_router(user.router)     # /api/user
app.include_router(mine.router)     # /api/mine
app.include_router(launcher.router) # /api/launcher

# --- SERVING THE FRONTEND ---
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Frontend index.html not found!</h1>"

# --- TELEGRAM BOT LOGIC ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    
    # 1. Vérifier si c'est un nouveau joueur via parrainage
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
        if referrer_id != uid: # On ne peut pas se parrainer soi-même
            # On vérifie si l'user existe déjà
            user_data = database.get_user_full(uid)
            # Si le score est 0, on considère que c'est une première connexion
            if sum(user_data[0:3]) == 0:
                database.add_referral_reward(uid, referrer_id)
                await context.bot.send_message(chat_id=referrer_id, text=f"🎁 Your friend {name} joined! You earned +500 WPT.")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN APP", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text(f"<b>Welcome {name}!</b>\n\nStart mining and trade community tokens.", parse_mode="HTML", reply_markup=keyboard)


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload

    if payload.startswith("buy|"):
        _, uid, tid, qty, cost_wpt = payload.split('|')
        conn = database.get_db_conn()
        c = conn.cursor()
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (float(cost_wpt), int(uid)))
        database.buy_token(int(uid), int(tid), float(qty))
        conn.commit()
        c.close(); conn.close()
        await update.message.reply_text("✅ Purchase Confirmed! Your tokens are now in your wallet.")
    else:
        # Import local pour éviter l'import circulaire
        from routes.launcher import pending_tokens
        data = pending_tokens.get(payload)
        if data:
            database.deploy_token(
                data['user_id'], data['name'], data['symbol'], 
                data['desc'], data['logo'], data['banner'], "", ""
            )
            del pending_tokens[payload]
            await update.message.reply_text(f"🚀 Success! <b>{data['name']}</b> has been deployed!")

# --- MAIN SERVER RUNNER ---

async def main():
    # 1. Initialisation du Bot
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    
    # 2. Partage de l'instance pour les routes (Crucial pour éviter le crash)
    app.state.bot = bot_app.bot 

    # 3. Enregistrement des Handlers (Une seule fois !)
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    bot_app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # 4. Lancement du Bot
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    
    # 5. Lancement du Serveur Web
    print(f"🚀 Server running on port {config.PORT}")
    config_uvicorn = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    server = uvicorn.Server(config_uvicorn)
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
