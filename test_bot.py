import os, sqlite3, asyncio, uvicorn, logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters

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

# --- BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    if context.args and context.args[0] == "donate":
        await update.message.reply_invoice(
            title="🚀 VEO BOOST", description="Add +10.00 VEO to your account!",
            payload="boost_veo", provider_token="", currency="XTR", prices=[LabeledPrice("Payer", 50)]
        )
        return
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    conn.commit(); conn.close()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 OPEN OWPC HUB", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await update.message.reply_text(f"Welcome to the Hub, {name}.", reply_markup=kb)

async def success_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE users SET p_veo = p_veo + 10.0 WHERE user_id = ?", (uid,))
    conn.commit(); conn.close()
    await update.message.reply_text("✅ Payment Successful! +10.00 VEO added to your account.")

# --- API ---
@app.get("/api/user/{uid}")
async def get_user(uid: int):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT p_genesis, p_unity, p_veo, ref_count FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return {"g": r[0], "u": r[1], "v": r[2], "rc": r[3]} if r else None

@app.post("/api/mine")
async def mine_api(request: Request):
    data = await request.json()
    uid, t = data.get("user_id"), data.get("token")
    gain = 0.01 if t == 'veo' else 0.05
    col = {"genesis":"p_genesis", "unity":"p_unity", "veo":"p_veo"}.get(t)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(f"UPDATE users SET {col} = {col} + ? WHERE user_id = ?", (gain, uid))
    conn.commit(); conn.close()
    return {"ok": True}

# --- UI (Correction de la chaîne de caractères) ---
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {{ --bg: #000; --card: #111; --blue: #007AFF; --green: #34C759; }}
            body {{ background: var(--bg); color: #FFF; font-family: sans-serif; margin: 0; padding: 20px; }}
            .header {{ font-weight: 800; font-size: 20px; margin-bottom: 20px; color: var(--blue); }}
            .balance {{ text-align: center; margin-bottom: 30px; border: 1px solid #222; padding: 20px; border-radius: 20px; }}
            .card {{ background: var(--card); padding: 15px; border-radius: 15px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #222; }}
            .btn {{ background: #FFF; color: #000; border: none; padding: 10px 15px; border-radius: 10px; font-weight: bold; }}
            .nav {{ position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: #111; padding: 10px 20px; border-radius: 25px; display: flex; gap: 20px; border: 1px solid #333; }}
            .task-link {{ text-decoration: none; background: #222; color: gold; padding: 8px 12px; border-radius: 8px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div id="h">
            <div class="header">OWPC HUB</div>
            <div class="balance"><span>TOTAL ASSETS</span><h1 id="tot">0.00</h1></div>
            <div class="card"><div>Genesis<br><b id="gv">0.00</b></div><button class="btn" style="background:var(--green)" onclick="mine('genesis')">CLAIM</button></div>
            <div class="card"><div>Unity<br><b id="uv">0.00</b></div><button class="btn" onclick="mine('unity')">SYNC</button></div>
            <div class="card"><div>Veo AI<br><b id="vv">0.00</b></div><button class="btn" style="background:var(--blue);color:#FFF" onclick="
