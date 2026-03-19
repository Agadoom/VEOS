import os
import sqlite3
import asyncio
import uvicorn
import random
from datetime import datetime, date
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

# --- 📊 LOGIQUE DE PROGRESSION ---
def get_rank_info(total_points):
    if total_points < 25:
        return {"name": "🆕 NOVICE", "mult": 1.0, "next": 25, "color": "#888888"}
    elif total_points < 100:
        return {"name": "🛠️ SPECIALIST", "mult": 2.0, "next": 100, "color": "#50ff50"}
    elif total_points < 500:
        return {"name": "⚡ EXTRACTOR", "mult": 5.0, "next": 500, "color": "#3399ff"}
    else:
        return {"name": "🐋 WHALE", "mult": 10.0, "next": 999999, "color": "#ffcc00"}

# --- 🗄️ DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, points_unity REAL DEFAULT 0.0, 
                  points_veo REAL DEFAULT 0.0, referred_by INTEGER,
                  last_bonus TEXT DEFAULT '')''')
    conn.commit(); conn.close()

def get_stats(uid):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo, last_bonus FROM users WHERE user_id=?", (uid,))
        res = c.fetchone(); conn.close()
        if res:
            total = sum(res[:3])
            return {"g": res[0], "u": res[1], "v": res[2], "total": total, "rank": get_rank_info(total), "last_bonus": res[3]}
    except: pass
    return {"g": 0.0, "u": 0.0, "v": 0.0, "total": 0.0, "rank": get_rank_info(0), "last_bonus": ""}

# --- 🌐 MINI APP API ---
@app.post("/update_points")
async def receive_points(request: Request):
    data = await request.json()
    uid, token = data.get("user_id"), data.get("token")
    if uid and token:
        s = get_stats(uid)
        gain = 0.05 * s['rank']['mult']
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute(f"UPDATE users SET points_{token} = points_{token} + ? WHERE user_id = ?", (gain, uid))
        c.execute("SELECT referred_by FROM users WHERE user_id = ?", (uid,))
        ref = c.fetchone()
        if ref and ref[0]:
            c.execute(f"UPDATE users SET points_{token} = points_{token} + ? WHERE user_id = ?", (gain * 0.1, ref[0]))
        conn.commit(); conn.close()
        return {"status": "success", "new_balance": get_stats(uid)}
    return {"status": "error"}

@app.get("/", response_class=HTMLResponse)
async def mini_app():
    # (Le code HTML reste identique à la V3 mais avec l'API V4)
    return """
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"><script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>body { background: #000; color: #0f0; font-family: monospace; text-align: center; margin:0; padding:15px; } .terminal { border: 2px solid #0f0; padding: 15px; border-radius: 15px; height: 85vh; display: flex; flex-direction: column; justify-content: space-between; } .progress-bg { width: 100%; background: #002200; height: 8px; border-radius: 4px; margin: 10px 0; border: 1px solid #0f0; } #progress-bar { width: 0%; background: #0f0; height: 100%; transition: 0.5s; } .btn-extract { background: #0f0; color: #000; border: none; width: 140px; height: 140px; border-radius: 50%; font-weight: bold; cursor: pointer; box-shadow: 0 0 20px #0f0; }</style></head>
    <body><div class="terminal"><div><div id="rank-tag">RANK: NOVICE</div><div class="progress-bg"><div id="progress-bar"></div></div><div style="display:grid; grid-template-columns:1fr 1fr 1fr; font-size:0.7em;"><div>G:<br><span id="g">0</span></div><div>U:<br><span id="u">0</span></div><div>V:<br><span id="v">0</span></div></div></div>
    <div><select id="sel" style="background:#000; color:#0f0; border:1px solid #0f0; padding:10px; width:90%;"><option value="genesis">GENESIS</option><option value="unity">UNITY</option><option value="veo">VEO AI</option></select><br><br><button class="btn-extract" onclick="mine()">EXTRACT</button></div>
    <div id="log" style="font-size: 0.6em;">> SYSTEM ONLINE</div></div>
    <script>let tg = window.Telegram.WebApp; tg.expand(); async function mine() { let uid = tg.initDataUnsafe.user.id; let t = document.getElementById('sel').value; const r = await fetch('/update_points', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ user_id: uid, token: t })}); const res = await r.json(); updateUI(res.new_balance); }
    function updateUI(s) { document.getElementById('g').innerText = s.g.toFixed(2); document.getElementById('u').innerText = s.u.toFixed(2); document.getElementById('v').innerText = s.v.toFixed(2); document.getElementById('rank-tag').innerText = "RANK: " + s.rank.name; let p = (s.total / s.rank.next) * 100; document.getElementById('progress-bar').style.width = p + "%"; }</script></body></html>
    """

# --- 🤖 BOT LOGIC ---
async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    
    # Inscription + Parrainage
    ref_by = None
    if context.args:
        try:
            rid = int(context.args[0])
            if rid != user.id: ref_by = rid
        except: pass

    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (user.id, user.first_name, ref_by))
    conn.commit(); conn.close()
    
    s = get_stats(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily"), InlineKeyboardButton("🆔 Passport", callback_data="passport")],
        [InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof"), InlineKeyboardButton("🎰 Lucky", callback_data="lucky")],
        [InlineKeyboardButton("🔗 Invite Friends", callback_data="invite"), InlineKeyboardButton("💰 Invest", callback_data="invest")]
    ])
    
    text = f"🕊️ **OWPC PROTOCOL**\n\nRank: `{s['rank']['name']}`\nBalance: `{s['total']:.2f}` OWPC"
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id
    
    if q.data == "back_to_main":
        await start_menu(update, context)

    elif q.data == "daily":
        today = date.today().isoformat()
        s = get_stats(uid)
        if s['last_bonus'] == today:
            await q.message.edit_text("⏳ **BONUS ALREADY CLAIMED**\n\nCome back tomorrow for more OWPC!", 
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]]))
        else:
            bonus = 1.0 * s['rank']['mult'] # Bonus indexé sur le rang !
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE users SET points_genesis = points_genesis + ?, last_bonus = ? WHERE user_id = ?", (bonus, today, uid))
            conn.commit(); conn.close()
            await q.message.edit_text(f"🎁 **DAILY BONUS GRANTED**\n\nYou received `{bonus}` OWPC Genesis!\n\nRank Multiplier x{s['rank']['mult']} applied.", 
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]]))

    elif q.data == "passport":
        s = get_stats(uid)
        txt = f"🆔 **OWPC PASSPORT**\n\nHolder: `{q.from_user.first_name}`\nRank: **{s['rank']['name']}**\nPower: `x{s['rank']['mult']}`\n\nStatus: `ACTIVE ✅`"
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]]), parse_mode="Markdown")

    elif q.data == "hof":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, (points_genesis+points_unity+points_veo) as t FROM users ORDER BY t DESC LIMIT 5")
        top = c.fetchall(); conn.close()
        txt = "🏛️ **TOP EXTRACTORS**\n\n" + "\n".join([f"{i+1}. {u[0]} - `{u[1]:.2f}`" for i,u in enumerate(top)])
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]]), parse_mode="Markdown")

    elif q.data == "invite":
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        await q.message.edit_text(f"🔗 **NETWORK**\n\nEarn 10% from your friends!\n\n`{link}`", 
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]]), parse_mode="Markdown")

    elif q.data == "invest":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 Genesis", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 Unity", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 Veo AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
        ])
        await q.message.edit_text("💰 **INVEST SECTORS**", reply_markup=kb)

    elif q.data == "lucky":
        win = round(random.uniform(0.1, 0.4), 2)
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (win, uid))
        conn.commit(); conn.close()
        await q.message.edit_text(f"🎰 **LUCKY DRAW**\n\nYou found `+{win}` VEO AI!", 
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]]))

# --- RUN ---
async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start_menu))
    bot.add_handler(CallbackQueryHandler(handle_cb))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
