import asyncio
import uvicorn
import os
import database
import config
from datetime import datetime, timedelta

# FastAPI & Responses
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Telegram Bot API
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    ContextTypes, 
    PreCheckoutQueryHandler, 
    MessageHandler, 
    filters
)

# Planification (Loterie)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from routes.lottery import router as lottery_router, draw_lottery

# --- INITIALISATION ---
app = FastAPI(title="One World Peace Coins API")

# Configuration CORS pour éviter les blocages du WebApp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routes de la loterie
app.include_router(lottery_router)
app.include_router(mine_router)
app.include_router(stars_router)
app.include_router(premium_router)
app.include_router(admin_router)
app.include_router(launcher_router)
app.include_router(profile_router)


# --- 1. ROUTES D'AFFICHAGE (FRONT-END) ---

@app.get("/")
async def serve_home():
    """Sert l'application principale"""
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"error": "index.html introuvable"}

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    """Sert le Cockpit Admin (🛰️ Admin Access)"""
    if os.path.exists("admin.html"):
        return FileResponse("admin.html")
    return """
    <body style='background:#000;color:gold;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;'>
        <div style='text-align:center;border:1px solid #333;padding:40px;border-radius:20px;'>
            <h1 style='color:#ff4444;'>🛰️ ADMIN ERROR</h1>
            <p>Le fichier <b>admin.html</b> est absent de la racine du serveur.</p>
        </div>
    </body>
    """

# --- 2. COMMANDES DU BOT TELEGRAM ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /start pour ouvrir la WebApp"""
    name = update.effective_user.first_name
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🚀 OPEN APP", web_app=WebAppInfo(url=config.WEBAPP_URL))
    ]])
    await update.message.reply_text(f"Welcome {name} to OWPC! 🌍✨", reply_markup=keyboard)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /admin pour le centre de commande"""
    # L'URL utilise le BASE_URL défini dans ton config.py
    admin_url = f"{config.BASE_URL}/admin" 
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("💻 COMMAND CENTER", web_app=WebAppInfo(url=admin_url))
    ]])
    
    await update.message.reply_text(
        "🛰️ <b>Admin Access Granted.</b>\nAuthorized personnel only.", 
        reply_markup=keyboard, 
        parse_mode="HTML"
    )

# --- 3. GESTION DES PAIEMENTS (STARS & TURBO) ---

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Valide la transaction avant le débit"""
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Traitement après paiement réussi"""
    payment = update.message.successful_payment
    payload = payment.invoice_payload # Format attendu: stars_pack_50_uid
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
                msg = f"✅ <b>Payment Received!</b>\n{wpt_to_add:,} WPT added to your account! 🚀"

        elif "turbo_boost" in payload:
            expiry = (datetime.now() + timedelta(hours=24))
            c.execute("UPDATE users SET turbo_until = %s WHERE user_id = %s", (expiry, uid))
            msg = "✅ <b>TURBO ACTIVATED!</b>\nYour energy refills 3x faster for 24 hours! ⚡"

        conn.commit()
    except Exception as e:
        print(f"❌ Payment DB Error: {e}")
        msg = "⚠️ An error occurred while processing your WPT."
    finally:
        c.close(); conn.close()
    
    if msg:
        await update.message.reply_text(msg, parse_mode="HTML")

# --- 4. RUNNER PRINCIPAL ---

async def main():
    # A. Initialisation du Bot Telegram
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    
    # On rend l'instance du bot accessible à FastAPI pour les notifications (Loterie)
    app.state.bot = bot_app.bot 

    # B. Planification (Tirage Loterie tous les Dimanches à 21h)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(draw_lottery, 'cron', day_of_week='sun', hour=21, minute=0)
    scheduler.start()

    # C. Handlers du Bot
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("admin", admin_command))
    bot_app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    bot_app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # D. Démarrage du Bot en Polling (Async)
    await bot_app.initialize()
    await bot_app.start()
    
    # On lance le polling sans bloquer la boucle
    asyncio.create_task(bot_app.updater.start_polling()) 
    
    # E. Lancement du serveur Web FastAPI (Uvicorn)
    # On cast le port en int car Railway l'envoie parfois en string
    port = int(os.environ.get("PORT", 8080))
    
    uv_config = uvicorn.Config(app, host="0.0.0.0", port=port, loop="asyncio")
    server = uvicorn.Server(uv_config)
    
    print(f"🚀 OWPC Server started on port {port}")
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛰️ Server stopped.")
