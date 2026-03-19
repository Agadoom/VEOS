import os, asyncio, uvicorn, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- IMPORT DE TON NOUVEAU MODULE ---
from data_conx import init_db, get_db_conn

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")

logging.basicConfig(level=logging.INFO)
app = FastAPI()
bot_app = None 

# --- BOT FUNCTIONS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        # Syntaxe PostgreSQL: %s au lieu de ?
        c.execute("INSERT INTO users (user_id, name) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (uid, name))
        conn.commit(); c.close(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC HUB, {name}!", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn()
    if not conn: return None
    c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_daily, total_clicks, name FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    
    c.execute("SELECT token, amount, timestamp FROM logs WHERE user_id=%s ORDER BY id DESC LIMIT 5", (uid,))
    history = [{"t": x[0], "a": x[1], "ts": x[2]} for x in c.fetchall()]
    
    c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    
    c.close(); conn.close()
    if not r: return None
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "history": history, "clicks": r[5], "name": r[6], "top": top}

@app.post("/api/reward-success/{uid}")
async def reward_success(uid: int):
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        c.execute("UPDATE users SET p_unity = p_unity + 10.0 WHERE user_id = %s", (uid,))
        c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (%s, 'STARS_REWARD', 10.0, %s)", (uid, int(time.time())))
        conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.05
    col = {"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}.get(t)
    
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        # Sécurisation du nom de colonne et injection du gain
        c.execute(f"UPDATE users SET {col} = {col} + %s, total_clicks = total_clicks + 1 WHERE user_id = %s", (gain, uid))
        c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (%s, %s, %s, %s)", (uid, t.upper(), gain, int(time.time())))
        conn.commit(); c.close(); conn.close()
    return {"ok": True}

@app.post("/api/create-invoice/{uid}")
async def create_invoice(uid: int):
    try:
        link = await bot_app.bot.create_invoice_link(
            title="10 UNITY Points Boost",
            description="Félicitations pour votre achat !",
            payload=f"stars_{uid}",
            provider_token="", currency="XTR",
            prices=[LabeledPrice("Stars", 50)]
        )
        return {"invoice_url": link}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- WEB UI (Ton code HTML reste le même) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    # ... (Copie-colle ici ton gros bloc HTML sans rien changer) ...
    return """ ... """

async def main():
    global bot_app
    init_db() # Initialisation via data_conx
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
