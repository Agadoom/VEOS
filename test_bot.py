import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = "OWPCsbot"

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "owpc_data.db")

app = FastAPI()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0, points_unity REAL DEFAULT 0, 
                  points_veo REAL DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

# --- BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (uid, name, ref_id))
        if ref_id and ref_id != uid:
            # Bonus de parrainage immédiat pour le parrain
            c.execute("UPDATE users SET points_unity = points_unity + 5.0, ref_count = ref_count + 1 WHERE user_id = ?", (ref_id,))
    conn.commit(); conn.close()

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💎 OPEN OWPC TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome {name}.\nYour mining nodes are ready.", reply_markup=kb)

# --- API ---
@app.get("/api/user/{uid}")
async def get_user_api(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, ref_count FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3]} if r else {"g":0,"u":0,"v":0,"rc":0}

@app.post("/api/mine")
async def api_mine(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    col = {"genesis":"points_genesis", "unity":"points_unity", "veo":"points_veo"}.get(t)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET {col} = {col} + ? WHERE user_id = ?", (gain, uid))
    conn.commit(); conn.close()
    return {"ok": True}

# --- WEB APP ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {{ --g: #00ff88; --u: #ffffff; --v: #00d9ff; --bg: #0a0e17; }}
            body {{ background: var(--bg); color: #fff; font-family: 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; text-align: center; }}
            
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 12px; }}
            .ref-badge {{ background: gold; color: #000; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }}

            .card {{ background: linear-gradient(145deg, #161c27, #0b0f19); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 20px; margin-bottom: 15px; box-shadow: 0 10px 20px rgba(0,0,0,0.3); }}
            .label {{ font-size: 12px; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }}
            .val {{ font-size: 32px; font-weight: 800; margin: 10px 0; font-family: 'Courier New', monospace; }}
            
            .btn-mine {{ width: 100%; padding: 18px; border-radius: 15px; border: none; font-weight: bold; font-size: 16px; cursor: pointer; transition: 0.3s; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }}
            .btn-mine:active {{ transform: scale(0.96); opacity: 0.8; }}
            
            .btn-share {{ background: #2b3344; color: #fff; padding: 15px; border-radius: 12px; border: 1px solid #444; width: 100%; font-weight: bold; margin-top: 10px; display: flex; align-items: center; justify-content: center; gap: 10px; }}
            
            .floating {{ position: absolute; font-weight: bold; color: var(--g); pointer-events: none; animation: up 1s forwards; }}
            @keyframes up {{ 0%{{transform:translateY(0);opacity:1}} 100%{{transform:translateY(-60px);opacity:0}} }}
        </style>
    </head>
    <body>
        <div class="header">
            <span style="font-weight:bold; color:var(--v)">OWPC PROTOCOL</span>
            <div class="ref-badge">Parrains: <span id="ref_count">0</span></div>
        </div>
        
        <div class="card" style="border-top: 4px solid var(--g)">
            <div class="label">Genesis Balance</div>
            <div class="val" style="color:var(--g)" id="g_val">0.00</div>
            <button class="btn-mine" style="background:var(--g); color:#000" onclick="mine('genesis', this)">EXTRACT GENESIS</button>
        </div>

        <div class="card" style="border-top: 4px solid var(--u)">
            <div class="label">Unity Core</div>
            <div class="val" style="color:var(--u)" id="u_val">0.00</div>
            <button class="btn-mine" style="background:var(--u); color:#000" onclick="mine('unity', this)">HARVEST UNITY</button>
        </div>

        <div class="card" style="border-top: 4px solid var(--v)">
            <div class="label">Veo AI Tokens</div>
            <div class="val" style="color:var(--v)" id="v_val">0.00</div>
            <button class="btn-mine" style="background:var(--v); color:#000" onclick="mine('veo', this)">COMPUTE VEO</button>
        </div>

        <button class="btn-share" onclick="share()">
            <span>🔗</span> INVITE FRIENDS (+5 UNITY)
        </button>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            const uid = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 0;

            async function refresh() {{
                if(!uid) return;
                const r = await fetch('/api/user/' + uid);
                const d = await r.json();
                document.getElementById('g_val').innerText = d.g.toFixed(2);
                document.getElementById('u_val').innerText = d.u.toFixed(2);
                document.getElementById('v_val').innerText = d.v.toFixed(2);
                document.getElementById('ref_count').innerText = d.rc;
            }}

            async function mine(t, btn) {{
                tg.HapticFeedback.impactOccurred('rigid');
                let float = document.createElement('div');
                float.className = 'floating';
                float.innerText = (t==='veo' ? '+0.01' : '+0.05');
                float.style.left = '50%'; float.style.top = '20%';
                btn.parentElement.appendChild(float);
                setTimeout(()=>float.remove(), 1000);

                await fetch('/api/mine', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{user_id: uid, token: t}})
                }});
                refresh();
            }}

            function share() {{
                const url = `https://t.me/{BOT_USERNAME}?start=${{uid}}`;
                const text = "Join me on OWPC and start mining Genesis tokens!";
                tg.openTelegramLink(`https://t.me/share/url?url=${{encodeURIComponent(url)}}&text=${{encodeURIComponent(text)}}`);
            }}

            refresh();
            setInterval(refresh, 5000);
        </script>
    </body>
    </html>
    """

async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling())
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__": asyncio.run(main())
