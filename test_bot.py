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

# --- 2. BASE DE DONNÉES ---
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
    column = f"points_{token_type}"
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
    token = data.get("token")
    amount = data.get("amount", 0.05)
    if uid and token:
        update_user_points(uid, token, amount)
        return {"status": "success", "new_balance": get_stats(uid)}
    return {"status": "error"}

# --- 4. INTERFACE MINI APP (HTML/JS) ---
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
            body { background: #000; color: #00ff00; font-family: 'Courier New', monospace; text-align: center; margin: 0; padding: 15px; }
            .terminal { border: 2px solid #00ff00; padding: 20px; border-radius: 10px; height: 85vh; display: flex; flex-direction: column; justify-content: space-between; }
            .assets { display: flex; justify-content: space-around; font-size: 0.8em; border-bottom: 1px solid #00ff00; padding-bottom: 10px; }
            .btn-mine { 
                background: radial-gradient(#00ff00, #004400); color: #000; border: none; 
                width: 140px; height: 140px; border-radius: 50%; font-weight: bold; 
                box-shadow: 0 0 20px #00ff00; cursor: pointer; margin: 20px auto;
            }
            .btn-mine:active { transform: scale(0.95); box-shadow: 0 0 5px #00ff00; }
            select { background: #000; color: #00ff00; border: 1px solid #00ff00; padding: 10px; width: 80%; margin: 10px auto; }
            #status { font-size: 0.7em; color: #008800; }
        </style>
    </head>
    <body>
        <div class="terminal">
            <div>
                <h2>> OWPC EXTRACTOR</h2>
                <div class="assets">
                    <div>GEN:<br><span id="val-g">0.00</span></div>
                    <div>UNI:<br><span id="val-u">0.00</span></div>
                    <div>VEO:<br><span id="val-v">0.00</span></div>
                </div>
            </div>

            <div>
                <select id="token-choice">
                    <option value="genesis">GENESIS SECTOR</option>
                    <option value="unity">UNITY SECTOR</option>
                    <option value="veo">VEO AI SECTOR</option>
                </select>
                <button class="btn-mine" onclick="mine()">EXTRACT</button>
                <p id="status">SYSTEM IDLE</p>
            </div>
            
            <div style="font-size: 0.6em;">OWPC PROTOCOL v1.0.4</div>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            let uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : null;

            async function mine() {
                if(!uid) return;
                let token = document.getElementById('token-choice').value;
                document.getElementById('status').innerText = "CONNECTING TO NODE...";
                tg.HapticFeedback.impactOccurred('medium');

                try {
                    const response = await fetch('/update_points', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ user_id: uid, token: token, amount: 0.05 })
                    });
                    const result = await response.json();
                    if(result.status === "success") {
                        document.getElementById('val-g').innerText = result.new_balance.g.toFixed(2);
                        document.getElementById('val-u').innerText = result.new_balance.u.toFixed(2);
                        document.getElementById('val-v').innerText = result.new_balance.v.toFixed(2);
                        document.getElementById('status').innerText = "DATA EXTRACTED SUCCESSFULLY";
                    }
                } catch (e) {
                    document.getElementById('status').innerText = "NODE CONNECTION FAILED";
                }
            }
        </script>
    </body>
    </html>
    """

# --- 5. LOGIQUE DU BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()
    
    s = get_stats(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("📊 Stats", callback_data="stats")]
    ])
    msg = f"🕊️ **OWPC PROTOCOL**\n\nCommander: `{user.first_name}`\nBalance: `{s['total']:.2f}` OWPC"
    
    if update.message: await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")
    else: await update.callback_query.message.edit_text(msg, reply_markup=kb, parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid = query.from_user.id
    if query.data == "main_menu": await start(update, context)
    elif query.data == "stats":
        s = get_stats(uid)
        txt = f"📊 **STATS**\n\nGen: `{s['g']:.2f}`\nUni: `{s['u']:.2f}`\nVeo: `{s['v']:.2f}`"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")
    elif query.data == "passport":
        txt = f"🆔 **PASSPORT**\n\nHolder: `{query.from_user.first_name}`\nStatus: `VERIFIED ✅`"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")
    elif query.data == "invest":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
        ])
        await query.message.edit_text("💰 **INVEST HUB**", reply_markup=kb)
    elif query.data in ["hof"]:
        await query.message.edit_text("🏛️ **HALL OF FAME**\nComing soon...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]))

# --- 6. EXECUTION ---
async def main():
    init_db()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_callbacks))
    await bot_app.initialize(); await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT)
    await uvicorn.Server(config).serve()

if __name__ == "__main__":
    asyncio.run(main())
