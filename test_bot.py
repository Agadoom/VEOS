import os
import sqlite3
import asyncio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- 1. CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app" 
BOT_USERNAME = "OWPCsbot" # Ton username exact sans le @

app = FastAPI()

# --- 2. DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, points_unity REAL DEFAULT 0.0, 
                  points_veo REAL DEFAULT 0.0, referred_by INTEGER)''')
    conn.commit(); conn.close()

def get_stats(uid):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
        res = c.fetchone(); conn.close()
        if res: return {"g": res[0], "u": res[1], "v": res[2], "total": sum(res)}
    except: pass
    return {"g": 0.0, "u": 0.0, "v": 0.0, "total": 0.0}

def get_leaderboard():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT name, (points_genesis + points_unity + points_veo) as total FROM users ORDER BY total DESC LIMIT 5")
    res = c.fetchall(); conn.close()
    return res

# --- 3. API POUR LA MINI APP ---
@app.post("/update_points")
async def receive_points(request: Request):
    data = await request.json()
    uid, token, amount = data.get("user_id"), data.get("token"), data.get("amount", 0.05)
    if uid and token:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute(f"UPDATE users SET points_{token} = points_{token} + ? WHERE user_id = ?", (amount, uid))
        conn.commit(); conn.close()
        return {"status": "success", "new_balance": get_stats(uid)}
    return {"status": "error"}

# --- 4. MINI APP INTERFACE (HTML) ---
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
            body { background: #000; color: #0f0; font-family: monospace; text-align: center; padding: 15px; }
            .terminal { border: 2px solid #0f0; padding: 20px; border-radius: 10px; height: 80vh; display: flex; flex-direction: column; justify-content: space-between; }
            .btn-mine { background: radial-gradient(#0f0, #004400); color: #000; border: none; width: 130px; height: 130px; border-radius: 50%; font-weight: bold; cursor: pointer; box-shadow: 0 0 15px #0f0; margin: 10px auto; }
            .stats-grid { display: flex; justify-content: space-around; font-size: 0.8em; border-bottom: 1px solid #0f0; padding-bottom: 10px; }
        </style>
    </head>
    <body>
        <div class="terminal">
            <h2>> OWPC EXTRACTOR</h2>
            <div class="stats-grid">
                <div>GEN:<br><span id="val-g">0.00</span></div>
                <div>UNI:<br><span id="val-u">0.00</span></div>
                <div>VEO:<br><span id="val-v">0.00</span></div>
            </div>
            <select id="token-choice" style="background:#000; color:#0f0; border:1px solid #0f0; padding:5px;">
                <option value="genesis">GENESIS</option>
                <option value="unity">UNITY</option>
                <option value="veo">VEO AI</option>
            </select>
            <button class="btn-mine" onclick="mine()">EXTRACT</button>
            <p id="status" style="font-size:0.7em;">READY</p>
        </div>
        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            let uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : null;
            async function mine() {
                if(!uid) return;
                let t = document.getElementById('token-choice').value;
                tg.HapticFeedback.impactOccurred('medium');
                const r = await fetch('/update_points', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ user_id: uid, token: t, amount: 0.05 })
                });
                const res = await r.json();
                if(res.status === "success") {
                    document.getElementById('val-g').innerText = res.new_balance.g.toFixed(2);
                    document.getElementById('val-u').innerText = res.new_balance.u.toFixed(2);
                    document.getElementById('val-v').innerText = res.new_balance.v.toFixed(2);
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
    ref_id = int(context.args[0]) if context.args else None
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (user.id, user.first_name, ref_id))
    conn.commit(); conn.close()
    
    s = get_stats(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")]
    ])
    await update.message.reply_text(f"🕊️ **OWPC PROTOCOL**\n\nBalance: `{s['total']:.2f}` OWPC", reply_markup=kb, parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); uid = query.from_user.id
    
    if query.data == "main_menu":
        s = get_stats(uid)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
            [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
            [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
            [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")]
        ])
        await query.message.edit_text(f"🕊️ **OWPC PROTOCOL**\n\nBalance: `{s['total']:.2f}` OWPC", reply_markup=kb, parse_mode="Markdown")

    elif query.data == "stats":
        s = get_stats(uid)
        txt = f"📊 **ASSETS OVERVIEW**\n\nGenesis: `{s['g']:.2f}`\nUnity: `{s['u']:.2f}`\nVeo AI: `{s['v']:.2f}`\n\nTotal: `{s['total']:.2f}`"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")

    elif query.data == "hof":
        top = get_leaderboard()
        txt = "🏛️ **HALL OF FAME**\n\n" + "\n".join([f"{i+1}. {u[0]} - `{u[1]:.2f}`" for i, u in enumerate(top)])
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")

    elif query.data == "invite":
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        txt = f"🔗 **INVITE FRIENDS**\n\nLien: `{link}`"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")

    elif query.data == "lucky":
        win = 0.50
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (win, uid))
        conn.commit(); conn.close()
        await query.message.edit_text(f"🎰 **LUCKY DRAW**\n\nGain: `+0.50` VEO AI!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")

    elif query.data == "invest":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],[InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],[InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]])
        await query.message.edit_text("💰 **INVEST HUB**", reply_markup=kb)

# --- 6. EXECUTION ---
async def main():
    init_db()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_callbacks))
    await bot_app.initialize(); await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
