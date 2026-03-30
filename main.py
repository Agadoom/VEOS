import asyncio, uvicorn, os, time
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters

import config, database
from routes import mine, launcher, user, stars, lottery, premium, admin
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from routes.lottery import draw_lottery 

# --- INITIALIZATION ---
database.init_db_structure()
app = FastAPI(title="WPT Hub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# --- INDEXATION DES ROUTES ---
app.include_router(user.router)
app.include_router(mine.router)
app.include_router(launcher.router)
app.include_router(stars.router)
app.include_router(lottery.router)
app.include_router(premium.router)
app.include_router(admin.router)

# --- SERVEUR DE PAGES ---
@app.get("/secret-admin-dashboard", response_class=HTMLResponse)
async def serve_admin_page():
    if os.path.exists("admin.html"):
        with open("admin.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>❌ Admin Dashboard not found!</h1>"

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Frontend index.html not found!</h1>"

# --- TELEGRAM HANDLERS ---

# COMMANDE /ADMIN (C'est elle qui gère tout !)
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != config.ADMIN_ID:
        return 

    # On ajoute un timestamp pour briser le cache de Telegram
    v = int(time.time())
    admin_url = f"https://veos-production-a2de.up.railway.app/secret-admin-dashboard?v={v}"
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🖥️ COMMAND CENTER (LIVE)", web_app=WebAppInfo(url=admin_url))
    ]])
    
    await update.message.reply_text(
        "🛰️ <b>WPT Master Access Granted.</b>\nOpening secure dashboard...", 
        parse_mode="HTML", 
        reply_markup=keyboard
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🚀 OPEN APP", web_app=WebAppInfo(url=config.WEBAPP_URL))
    ]])
    await update.message.reply_text(f"Welcome {name}!", reply_markup=keyboard)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # (Garde ton code de paiement habituel ici...)
    pass

# --- MAIN RUNNER ---
async def main():
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    app.state.bot = bot_app.bot 

    scheduler = AsyncIOScheduler()
    scheduler.add_job(draw_lottery, 'cron', day_of_week='sun', hour=21, minute=0, args=[bot_app.bot])
    scheduler.start()

    # Enregistrement des commandes Telegram
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("admin", admin_command)) # <--- LA COMMANDE EST ICI
    bot_app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    bot_app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling()) 
    
    uv_config = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    server = uvicorn.Server(uv_config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
