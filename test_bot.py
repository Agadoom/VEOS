import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, PreCheckoutQueryHandler, ContextTypes

# --- CONFIGURATION (CONSERVÉE) ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = "OWPCsbot"

# --- VOLUME RAILWAY (SÉCURISÉ) ---
DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "owpc_data.db")
logging.basicConfig(level=logging.INFO)

app = FastAPI()

# --- 🗄️ DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0, points_unity REAL DEFAULT 0, 
                  points_veo REAL DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

# --- 🤖 BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (uid, name, ref_id))
        if ref_id and ref_id != uid:
            c.execute("UPDATE users SET points_unity = points_unity + 5.0, ref_count = ref_count + 1 WHERE user_id = ?", (ref_id,))
    conn.commit(); conn.close()

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚡ ACCESS TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"--- PROTOCOL OWPC v21 ---\nStatus: Encrypted\nVolume: Online", reply_markup=kb)

# --- 🛰️ API ---
@app.get("/api/user/{uid}")
async def get_user_api(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return {"g": r[0], "u": r[1], "v": r[2]} if r else {"g":0,"u":0,"v":0}

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

# --- 🌐 WEB APP (DESIGN CYBERPUNK) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {{ --neon-g: #0f0; --neon-u: #fff; --neon-v: #00e5ff; }}
            body {{ background: #050505; color: #fff; font-family: 'Courier New', monospace; overflow: hidden; margin: 0; padding: 20px; }}
            
            /* Scanline Effect */
            body::before {{ content: " "; display: block; position: absolute; top: 0; left: 0; bottom: 0; right: 0; background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06)); z-index: 2; background-size: 100% 4px, 3px 100%; pointer-events: none; }}
            
            .header {{ border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; color: var(--neon-g); text-shadow: 0 0 5px var(--neon-g); }}
            
            .token-box {{ background: rgba(20,20,20,0.8); border: 1px solid #333; border-radius: 8px; padding: 15px; margin-bottom: 15px; position: relative; overflow: hidden; }}
            .token-label {{ font-size: 12px; color: #888; letter-spacing: 2px; }}
            .token-val {{ font-size: 28px; font-weight: bold; margin: 5px 0; }}
            
            .progress-bg {{ background: #222; height: 4px; width: 100%; border-radius: 2px; margin-top: 10px; }}
            .progress-fill {{ height: 100%; width: 0%; transition: width 0.3s; }}
            
            .btn-mine {{ width: 100%; padding: 18px; border: 1px solid #444; background: transparent; color: #fff; font-family: 'Courier New'; font-weight: bold; cursor: pointer; transition: 0.2s; }}
            .btn-mine:active {{ transform: scale(0.98); background: rgba(255,255,255,0.1); }}
            
            #g-box {{ border-left: 4px solid var(--neon-g); }} .g-text {{ color: var(--neon-g); }}
            #u-box {{ border-left: 4px solid var(--neon-u); }} .u-text {{ color: var(--neon-u); }}
            #v-box {{ border-left: 4px solid var(--neon-v); }} .v-text {{ color: var(--neon-v); }}
            
            .floating-text {{ position: absolute; color: gold; font-weight: bold; pointer-events: none; animation: floatUp 0.8s forwards; }}
            @keyframes floatUp {{ from {{ transform: translateY(0); opacity: 1; }} to {{ transform: translateY(-50px); opacity: 0; }} }}
        </style>
    </head>
    <body>
        <div class="header">>> OWPC_TERMINAL_v21.0</div>
        
        <div class="token-box" id="g-box">
            <div class="token-label">GENESIS_PROTOCOL</div>
            <div class="token-val g-text" id="g_val">0.00</div>
            <div class="progress-bg"><div id="g_bar" class="progress-fill" style="background:var(--neon-g)"></div></div>
        </div>
        <button class="btn-mine" onclick="mine('genesis', this)">[ INITIALIZE EXTRACTION ]</button>

        <div class="token-box" id="u-box">
            <div class="token-label">UNITY_CORE</div>
            <div class="token-val u-text" id="u_val">0.00</div>
            <div class="progress-bg"><div id="u_bar" class="progress-fill" style="background:var(--neon-u)"></div></div>
        </div>
        <button class="btn-mine" onclick="mine('unity', this)">[ SYNC NODES ]</button>

        <div class="token-box" id="v-box">
            <div class="token-label">VEO_AI_QUANTUM</div>
            <div class="token-val v-text" id="v_val">0.00</div>
            <div class="progress-bg"><div id="v_bar" class="progress-fill" style="background:var(--neon-v)"></div></div>
        </div>
        <button class="btn-mine" onclick="mine('veo', this)">[ COMPUTE NEURALS ]</button>

        <script>
            let tg = window.Telegram.WebApp; tg.expand();
            const uid = tg.initDataUnsafe.user.id;

            async function refresh() {{
                const r = await fetch('/api/user/' + uid);
                const d = await r.json();
                document.getElementById('g_val').innerText = d.g.toFixed(2);
                document.getElementById('u_val').innerText = d.u.toFixed(2);
                document.getElementById('v_val').innerText = d.v.toFixed(2);
                
                // Update Progress Bars (loop effect)
                document.getElementById('g_bar').style.width = (d.g % 1 * 100) + "%";
                document.getElementById('u_bar').style.width = (d.u % 1 * 100) + "%";
                document.getElementById('v_bar').style.width = (d.v % 1 * 100) + "%";
            }}

            async function mine(t, btn) {{
                tg.HapticFeedback.impactOccurred('medium');
                
                // Animation flottante
                let span = document.createElement('span');
                span.className = 'floating-text';
                span.innerText = (t === 'veo' ? '+0.01' : '+0.05');
                span.style.left = Math.random() * 80 + 10 + '%';
                btn.parentElement.appendChild(span);
                setTimeout(() => span.remove(), 800);

                await fetch('/api/mine', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{user_id: uid, token: t}})
                }});
                refresh();
            }}

            refresh();
            setInterval(refresh, 3000);
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
