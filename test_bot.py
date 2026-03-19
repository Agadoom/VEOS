import os
import sqlite3
import asyncio
import uvicorn
import random
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
                  points_veo REAL DEFAULT 0.0, referred_by INTEGER)''')
    conn.commit(); conn.close()

def get_stats(uid):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
        res = c.fetchone(); conn.close()
        if res:
            total = sum(res)
            rank = get_rank_info(total)
            return {"g": res[0], "u": res[1], "v": res[2], "total": total, "rank": rank}
    except: pass
    return {"g": 0.0, "u": 0.0, "v": 0.0, "total": 0.0, "rank": get_rank_info(0)}

# --- 🌐 MINI APP API & HTML ---
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
    return """
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { background: #000; color: #0f0; font-family: 'Courier New', monospace; text-align: center; margin:0; padding:15px; }
            .terminal { border: 2px solid #0f0; padding: 15px; border-radius: 15px; height: 85vh; display: flex; flex-direction: column; justify-content: space-between; }
            .progress-bg { width: 100%; background: #002200; height: 8px; border-radius: 4px; margin: 10px 0; border: 1px solid #0f0; }
            #progress-bar { width: 0%; background: #0f0; height: 100%; transition: 0.5s; box-shadow: 0 0 10px #0f0; }
            .btn-extract { background: #0f0; color: #000; border: none; width: 140px; height: 140px; border-radius: 50%; font-weight: bold; cursor: pointer; box-shadow: 0 0 20px #0f0; font-size: 1.1em; }
            .btn-extract:active { transform: scale(0.95); opacity: 0.8; }
            .stat-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; font-size: 0.7em; margin: 15px 0; }
        </style>
    </head>
    <body>
        <div class="terminal">
            <div>
                <div id="rank-tag" style="font-weight: bold; letter-spacing: 2px;">RANK: NOVICE</div>
                <div class="progress-bg"><div id="progress-bar"></div></div>
                <div class="stat-grid">
                    <div>GENESIS<br><span id="g">0.00</span></div>
                    <div>UNITY<br><span id="u">0.00</span></div>
                    <div>VEO AI<br><span id="v">0.00</span></div>
                </div>
            </div>
            
            <div>
                <select id="sel" style="background:#000; color:#0f0; border:1px solid #0f0; padding:10px; width:90%; margin-bottom:20px;">
                    <option value="genesis">CORE: GENESIS</option>
                    <option value="unity">CORE: UNITY</option>
                    <option value="veo">CORE: VEO AI</option>
                </select><br>
                <button class="btn-extract" onclick="mine()">EXTRACT</button>
            </div>

            <div id="log" style="font-size: 0.6em; color: #008800;">> INITIALIZING SYSTEM...</div>
        </div>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            async function mine() {
                let uid = tg.initDataUnsafe.user.id;
                let t = document.getElementById('sel').value;
                tg.HapticFeedback.impactOccurred('light');

                const r = await fetch('/update_points', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ user_id: uid, token: t })
                });
                const res = await r.json();
                updateUI(res.new_balance);
                document.getElementById('log').innerText = "> PACKET EXTRACTED (x" + res.new_balance.rank.mult + ")";
            }

            function updateUI(s) {
                document.getElementById('g').innerText = s.g.toFixed(2);
                document.getElementById('u').innerText = s.u.toFixed(2);
                document.getElementById('v').innerText = s.v.toFixed(2);
                document.getElementById('rank-tag').innerText = "RANK: " + s.rank.name;
                document.getElementById('rank-tag').style.color = s.rank.color;
                let p = (s.total / s.rank.next) * 100;
                document.getElementById('progress-bar').style.width = p + "%";
            }
        </script>
    </body>
    </html>
    """

# --- 🤖 BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    
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
        [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky"), InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("🔗 Invite", callback_data="invite"), InlineKeyboardButton("💰 Invest", callback_data="invest")]
    ])
    await update.message.reply_text(f"🕊️ **OWPC PROTOCOL**\n\nRank: `{s['rank']['name']}`\nBalance: `{s['total']:.2f}` OWPC", reply_markup=kb, parse_mode="Markdown")

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id
    
    if q.data == "menu":
        await start(update, context)

    elif q.data == "passport":
        s = get_stats(uid)
        txt = (
            f"🆔 **OWPC DIGITAL PASSPORT**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 HOLDER: `{q.from_user.first_name}`\n"
            f"🏆 RANK: **{s['rank']['name']}**\n"
            f"📈 POWER: `x{s['rank']['mult']}`\n"
            f"💰 TOTAL: `{s['total']:.2f}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Status: `VERIFIED ✅`"
        )
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="menu")]]), parse_mode="Markdown")

    elif q.data == "lucky":
        win = round(random.uniform(0.1, 0.5), 2)
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (win, uid))
        conn.commit(); conn.close()
        await q.message.edit_text(f"🎰 **LUCKY DRAW**\n\nExtraction bonus: `+{win}` VEO AI!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="menu")]]))

    elif q.data == "hof":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, (points_genesis+points_unity+points_veo) as t FROM users ORDER BY t DESC LIMIT 5")
        top = c.fetchall(); conn.close()
        txt = "🏛️ **HALL OF FAME**\n\n" + "\n".join([f"{i+1}. {u[0]} - `{u[1]:.2f}`" for i,u in enumerate(top)])
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="menu")]]), parse_mode="Markdown")

    elif q.data == "invite":
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        await q.message.edit_text(f"🔗 **INVITE & EARN**\n\nReceive 10% of your friends' extractions!\n\n`{link}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="menu")]]), parse_mode="Markdown")

    elif q.data == "stats":
        s = get_stats(uid)
        txt = f"📊 **RESOURCES**\n\n- Genesis: `{s['g']:.2f}`\n- Unity: `{s['u']:.2f}`\n- Veo AI: `{s['v']:.2f}`"
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="menu")]]), parse_mode="Markdown")

    elif q.data == "invest":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 Genesis", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 Unity", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 Veo AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="menu")]
        ])
        await q.message.edit_text("💰 **DIRECT INVESTMENT**\nAccess Blum Memepad sectors:", reply_markup=kb)

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
