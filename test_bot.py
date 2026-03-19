import os
import sqlite3
import asyncio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- 1. CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app" 

app = FastAPI()

# --- 2. BASE DE DONNÉES (GESTION DES TOKENS) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, 
                  points_unity REAL DEFAULT 0.0, 
                  points_veo REAL DEFAULT 0.0)''')
    conn.commit()
    conn.close()

def update_user_points(uid, token_type, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    column = f"points_{token_type}" # genesis, unity ou veo
    c.execute(f"UPDATE users SET {column} = {column} + ? WHERE user_id = ?", (amount, uid))
    conn.commit()
    conn.close()

def get_stats(uid):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
        res = c.fetchone(); conn.close()
        if res:
            return {"g": res[0] or 0.0, "u": res[1] or 0.0, "v": res[2] or 0.0, "total": sum(res)}
    except: pass
    return {"g": 0.0, "u": 0.0, "v": 0.0, "total": 0.0}

# --- 3. API POUR LA MINI APP ---
@app.post("/update_points")
async def receive_points(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    token = data.get("token") # 'genesis', 'unity' ou 'veo'
    amount = data.get("amount", 0.01)
    
    if uid and token:
        update_user_points(uid, token, amount)
        return {"status": "success", "new_balance": get_stats(uid)}
    return {"status": "error"}

# --- 4. INTERFACE MINI APP (MULTI-TOKEN) ---
@app.get("/", response_class=HTMLResponse)
async def mini_app():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OWPC Terminal</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { background: #000; color: #00ff00; font-family: 'Courier New', monospace; text-align: center; padding: 10px; }
            .terminal { border: 2px solid #00ff00; padding: 15px; border-radius: 10px; }
            .assets { display: flex; justify-content: space-around; font-size: 0.7em; margin: 15px 0; border: 1px solid #333; padding: 5px; }
            .btn-mine { background: radial-gradient(#00ff00, #004400); color: #000; border: none; padding: 30px; font-weight: bold; border-radius: 50%; width: 120px; height: 120px; cursor: pointer; box-shadow: 0 0 20px #00ff00; }
            .token-select { margin: 10px; background: #000; color: #00ff00; border: 1px solid #00ff00; padding: 5px; }
        </style>
    </head>
    <body>
        <div class="terminal">
            <h2>> OWPC EXTRACTOR</h2>
            <div class="assets">
                <div>GEN: <span id="val-g">0</span></div>
                <div>UNI: <span id="val-u">0</span></div>
                <div>VEO: <span id="val-v">0</span></div>
            </div>
            
            <select id="token-choice" class="token-select">
                <option value="genesis">MINE GENESIS</option>
                <option value="unity">MINE UNITY</option>
                <option value="veo">MINE VEO AI</option>
            </select>

            <button class="btn-mine" onclick="mine()">EXTRACT</button>
            <p id="status">IDLE</p>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            let uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : null;

            async def mine() {
                if(!uid) return;
                let token = document.getElementById('token-choice').value;
                document.getElementById('status').innerText = "MINING " + token.toUpperCase() + "...";
                tg.HapticFeedback.impactOccurred('medium');

                // Envoi au serveur Railway
                const response = await fetch('/update_points', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ user_id: uid, token: token, amount: 0.05 })
                });
                
                let result = await response.json();
                if(result.status === "success") {
                    document.getElementById('val-g').innerText = result.new_balance.g.toFixed(2);
                    document.getElementById('val-u').innerText = result.new_balance.u.toFixed(2);
                    document.getElementById('val-v').innerText = result.new_balance.v.toFixed(2);
                }
            }
        </script>
    </body>
    </html>
    """

# --- 5. BOT LOGIC (Inchangée mais stable) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()
    
    s = get_stats(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("💰 Invest Hub", callback_data="invest")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
    ])
    msg = f"🕊️ **OWPC PROTOCOL**\n\nBalance: `{s['total']:.2f}` OWPC"
    if update.message: await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")
    else: await update.callback_query.message.edit_text(msg, reply_markup=kb, parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "main_menu": await start(update, context)
    # ... (les autres boutons restent les mêmes)

async def main():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_callbacks))
    await bot_app.initialize(); await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT)
    await uvicorn.Server(config).serve()

if __name__ == "__main__":
    asyncio.run(main())
