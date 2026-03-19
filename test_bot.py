import os
import sqlite3
import asyncio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- 1. CONFIGURATION ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app" 
BOT_USERNAME = "TonBotUsername" # Remplace par l'ID de ton bot (ex: OWPC_Bot)

app = FastAPI()

# --- 2. BASE DE DONNÉES (EXTENDUE) ---
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

def get_leaderboard():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT name, (points_genesis + points_unity + points_veo) as total FROM users ORDER BY total DESC LIMIT 5")
    res = c.fetchall(); conn.close()
    return res

# --- 3. API POUR LA MINI APP ---
@app.post("/update_points")
async def receive_points(request: Request):
    data = await request.json()
    uid, token, amount = data.get("user_id"), data.get("token"), data.get("amount", 0.05)
    if uid and token:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute(f"UPDATE users SET points_{token} = points_{token} + ? WHERE user_id = ?", (amount, uid))
        conn.commit(); conn.close()
        return {"status": "success", "new_balance": get_stats(uid)}
    return {"status": "error"}

# --- 4. MINI APP INTERFACE ---
@app.get("/", response_class=HTMLResponse)
async def mini_app():
    # (Le code HTML reste le même que la version précédente, il est déjà parfait)
    with open(__file__, 'r') as f: # Juste pour l'exemple, garde ton HTML précédent ici
        pass 
    return """"""

# --- 5. LOGIQUE DU BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    
    # Gestion du parrainage via /start [ID]
    ref_id = int(context.args[0]) if context.args else None
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (user.id, user.first_name, ref_id))
    conn.commit(); conn.close()
    
    s = get_stats(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")]
    ])
    await update.message.reply_text(f"🕊️ **OWPC PROTOCOL**\n\nCommander: `{user.first_name}`\nBalance: `{s['total']:.2f}` OWPC", reply_markup=kb, parse_mode="Markdown")

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); uid = query.from_user.id
    
    if query.data == "main_menu":
        # Retour au menu simplifié
        s = get_stats(uid)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],[InlineKeyboardButton("⬅️ Back", callback_data="main_menu_full")]])
        await query.message.edit_text(f"🕊️ Balance: `{s['total']:.2f}`", reply_markup=kb, parse_mode="Markdown")

    elif query.data == "hof":
        top = get_leaderboard()
        txt = "🏛️ **HALL OF FAME**\n\n" + "\n".join([f"{i+1}. {u[0]} - `{u[1]:.2f}`" for i, u in enumerate(top)])
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")

    elif query.data == "invite":
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        txt = f"🔗 **INVITE FRIENDS**\n\nShare your link to earn 10% of their extraction!\n\n`{link}`"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")

    elif query.data == "lucky":
        # Simulation de gain aléatoire
        win = 0.50 # On pourra ajouter un cooldown de 24h plus tard
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (win, uid))
        conn.commit(); conn.close()
        await query.message.edit_text(f"🎰 **LUCKY DRAW**\n\nYou won `{win}` VEO AI!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]), parse_mode="Markdown")

    # (Garder les autres elif pour stats, passport, invest de la version précédente)

# --- 6. EXECUTION ---
async def main():
    init_db()
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(handle_callbacks))
    await bot_app.initialize(); await bot_app.start()
    asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
