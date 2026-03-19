import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_USERNAME = "OWPCsbot"

DATA_DIR = "/app/data" if os.path.exists("/app") else "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "owpc_pro_v27.db")

logging.basicConfig(level=logging.INFO)
app = FastAPI()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  p_genesis REAL DEFAULT 0, p_unity REAL DEFAULT 0, 
                  p_veo REAL DEFAULT 0, ref_count INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

# --- BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    
    if context.args and context.args[0] == "donate":
        await update.message.reply_invoice(
            title="🚀 VEO BOOST",
            description="Add +10.00 VEO to your account!",
            payload="boost_veo",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("Payer", 50)]
        )
        return

    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    conn.commit(); conn.close()
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome back to the Ecosystem.", reply_markup=kb)

# --- API ---
@app.get("/api/user/{{uid}}")
async def get_user(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return {{"g": r[0], "u": r[1], "v": r[2], "rc": r[3]}} if r else None

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    col = {{"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}}.get(t)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET {{col}} = {{col}} + ? WHERE user_id = ?", (gain, uid))
    conn.commit(); conn.close()
    return {{"ok": True}}

# --- UI RÉALISTE ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {{ --bg: #000000; --card: #121212; --blue: #007AFF; --green: #34C759; }}
            body {{ background: var(--bg); color: #FFF; font-family: 'Inter', sans-serif; margin: 0; padding: 20px; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }}
            .logo {{ font-size: 20px; font-weight: 800; }}
            .main-balance {{ text-align: center; margin-bottom: 40px; }}
            .main-balance h1 {{ font-size: 48px; margin: 5px 0; font-weight: 800; }}
            .action-card {{ background: var(--card); border-radius: 24px; padding: 20px; margin-bottom: 15px; border: 1px solid #1C1C1E; }}
            .btn-action {{ padding: 12px 20px; border-radius: 12px; border: none; font-weight: 700; cursor: pointer; }}
            .nav {{ position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); background: rgba(28, 28, 30, 0.8); backdrop-filter: blur(20px); border-radius: 30px; display: flex; padding: 10px 30px; gap: 30px; border: 1px solid #38383A; }}
            .nav-item {{ font-size: 22px; cursor: pointer; opacity: 0.5; }}
            .nav-item.active {{ opacity: 1; }}
            .task-item {{ background: var(--card); padding: 15px; border-radius: 18px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
            .task-link {{ background: #2C2C2E; color: #FFF; padding: 8px 15px; border-radius: 8px; font-size: 12px; text-decoration: none; font-weight: 600; }}
        </style>
    </head>
    <body>
        <div id="p-home">
            <div class="header"><div class="logo">OWPC HUB</div></div>
            <div class="main-balance"><span>TOTAL ASSETS</span><h1 id="total-val">0.00</h1></div>
            
            <div class="action-card">
                <div style="display:flex; justify-content:space-between">
                    <div><div style="font-size:12px;color:#8E8E93">Genesis</div><div style="font-size:20px" id="gv">0.00</div></div>
                    <button class="btn-action" style="background:var(--green)" onclick="mine('genesis')">CLAIM</button>
                </div>
            </div>
            <div class="action-card">
                <div style="display:flex; justify-content:space-between">
                    <div><div style="font-size:12px;color:#8E8E93">Unity</div><div style="font-size:20px" id="uv">0.00</div></div>
                    <button class="btn-action" style="background:#FFF" onclick="mine('unity')">SYNC</button>
                </div>
            </div>
            <div class="action-card">
                <div style="display:flex; justify-content:space-between">
                    <div><div style="font-size:12px;color:#8E8E93">Veo AI</div><div style="font-size:20px" id="vv">0.00</div></div>
                    <button class="btn-action" style="background:var(--blue);color:#FFF" onclick="mine('veo')">COMPUTE
