import asyncio, uvicorn, os, time
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters

# Import de tes configurations et modules
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

# --- ROUTES ADMIN & MANIFEST ---
@app.get("/secret-admin-dashboard", response_class=HTMLResponse)
async def serve_admin_page():
    file_path = "admin.html"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>❌ Admin Dashboard file (admin.html) not found!</h1>"

@app.get("/tonconnect-manifest.json")
async def get_manifest():
    return JSONResponse({
        "url": "https://veos-production-a2de.up.railway.app",
        "name": "WPT Ecosystem",
        "iconUrl": "https://veos-production-a2de.up.railway.app/media/owpc_logo.png"
    })

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
    
    if context.args:
        param = context.args[0]
        if param.isdigit():
            referrer_id = int(param)
            if referrer_id != uid:
                user_data = database.get_user_full(uid)
                if not user_data or sum(user_data[0:3]) == 0:
                    database.add_referral_reward(uid, referrer_id)
                    try:
                        await context.bot.send_message(chat_id=referrer_id, text=f"🎁 Your friend {name} joined! +500 WPT.")
                    except: pass

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🚀 OPEN APP", web_app=WebAppInfo(url=config.WEBAPP_URL))
    ]])
    await update.message.reply_text(f"<b>Welcome {name}!</b>\n\nWPT Ecosystem is active.", parse_mode="HTML", reply_markup=keyboard)

@app.get("/admin_command_v2") # Change légèrement l'URL ici
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != config.ADMIN_ID:
        return 

    # On ajoute ?v=123 pour forcer le rafraîchissement du cache
    timestamp = int(time.time())
    url = f"https://veos-production-a2de.up.railway.app/secret-admin-dashboard?v={timestamp}"
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🖥️ COMMAND CENTER (V2)", web_app=WebAppInfo(url=url))
    ]])
    await update.message.reply_text("Re-loading Command Center... 🛰️", reply_markup=keyboard)


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
        msg = "⚠️ Payment error. Contact support."
    finally:
        c.close(); conn.close()
    if msg: await update.message.reply_text(msg, parse_mode="HTML")

# --- MAIN RUNNER ---

async def main():
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    app.state.bot = bot_app.bot 

    scheduler = AsyncIOScheduler()
    scheduler.add_job(draw_lottery, 'cron', day_of_week='sun', hour=21, minute=0, args=[bot_app.bot])
    scheduler.start()

    # Handlers (Tirage au sort, Commandes, Paiements)
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("admin", admin_command))
    bot_app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    bot_app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling()) 
    
    print(f"🚀 Server & Bot active on port {config.PORT}")
    uv_config = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    server = uvicorn.Server(uv_config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
