import asyncio, uvicorn, time, random
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Import de tes nouveaux fichiers
import config
import database

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Initialisation au démarrage
database.init_db_structure()

# --- UTILS ---
def get_badge_info(score):
    if score >= 500: return "💎 Diamond", 1000, "#00D1FF"
    if score >= 150: return "🥇 Gold", 500, "#FFD700"
    if score >= 50:  return "🥈 Silver", 150, "#C0C0C0"
    return "🥉 Bronze", 50, "#CD7F32"

# --- BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    database.register_user(uid, name, ref_id)
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌍 OPEN OWPC HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]])
    await update.message.reply_text(f"✨ Welcome {name} to OWPC DePIN Hub.", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    r = database.get_user_data(uid)
    if not r: return JSONResponse(status_code=404, content={})
    
    now = int(time.time())
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + ((now - (r[6] or now)) // 60) * config.REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, goal, color = get_badge_info(score)

    return {
        "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0, "rc": r[3] or 0, "name": r[4],
        "energy": int(current_e), "max_energy": config.MAX_ENERGY, "badge": badge,
        "score": round(score, 2), "jackpot": 0 # Ajoute ta logique jackpot ici si besoin
    }

# L'UI HTML reste identique, assure-hui juste d'utiliser config.WEBAPP_URL
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    # ... Insère ici ton code HTML précédent ...
    return "Contenu HTML"

async def main():
    bot_app = ApplicationBuilder().token(config.TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    
    uv_config = uvicorn.Config(app, host="0.0.0.0", port=config.PORT, loop="asyncio")
    await uvicorn.Server(uv_config).serve()

if __name__ == "__main__":
    asyncio.run(main())
