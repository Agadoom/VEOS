import os, asyncio, uvicorn, logging, time, psycopg2
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
DATABASE_URL = os.getenv("DATABASE_URL") # Récupère le lien vers ton Postgres Railway

logging.basicConfig(level=logging.INFO)
app = FastAPI()
bot_app = None 

# Connexion sécurisée à PostgreSQL
def get_db_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_db_conn(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id BIGINT PRIMARY KEY, name TEXT, 
                  p_genesis REAL DEFAULT 0, p_unity REAL DEFAULT 0, 
                  p_veo REAL DEFAULT 0, ref_count INTEGER DEFAULT 0,
                  total_clicks INTEGER DEFAULT 0,
                  last_daily INTEGER DEFAULT 0, referred_by BIGINT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id SERIAL PRIMARY KEY, user_id BIGINT, 
                  token TEXT, amount REAL, timestamp INTEGER)''')
    conn.commit(); c.close(); conn.close()

# --- BOT FUNCTIONS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    conn = get_db_conn(); c = conn.cursor()
    c.execute("INSERT INTO users (user_id, name) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (uid, name))
    conn.commit(); c.close(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to OWPC HUB, {name}!", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count, last_daily, total_clicks, name FROM users WHERE user_id=%s", (uid,))
    r = c.fetchone()
    if not r: 
        c.close(); conn.close(); return None
    c.execute("SELECT token, amount, timestamp FROM logs WHERE user_id=%s ORDER BY id DESC LIMIT 5", (uid,))
    history = [{"t": x[0], "a": x[1], "ts": x[2]} for x in c.fetchall()]
    c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 5")
    top = [{"n": x[0], "p": round(x[1], 2)} for x in c.fetchall()]
    c.close(); conn.close()
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3], "history": history, "clicks": r[5], "name": r[6], "top": top}

@app.post("/api/create-invoice/{uid}")
async def create_invoice(uid: int):
    try:
        link = await bot_app.bot.create_invoice_link(
            title="10 UNITY Points Boost",
            description="Félicitations pour votre achat de points UNITY !",
            payload=f"stars_{uid}_{int(time.time())}",
            provider_token="", 
            currency="XTR",
            prices=[LabeledPrice("Stars", 50)]
        )
        return {"invoice_url": link}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/reward-success/{uid}")
async def reward_success(uid: int):
    conn = get_db_conn(); c = conn.cursor()
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
    conn = get_db_conn(); c = conn.cursor()
    c.execute(f"UPDATE users SET {col} = {col} + %s, total_clicks = total_clicks + 1 WHERE user_id = %s", (gain, uid))
    c.execute("INSERT INTO logs (user_id, token, amount, timestamp) VALUES (%s, %s, %s, %s)", (uid, t.upper(), gain, int(time.time())))
    conn.commit(); c.close(); conn.close()
    return {"ok": True}

# --- WEB UI (Ton HTML original, inchangé) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return r"""
    ... (Insère ici tout ton bloc HTML de l'étape précédente) ...
    """

async def main():
    global bot_app
    init_db()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    await bot_app.initialize()
    await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
