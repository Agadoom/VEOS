import os
import asyncio
import sqlite3
import nest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

nest_asyncio.apply()

TOKEN = os.getenv("TOKEN")
PORT = int(os.environ.get("PORT", 8080))
# On utilise l'URL que tu as générée
WEBAPP_URL = f"https://{os.getenv('RAILWAY_STATIC_URL', 'veos-production.up.railway.app')}"

app = FastAPI()

# --- 🎨 L'INTERFACE MINI APP (HTML/CSS) ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <title>OWPC HIVE</title>
        <style>
            :root {{
                --tg-color: var(--tg-theme-button-color, #d4af37);
                --tg-bg: var(--tg-theme-bg-color, #0a0a12);
                --tg-text: var(--tg-theme-text-color, #ffffff);
            }}
            body {{
                background-color: var(--tg-bg);
                color: var(--tg-text);
                margin: 0; padding: 0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                overflow: hidden;
            }}
            .container {{ padding: 20px; text-align: center; }}
            .header {{ margin-bottom: 30px; }}
            .logo {{ width: 100px; height: 100px; border-radius: 50%; border: 3px solid var(--tg-color); margin-bottom: 10px; }}
            .rank {{ font-size: 14px; color: var(--tg-color); letter-spacing: 2px; font-weight: bold; }}
            
            .balance-card {{
                background: rgba(255, 255, 255, 0.05);
                border-radius: 20px; padding: 30px; margin: 20px 0;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
            .balance-label {{ font-size: 12px; opacity: 0.6; text-transform: uppercase; }}
            .balance-amount {{ font-size: 42px; font-weight: bold; margin: 10px 0; }}
            
            .actions {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 20px; }}
            .btn {{
                background: var(--tg-color); color: black;
                border: none; padding: 15px; border-radius: 12px;
                font-weight: bold; font-size: 14px; cursor: pointer;
            }}
            
            .nav-bar {{
                position: fixed; bottom: 0; width: 100%;
                display: flex; justify-content: space-around;
                background: rgba(0,0,0,0.3); padding: 15px 0;
                border-top: 1px solid rgba(255,255,255,0.1);
            }}
            .nav-item {{ opacity: 0.5; font-size: 12px; }}
            .nav-item.active {{ opacity: 1; color: var(--tg-color); }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="https://api.dicebear.com/7.x/identicon/svg?seed=OWPC" class="logo">
                <div class="rank">👑 OVERLORD</div>
            </div>

            <div class="balance-card">
                <div class="balance-label">Total Credits</div>
                <div class="balance-amount">12,450</div>
                <div style="color: #4cd137; font-size: 14px;">+12.5% this week</div>
            </div>

            <div class="actions">
                <button class="btn" onclick="tg.showAlert('Staking Unity Active!')">STAKE</button>
                <button class="btn" style="background: white;" onclick="tg.showAlert('Quests coming soon')">QUESTS</button>
            </div>
        </div>

        <div class="nav-bar">
            <div class="nav-item active">🏠<br>Home</div>
            <div class="nav-item">💎<br>Staking</div>
            <div class="nav-item">👥<br>Friends</div>
            <div class="nav-item">⚙️<br>Settings</div>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand(); // Ouvre la Mini App en plein écran
            tg.MainButton.setText("INVITE FRIENDS").show();
        </script>
    </body>
    </html>
    """

# --- 🤖 PARTIE BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Launch OWPC App", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📢 Channel", url="https://t.me/owpc_co")]
    ])
    await update.message.reply_text(
        "Welcome to the **OWPC Phase 2 Experience**.\n\nYour digital asset management is now visual. Tap the button below to start.",
        reply_markup=kb, parse_mode="Markdown"
    )

async def run_bot():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    async with bot_app:
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        while True: await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
