import asyncio, uvicorn, os, time
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters
from fastapi.responses import FileResponse

# Import de tes configurations et modules
import config, database
from routes import mine, launcher, user, stars

# --- INITIALIZATION ---
database.init_db_structure()

app = FastAPI(title="WPT Hub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cette ligne est OBLIGATOIRE pour lire le dossier static
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- INDEXATION DES ROUTES ---
app.include_router(user.router)
app.include_router(mine.router)
app.include_router(launcher.router)
app.include_router(stars.router)

# --- API STARS (Générer le lien de paiement) ---
@app.get("/api/stars/create-invoice/{uid}")
async def create_invoice(uid: int):
    # On récupère l'instance du bot stockée dans l'app
    bot = app.state.bot
    
    # Prix : 50 Stars (En Telegram Stars, 1 Star = 1 unité, pas de centimes)
    prices = [LabeledPrice(label="10,000 WPT Pack", amount=50)]
    
    try:
        # Génération du lien de paiement officiel Telegram Stars (XTR)
        invoice_link = await bot.create_invoice_link(
            title="WPT Boost Pack",
            description="Get 10,000 WPT instantly to trade community tokens!",
            payload=f"buy_wpt_10k_{uid}",
            provider_token="", # Vide pour Telegram Stars
            currency="XTR",    # Code pour les Stars
            prices=prices
        )
        return {"invoice_link": invoice_link}
    except Exception as e:
        print(f"Invoice Error: {e}")
        return {"error": str(e)}


from fastapi.responses import JSONResponse

@app.get("/tonconnect-manifest.json")
async def get_manifest():
    return JSONResponse({
        "url": "https://veos-production-a2de.up.railway.app",
        "name": "WPT Ecosystem",
        "iconUrl": "https://veos-production-a2de.up.railway.app/media/owpc_logo.png"
    })







# --- SERVING THE FRONTEND ---
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Frontend index.html not found!</h1>"

# --- TELEGRAM BOT HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    
    # Referral logic
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
        if referrer_id != uid:
            user_data = database.get_user_full(uid)
            if not user_data or sum(user_data[0:3]) == 0:
                database.add_referral_reward(uid, referrer_id)
                await context.bot.send_message(chat_id=referrer_id, text=f"🎁 Your friend {name} joined! You earned +500 WPT.")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN APP", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text(f"<b>Welcome {name}!</b>\n\nStart mining and trade tokens.", parse_mode="HTML", reply_markup=keyboard)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Répondre OUI à Telegram pour autoriser le paiement"""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    # total_amount est en "milli-stars" ou Stars selon la version, 
    # mais on va se baser sur le payload pour être sûr du produit
    
    uid = int(payload.split("_")[-1])
    user_name = update.effective_user.first_name
    
    # --- LOGIQUE DE CALCUL DU PACK ---
    wpt_to_add = 0
    pack_name = ""

    if "buy_stars_50" in payload:
        wpt_to_add = 10000
        pack_name = "Base Pack (10k)"
    elif "buy_stars_250" in payload:
        wpt_to_add = 60000  # 10k * 5 + 20% bonus
        pack_name = "Medium Pack (60k)"
    elif "buy_stars_500" in payload:
        wpt_to_add = 150000 # 10k * 10 + 50% bonus
        pack_name = "Mega Pack (150k)"

    if wpt_to_add > 0:
        # 1. Créditer le montant dynamique en BDD
        conn = database.get_db_conn()
        c = conn.cursor()
        # On utilise wpt_to_add au lieu de 10000
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (wpt_to_add, uid))
        conn.commit()
        c.close()
        conn.close()

        # --- LOG RAILWAY ---
        print(f"💰 SUCCESS: {wpt_to_add} WPT added to {user_name}")

        # 2. Réponse au client
        await update.message.reply_text(
            f"✅ <b>Payment Received!</b>\n{wpt_to_add:,} WPT added to your balance. 🚀", 
            parse_mode="HTML"
        )


# --- MAIN RUNNER ---

async def main():
    # 1. Init Bot App
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    
    # 2. Stocker le bot dans FastAPI pour y accéder depuis les routes
    app.state.bot = bot_app.bot 

    # 3. Handlers
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    bot_app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # 4. Start Bot (Polling mode)
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling()) # Run polling in background
    
    # 5. Run FastAPI
    print(f"🚀 Server & Bot active on port {config.PORT}")
    uv_config = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    server = uvicorn.Server(uv_config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
