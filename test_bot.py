import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from telegram import Update, LabeledPrice, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, PreCheckoutQueryHandler, MessageHandler, filters, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = os.getenv("WEBAPP_URL")
CHANNEL_ID = "@owpc_co"  # Ton canal pour la vérification

app = FastAPI()

# --- 🗄️ DATABASE EXTENSION ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, points_unity REAL DEFAULT 0.0, 
                  points_veo REAL DEFAULT 0.0, task_channel INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

# --- 🤖 BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Gestion Boosts (Stars)
    if context.args and "boost" in context.args[0]:
        token = context.args[0].split('_')[1]
        price = 100 if token == "veo" else 50
        await update.message.reply_invoice(
            title=f"🚀 {token.upper()} BOOST",
            description=f"Instantly receive tokens via Telegram Stars!",
            payload=f"boost_{token}", provider_token="", currency="XTR",
            prices=[LabeledPrice("Boost", price)]
        )
        return

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text("Welcome to OWPC. Complete tasks to earn VEO AI.", reply_markup=kb)

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def payment_success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = update.message.successful_payment.invoice_payload.split('_')[1]
    amount = 5.0 if token == "veo" else 10.0
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET points_{token} = points_{token} + ? WHERE user_id = ?", (amount, update.effective_user.id))
    conn.commit(); conn.close()
    await update.message.reply_text(f"✅ Success! +{amount} {token.upper()} credited.")

# --- 🌐 WEB APP API (TASKS) ---
@app.get("/api/get_user/{uid}")
async def get_user(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, task_channel FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return {"g": r[0], "u": r[1], "v": r[2], "task_done": r[3]} if r else {"g":0,"u":0,"v":0,"task_done":0}

@app.post("/api/check_task")
async def check_task(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    # Vérification réelle via l'API Telegram
    bot = ApplicationBuilder().token(TOKEN).build().bot
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=uid)
        if member.status in ['member', 'administrator', 'creator']:
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            # On vérifie si déjà récompensé
            c.execute("SELECT task_channel FROM users WHERE user_id=?", (uid,))
            if c.fetchone()[0] == 0:
                c.execute("UPDATE users SET points_veo = points_veo + 2.0, task_channel = 1 WHERE user_id = ?", (uid,))
                conn.commit()
                conn.close()
                return {"status": "success", "msg": "+2.00 VEO Credited!"}
            return {"status": "error", "msg": "Already claimed"}
    except: pass
    return {"status": "error", "msg": "Not a member yet"}

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {{ background: #000; color: #fff; font-family: sans-serif; text-align: center; }}
        .task-card {{ background: #111; border: 1px solid #333; padding: 15px; margin: 10px; border-radius: 10px; }}
        .btn-check {{ background: #0f0; border: none; padding: 10px; border-radius: 5px; font-weight: bold; cursor:pointer; }}
    </style>
    </head>
    <body>
        <h2>OWPC TASKS</h2>
        <div class="task-card">
            <p>Join @owpc_co (+2.00 VEO)</p>
            <button class="btn-check" onclick="checkTask()">CHECK & CLAIM</button>
        </div>
        <hr>
        <button style="background:gold; padding:15px; width:90%; font-weight:bold; border-radius:10px;" onclick="tg.openTelegramLink('https://t.me/OWPCsbot?start=boost_veo')">⭐ BOOST VEO (100 Stars)</button>
        
        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            async function checkTask() {{
                const res = await fetch('/api/check_task', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{user_id: tg.initDataUnsafe.user.id}})
                }});
                const d = await res.json();
                alert(d.msg);
            }}
        </script>
    </body></html>
    """

async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(PreCheckoutQueryHandler(precheckout))
    bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_success))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
