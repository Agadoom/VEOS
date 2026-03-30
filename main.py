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
from routes import mine, launcher, user, stars, lottery, premium


from apscheduler.schedulers.asyncio import AsyncIOScheduler
from routes.lottery import draw_lottery # On importe la fonction de tirage



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



@app.get("/secret-admin-dashboard")
async def admin_page():
    return FileResponse("admin.html")



# --- INDEXATION DES ROUTES ---
app.include_router(user.router)
app.include_router(mine.router)
app.include_router(launcher.router)
app.include_router(stars.router)
app.include_router(lottery.router)
app.include_router(premium.router)

# --- API STARS (Générer le lien de paiement) ---
@app.get("/api/stars/create-invoice/{uid}")
async def create_invoice(uid: int, amount: int = 50): # On ajoute le paramètre amount
    bot = app.state.bot
    
    # --- CONFIGURATION DYNAMIQUE DES PACKS ---
    title = "WPT Boost Pack"
    description = "Get WPT instantly to trade community tokens!"
    # On crée un payload unique qui contient le montant et l'ID
    payload = f"stars_pack_{amount}_{uid}"
    
    if amount == 1000:
        title = "💎 LEGEND PACK"
        description = "300,000 WPT + Exclusive Legendary Badge!"
    elif amount == 250:
        title = "🌟 MEDIUM PACK"
        description = "60,000 WPT + 20% Bonus included!"
    elif amount == 99:
        title = "⚡ TURBO RECHARGE"
        description = "Your energy refills 3x faster for 24h!"
        payload = f"turbo_boost_99_{uid}"

    try:
        invoice_link = await bot.create_invoice_link(
            title=title,
            description=description,
            payload=payload,
            provider_token="", 
            currency="XTR",
            prices=[LabeledPrice(label=title, amount=amount)]
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
    
    # --- LOGIQUE DE DEEP LINKING (Parrainage & Tokens) ---
    if context.args:
        param = context.args[0]
        print(f"🚀 Deep Link détecté : {param}")
        
        # Cas 1 : Parrainage classique (chiffres uniquement)
        if param.isdigit():
            referrer_id = int(param)
            if referrer_id != uid:
                user_data = database.get_user_full(uid)
                # Si l'utilisateur est nouveau (solde à 0)
                if not user_data or sum(user_data[0:3]) == 0:
                    database.add_referral_reward(uid, referrer_id)
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id, 
                            text=f"🎁 Your friend {name} joined! You earned +500 WPT."
                        )
                    except: pass

        # Cas 2 : Lien spécifique vers un Token (ex: 12345_67)
        elif "_" in param:
            referrer_id, token_id = param.split("_")
            print(f"Invitation pour le Token ID: {token_id} par l'user {referrer_id}")
            # Ici tu peux ajouter une logique pour enregistrer que l'user vient pour ce token

    # --- RÉPONSE CLASSIQUE ---
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🚀 OPEN APP", web_app=WebAppInfo(url=config.WEBAPP_URL))
    ]])
    
    await update.message.reply_text(
        f"<b>Welcome {name}!</b>\n\nOne World Peace Coins ecosystem is active.\nStart mining and trade community tokens.", 
        parse_mode="HTML", 
        reply_markup=keyboard
    )
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Répondre OUI à Telegram pour autoriser le paiement"""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    
    # On extrait l'UID depuis le payload (ex: stars_pack_50_123456)
    parts = payload.split("_")
    uid = int(parts[-1])
    
    conn = database.get_db_conn()
    c = conn.cursor()
    msg = ""

    try:
        # CASE 1: WPT PACKS
        if "stars_pack_" in payload:
            amount_stars = int(parts[2])
            wpt_to_add = 0
            if amount_stars == 50: wpt_to_add = 10000
            elif amount_stars == 250: wpt_to_add = 60000
            elif amount_stars == 1000: wpt_to_add = 300000
            
            if wpt_to_add > 0:
                c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (wpt_to_add, uid))
                msg = f"✅ <b>Payment Received!</b>\n{wpt_to_add:,} WPT added to your balance. 🚀"
                print(f"💰 SUCCESS: {wpt_to_add} WPT added to user {uid}")

        # CASE 2: TURBO BOOST
        elif "turbo_boost" in payload:
            expiry = (datetime.now() + timedelta(hours=24))
            c.execute("UPDATE users SET turbo_until = %s WHERE user_id = %s", (expiry, uid))
            msg = "✅ <b>TURBO ACTIVATED!</b>\nYour energy will refill 3x faster for 24h! ⚡"
            print(f"⚡ TURBO: Activated for user {uid}")

        conn.commit()
    except Exception as e:
        print(f"❌ Payment Error: {e}")
        msg = "⚠️ An error occurred while processing your payment. Contact support."
    finally:
        c.close(); conn.close()

    if msg:
        await update.message.reply_text(msg, parse_mode="HTML")



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

    # --- 🕒 CONFIGURATION DE LA LOTERIE (CRON) ---
    scheduler = AsyncIOScheduler()
    
    # FIX: On ajoute args=[bot_app.bot] pour que la fonction draw_lottery 
    # puisse utiliser le bot pour annoncer le gagnant ! 📣
    scheduler.add_job(
        draw_lottery, 
        'cron', 
        day_of_week='sun', 
        hour=21, 
        minute=0, 
        args=[bot_app.bot] 
    )
    
    scheduler.start()
    print("📅 Scheduler Started: Lottery draw set for Sunday 21:00 UTC")
    # -----------------------------------------------

    # 3. Handlers
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    bot_app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # 4. Start Bot (Polling mode)
    await bot_app.initialize()
    await bot_app.start()
    
    # On lance le polling en arrière-plan
    asyncio.create_task(bot_app.updater.start_polling()) 
    
    # 5. Run FastAPI
    print(f"🚀 Server & Bot active on port {config.PORT}")
    uv_config = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    server = uvicorn.Server(uv_config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
