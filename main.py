import asyncio
import uvicorn
import database
import config  # <--- CRITIQUE : Assure-toi que ce fichier existe !
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import FileResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import de ta fonction de loterie depuis ton autre fichier
from routes.lottery import draw_lottery 

app = FastAPI()

# --- 1. ROUTE POUR SERVIR L'ADMIN HTML ---
@app.get("/admin")
async def serve_admin():
    # On renvoie le fichier admin.html pour que le bouton Telegram marche
    return FileResponse("admin.html")

# --- 2. COMMANDES TELEGRAM ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    # On utilise config.WEBAPP_URL défini dans ton config.py
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🚀 OPEN APP", web_app=WebAppInfo(url=config.WEBAPP_URL))
    ]])
    await update.message.reply_text(f"Welcome {name}!", reply_markup=keyboard)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Correction : On utilise config en minuscules comme ton import
    admin_url = f"{config.BASE_URL}/admin" 
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("💻 COMMAND CENTER", web_app=WebAppInfo(url=admin_url))
    ]])
    
    await update.message.reply_text("🛰️ <b>Admin Access Granted.</b>", reply_markup=keyboard, parse_mode="HTML")

# --- 3. GESTION DES PAIEMENTS STARS ---
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    parts = payload.split("_")
    uid = int(parts[-1])
    
    conn = database.get_db_conn()
    c = conn.cursor()
    msg = ""
    try:
        if "stars_pack_" in payload:
            amount_stars = int(parts[2])
            wpt_to_add = 0
            if amount_stars == 50: wpt_to_add = 10000
            elif amount_stars == 250: wpt_to_add = 60000
            elif amount_stars == 1000: wpt_to_add = 300000
            
            if wpt_to_add > 0:
                c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (wpt_to_add, uid))
                msg = f"✅ <b>Payment Received!</b>\n{wpt_to_add:,} WPT added. 🚀"

        elif "turbo_boost" in payload:
            expiry = (datetime.now() + timedelta(hours=24))
            c.execute("UPDATE users SET turbo_until = %s WHERE user_id = %s", (expiry, uid))
            msg = "✅ <b>TURBO ACTIVATED!</b>\nRefill 3x faster for 24h! ⚡"

        conn.commit()
    except Exception as e:
        print(f"❌ Payment Error: {e}")
        msg = "⚠️ Error processing payment."
    finally:
        c.close(); conn.close()
    
    if msg: await update.message.reply_text(msg, parse_mode="HTML")

# --- 4. MAIN RUNNER (LE CŒUR) ---
async def main():
    # Initialisation du Bot
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    
    # CRITIQUE : On stocke le bot pour que FastAPI puisse envoyer des notifs
    app.state.bot = bot_app.bot 

    # Scheduler pour la loterie le Dimanche à 21h
    scheduler = AsyncIOScheduler()
    scheduler.add_job(draw_lottery, 'cron', day_of_week='sun', hour=21, minute=0)
    scheduler.start()

    # Handlers Telegram
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("admin", admin_command))
    bot_app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    bot_app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Lancement du Bot en mode polling
    await bot_app.initialize()
    await bot_app.start()
    
    # Démarrage du polling dans une tâche séparée
    polling_task = asyncio.create_task(bot_app.updater.start_polling()) 
    
    # Lancement du serveur FastAPI (Uvicorn)
    uv_config = uvicorn.Config(app, host="0.0.0.0", port=int(config.PORT), loop="asyncio")
    server = uvicorn.Server(uv_config)
    
    try:
        await server.serve()
    finally:
        # Nettoyage en cas d'arrêt
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()

if __name__ == "__main__":
    # Correction : On utilise une gestion d'exception pour éviter les erreurs d'event loop
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
