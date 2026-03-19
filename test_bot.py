import os
import sqlite3
import asyncio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- ⚙️ CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app" 
BOT_USERNAME = "OWPCsbot"

app = FastAPI()

# --- 📊 DATABASE ---
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

# --- 🌐 MINI APP API & HTML ---
@app.post("/update_points")
async def receive_points(request: Request):
    data = await request.json()
    uid, token = data.get("user_id"), data.get("token")
    if uid and token:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute(f"UPDATE users SET points_{token} = points_{token} + 0.05 WHERE user_id = ?", (uid,))
        conn.commit(); conn.close()
        return {"status": "success", "new_balance": get_stats(uid)}
    return {"status": "error"}

@app.get("/", response_class=HTMLResponse)
async def mini_app():
    return """
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { background: #000; color: #0f0; font-family: monospace; text-align: center; }
            .terminal { border: 2px solid #0f0; padding: 20px; margin: 10px; border-radius: 10px; height: 80vh; }
            .btn { background: #0f0; color: #000; padding: 20px; border-radius: 50%; width: 120px; height: 120px; font-weight: bold; border: none; cursor: pointer; box-shadow: 0 0 15px #0f0; }
            .grid { display: flex; justify-content: space-around; margin-bottom: 20px; font-size: 0.7em; }
        </style>
    </head>
    <body>
        <div class="terminal">
            <h3>> OWPC TERMINAL</h3>
            <div class="grid">
                <div>GEN:<br><span id="val-g">0.00</span></div>
                <div>UNI:<br><span id="val-u">0.00</span></div>
                <div>VEO:<br><span id="val-v">0.00</span></div>
            </div>
            <select id="token-choice" style="background:#000; color:#0f0; border:1px solid #0f0; margin-bottom:20px;">
                <option value="genesis">GENESIS</option>
                <option value="unity">UNITY</option>
                <option value="veo">VEO AI</option>
            </select><br>
            <button class="btn" onclick="mine()">EXTRACT</button>
            <p id="st">READY</p>
        </div>
        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            async function mine() {
                let uid = tg.initDataUnsafe.user.id;
                let t = document.getElementById('token-choice').value;
                tg.HapticFeedback.impactOccurred('medium');
                const r = await fetch('/update_points', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ user_id: uid, token: t })
                });
                const res = await r.json();
                document.getElementById('val-g').innerText = res.new_balance.g.toFixed(2);
                document.getElementById('val-u').innerText = res.new_balance.u.toFixed(2);
                document.getElementById('val-v').innerText = res.new_balance.v.toFixed(2);
            }
        </script>
    </body>
    </html>
    """

# --- 🤖 BOT LOGIC ---
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
        [InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky"), InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("🔗 Invite", callback_data="invite")]
    ])
    await update.message.reply_text(f"🕊️ **OWPC PROTOCOL**\n\nBalance: `{s['total']:.2f}` OWPC", reply_markup=kb, parse_mode="Markdown")

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id
    if q.data == "invest":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu")]
        ])
        await q.message.edit_text("💰 **INVEST HUB**", reply_markup=kb)
    elif q.data == "stats":
        s = get_stats(uid)
        txt = f"📊 **STATS**\nGen: `{s['g']:.2f}`\nUni: `{s['u']:.2f}`\nVeo: `{s['v']:.2f}`"
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu")]]), parse_mode="Markdown")
    elif q.data == "menu":
        await start(update, context) # Retour au menu principal
    elif q.data == "lucky":
        win = 0.50
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (win, uid))
        conn.commit(); conn.close()
        await q.message.edit_text(f"🎰 **LUCKY DRAW**\n\nYou won `+0.50` VEO AI!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu")]]))
    elif q.data == "invite":
        await q.message.edit_text(f"🔗 **INVITE**\n\nLien: `https://t.me/{BOT_USERNAME}?start={uid}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu")]]))
    elif q.data == "hof":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, (points_genesis + points_unity + points_veo) as t FROM users ORDER BY t DESC LIMIT 5")
        top = c.fetchall(); conn.close()
        txt = "🏛️ **TOP PLAYERS**\n\n" + "\n".join([f"{i+1}. {u[0]} - {u[1]:.2f}" for i,u in enumerate(top)])
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu")]]))

# --- RUN ---
async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CallbackQueryHandler(handle_cb))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
