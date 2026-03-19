import os
import sqlite3
import asyncio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- 1. CONFIGURATION (Historique récupéré) ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app" 
BOT_USERNAME = "OWPCsbot"

# Liens officiels récupérés
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK"

app = FastAPI()

# --- 2. BASE DE DONNÉES ---
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

# --- 3. API & INTERFACE TERMINAL ---
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
    return f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body {{ background: #000; color: #0f0; font-family: monospace; text-align: center; }}
            .terminal {{ border: 2px solid #0f0; padding: 20px; margin: 10px; border-radius: 10px; height: 85vh; display: flex; flex-direction: column; justify-content: space-between; }}
            .btn {{ background: radial-gradient(#0f0, #004400); color: #000; padding: 20px; border-radius: 50%; width: 130px; height: 130px; font-weight: bold; border: none; cursor: pointer; box-shadow: 0 0 15px #0f0; margin: 10px auto; }}
            .grid {{ display: flex; justify-content: space-around; margin-bottom: 20px; font-size: 0.7em; border-bottom: 1px solid #0f0; padding-bottom: 10px; }}
            select {{ background:#000; color:#0f0; border:1px solid #0f0; padding:10px; width: 80%; }}
        </style>
    </head>
    <body>
        <div class="terminal">
            <div>
                <h3>> OWPC TERMINAL</h3>
                <div class="grid">
                    <div>GENESIS:<br><span id="val-g">0.00</span></div>
                    <div>UNITY:<br><span id="val-u">0.00</span></div>
                    <div>VEO AI:<br><span id="val-v">0.00</span></div>
                </div>
            </div>
            <div>
                <select id="token-choice">
                    <option value="genesis">GENESIS SECTOR</option>
                    <option value="unity">UNITY SECTOR</option>
                    <option value="veo">VEO AI SECTOR</option>
                </select><br><br>
                <button class="btn" onclick="mine()">EXTRACT</button>
                <p id="st">SYSTEM READY</p>
            </div>
            <div style="font-size: 0.6em; opacity: 0.5;">PROTOCOL V1.0.5 - SECURE CONNECTION</div>
        </div>
        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            async function mine() {{
                let uid = tg.initDataUnsafe.user.id;
                let t = document.getElementById('token-choice').value;
                tg.HapticFeedback.impactOccurred('medium');
                try {{
                    const r = await fetch('/update_points', {{
                        method: 'POST', headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{ user_id: uid, token: t }})
                    }});
                    const res = await r.json();
                    document.getElementById('val-g').innerText = res.new_balance.g.toFixed(2);
                    document.getElementById('val-u').innerText = res.new_balance.u.toFixed(2);
                    document.getElementById('val-v').innerText = res.new_balance.v.toFixed(2);
                    document.getElementById('st').innerText = "EXTRACTION SUCCESS";
                }} catch(e) {{ document.getElementById('st').innerText = "NODE ERROR"; }}
            }}
        </script>
    </body>
    </html>
    """

# --- 4. LOGIQUE DU BOT & BOUTON RETOUR ---
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
        [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")]
    ])
    msg = f"🕊️ **OWPC PROTOCOL**\n\nCommander: `{user.first_name}`\nBalance: `{s['total']:.2f}` OWPC"
    
    if update.message:
        await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.callback_query.message.edit_text(msg, reply_markup=kb, parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid = query.from_user.id
    
    # --- CORRECTION BOUTON RETOUR ---
    if query.data == "main_menu":
        await start(update, context)
        return

    if query.data == "invest":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS (Blum)", url=LINK_GENESIS)],
            [InlineKeyboardButton("🌍 UNITY (Blum)", url=LINK_UNITY)],
            [InlineKeyboardButton("🤖 VEO AI (Blum)", url=LINK_VEO)],
            [InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="main_menu")]
        ])
        await query.message.edit_text("💰 **INVEST HUB**\nSelect a sector to invest through Blum Memepad:", reply_markup=kb, parse_mode="Markdown")

    elif query.data == "stats":
        s = get_stats(uid)
        txt = f"📊 **ASSETS OVERVIEW**\n\nGenesis: `{s['g']:.2f}`\nUnity: `{s['u']:.2f}`\nVeo AI: `{s['v']:.2f}`\n\nTotal: `{s['total']:.2f}`"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="main_menu")]]), parse_mode="Markdown")

    elif query.data == "passport":
        txt = f"🆔 **PASSPORT**\n\nHolder: `{query.from_user.first_name}`\nStatus: `VERIFIED ✅`"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="main_menu")]]), parse_mode="Markdown")

    elif query.data == "lucky":
        win = 0.50
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (win, uid))
        conn.commit(); conn.close()
        await query.message.edit_text(f"🎰 **LUCKY DRAW**\n\nYou won `+0.50` VEO AI!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="main_menu")]]))

    elif query.data == "invite":
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        await query.message.edit_text(f"🔗 **INVITE FRIENDS**\n\nShare your link:\n`{link}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="main_menu")]]), parse_mode="Markdown")

    elif query.data == "hof":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, (points_genesis + points_unity + points_veo) as t FROM users ORDER BY t DESC LIMIT 5")
        top = c.fetchall(); conn.close()
        txt = "🏛️ **HALL OF FAME**\n\n" + "\n".join([f"{i+1}. {u[0]} - `{u[1]:.2f}`" for i,u in enumerate(top)])
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="main_menu")]]), parse_mode="Markdown")

# --- 5. RUN ---
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
