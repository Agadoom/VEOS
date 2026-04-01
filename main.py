import asyncio, uvicorn, os, time
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles


import config, database
from routes import mine, launcher, user, stars, lottery, premium, admin
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from routes.lottery import draw_lottery 

# --- INITIALIZATION ---
# --- INITIALIZATION ---
database.init_db_structure()

# UNE SEULE INSTANCE DE APP
app = FastAPI(title="WPT Hub API")

# CONFIGURATION JINJA2
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# MONTAGE STATIC (UNE SEULE FOIS)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# --- ROUTES API ---
app.include_router(user.router)
app.include_router(mine.router)
app.include_router(launcher.router)
app.include_router(stars.router)
app.include_router(lottery.router)
app.include_router(premium.router)
app.include_router(admin.router)

# --- ROUTE HOME ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # La nouvelle règle : request doit être passé AVANT le contexte
    return templates.TemplateResponse(
        request=request, 
        name="mine.html", 
        context={} # Tu peux laisser vide ou mettre tes autres variables ici
    )






# --- TELEGRAM HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN APP", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome {name}!", reply_markup=keyboard)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return 
    v = int(time.time())
    admin_url = f"https://veos-production-a2de.up.railway.app/secret-admin-dashboard?v={v}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🖥️ COMMAND CENTER", web_app=WebAppInfo(url=admin_url))]])
    await update.message.reply_text("🛰️ <b>Admin Access Granted.</b>", parse_mode="HTML", reply_markup=keyboard)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # --- ICI LE CODE QUI ÉTAIT MANQUANT ---
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    parts = payload.split("_")
    uid = int(parts[-1])
    
    conn = database.get_db_conn(); c = conn.cursor()
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

# --- MAIN RUNNER ---
async def main():
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    app.state.bot = bot_app.bot 

    scheduler = AsyncIOScheduler()
    scheduler.add_job(draw_lottery, 'cron', day_of_week='sun', hour=21, minute=0)

    scheduler.start()

    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("admin", admin_command))
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
