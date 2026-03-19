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
    # Ajout de la colonne referred_by si elle n'existe pas
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

# --- 🌐 MINI APP API ---
@app.post("/update_points")
async def receive_points(request: Request):
    data = await request.json()
    uid, token = data.get("user_id"), data.get("token")
    if uid and token:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        # On donne 0.05 au mineur
        c.execute(f"UPDATE users SET points_{token} = points_{token} + 0.05 WHERE user_id = ?", (uid,))
        
        # BONUS PARRAIN : On cherche si l'utilisateur a été invité
        c.execute("SELECT referred_by FROM users WHERE user_id = ?", (uid,))
        ref = c.fetchone()
        if ref and ref[0]:
            # Le parrain gagne 10% (0.005)
            c.execute(f"UPDATE users SET points_{token} = points_{token} + 0.005 WHERE user_id = ?", (ref[0],))
            
        conn.commit(); conn.close()
        return {"status": "success", "new_balance": get_stats(uid)}
    return {"status": "error"}

@app.get("/", response_class=HTMLResponse)
async def mini_app():
    # Design Hacker/Retro optimisé
    return """
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { background: #000; color: #0f0; font-family: 'Courier New', monospace; text-align: center; margin:0; padding:10px; overflow:hidden; }
            .terminal { border: 2px solid #0f0; padding: 15px; border-radius: 10px; height: 90vh; display: flex; flex-direction: column; justify-content: space-between; box-shadow: inset 0 0 10px #0f0; }
            .btn-extract { background: #0f0; color: #000; border: none; width: 140px; height: 140px; border-radius: 50%; font-weight: bold; font-size: 1.2em; cursor: pointer; box-shadow: 0 0 20px #0f0; transition: 0.2s; }
            .btn-extract:active { transform: scale(0.9); box-shadow: 0 0 5px #0f0; }
            .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 5px; font-size: 0.7em; margin-bottom: 15px; border-bottom: 1px solid #0f0; padding-bottom: 10px; }
            #log { font-size: 0.6em; height: 40px; color: #008800; overflow: hidden; }
        </style>
    </head>
    <body>
        <div class="terminal">
            <div>
                <h3>> SYSTEM ONLINE</h3>
                <div class="grid">
                    <div>GENESIS<br><span id="g">0.00</span></div>
                    <div>UNITY<br><span id="u">0.00</span></div>
                    <div>VEO AI<br><span id="v">0.00</span></div>
                </div>
            </div>
            
            <div>
                <select id="sel" style="background:#000; color:#0f0; border:1px solid #0f0; padding:8px; margin-bottom:15px; width:80%;">
                    <option value="genesis">SECTOR: GENESIS</option>
                    <option value="unity">SECTOR: UNITY</option>
                    <option value="veo">SECTOR: VEO AI</option>
                </select>
                <br>
                <button class="btn-extract" onclick="mine()">EXTRACT</button>
            </div>

            <div>
                <div id="log">> IDLE...</div>
                <div style="font-size: 0.5em; margin-top:10px;">OWPC PROTOCOL v2.0 - ENCRYPTED</div>
            </div>
        </div>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            async function mine() {
                let uid = tg.initDataUnsafe.user.id;
                let t = document.getElementById('sel').value;
                document.getElementById('log').innerText = "> INITIATING EXTRACTION...";
                tg.HapticFeedback.impactOccurred('medium');

                const r = await fetch('/update_points', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ user_id: uid, token: t })
                });
                const res = await r.json();
                
                document.getElementById('g').innerText = res.new_balance.g.toFixed(2);
                document.getElementById('u').innerText = res.new_balance.u.toFixed(2);
                document.getElementById('v').innerText = res.new_balance.v.toFixed(2);
                document.getElementById('log').innerText = "> DATA PACKET RECEIVED (+0.05)";
            }
        </script>
    </body>
    </html>
    """

# --- 🤖 BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    
    # Gestion de l'invitation
    ref_by = None
    if context.args:
        try:
            ref_id = int(context.args[0])
            if ref_id != user.id: ref_by = ref_id
        except: pass

    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (user.id, user.first_name, ref_by))
    conn.commit(); conn.close()
    
    s = get_stats(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest")]
    ])
    await update.message.reply_text(f"🕊️ **OWPC PROTOCOL**\n\nCommander: `{user.first_name}`\nTotal Balance: `{s['total']:.2f}` OWPC", reply_markup=kb, parse_mode="Markdown")

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id
    
    if q.data == "menu":
        s = get_stats(uid)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
            [InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
            [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")]
        ])
        await q.message.edit_text(f"🕊️ **OWPC PROTOCOL**\nBalance: `{s['total']:.2f}`", reply_markup=kb, parse_mode="Markdown")

    elif q.data == "hof":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, (points_genesis + points_unity + points_veo) as t FROM users ORDER BY t DESC LIMIT 5")
        rows = c.fetchall(); conn.close()
        txt = "🏛️ **TOP 5 EXTRACTORS**\n\n" + "\n".join([f"{i+1}. {r[0]} - `{r[1]:.2f}`" for i,r in enumerate(rows)])
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="menu")]]), parse_mode="Markdown")

    elif q.data == "invite":
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        txt = f"🔗 **INVITATION SYSTEM**\n\nShare your link and earn **10% bonus** on every extraction your friends make!\n\nYour link:\n`{link}`"
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="menu")]]), parse_mode="Markdown")

    elif q.data == "lucky":
        # Gain aléatoire entre 0.1 et 1.0
        win = round(random.uniform(0.1, 1.0), 2)
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (win, uid))
        conn.commit(); conn.close()
        await q.message.edit_text(f"🎰 **LUCKY DRAW**\n\nSystem breach successful!\nYou found `{win}` OWPC VEO AI.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="menu")]]))

    elif q.data == "stats":
        s = get_stats(uid)
        txt = f"📊 **DETAILED ASSETS**\n\n- Genesis: `{s['g']:.2f}`\n- Unity: `{s['u']:.2f}`\n- Veo AI: `{s['v']:.2f}`"
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="menu")]]), parse_mode="Markdown")

# --- RUN ---
async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot_app = bot # Alias
    bot.add_handler(CallbackQueryHandler(handle_cb))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    import random # Nécessaire pour le lucky draw
    asyncio.run(main())
