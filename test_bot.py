import os
import sqlite3
import asyncio
import uvicorn
import random
from datetime import datetime, date
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- ⚙️ CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = "https://veos-production.up.railway.app" 
LOGO_PATH = "media/owpc_logo.png"

app = FastAPI()

# --- 📊 LOGIQUE ---
def get_rank_info(total_points):
    if total_points < 25: return {"name": "🆕 NOVICE", "mult": 1.0, "next": 25, "color": "#888888"}
    elif total_points < 100: return {"name": "🛠️ SPECIALIST", "mult": 2.0, "next": 100, "color": "#50ff50"}
    elif total_points < 500: return {"name": "⚡ EXTRACTOR", "mult": 5.0, "next": 500, "color": "#3399ff"}
    else: return {"name": "🐋 WHALE", "mult": 10.0, "next": 999999, "color": "#ffcc00"}

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, points_unity REAL DEFAULT 0.0, 
                  points_veo REAL DEFAULT 0.0, referred_by INTEGER,
                  last_bonus TEXT DEFAULT '', tasks_sub_channel INTEGER DEFAULT 0,
                  wallet_address TEXT DEFAULT '')''')
    conn.commit(); conn.close()

def get_stats(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, last_bonus, tasks_sub_channel, wallet_address FROM users WHERE user_id=?", (uid,))
    res = c.fetchone(); conn.close()
    if res:
        total = sum(res[:3])
        return {"g": res[0], "u": res[1], "v": res[2], "total": total, "rank": get_rank_info(total), "last_bonus": res[3], "task_sub": res[4], "wallet": res[5]}
    return None

# --- 🤖 BOT LOGIC ---
async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    
    # Inscription
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()
    
    s = get_stats(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily"), InlineKeyboardButton("🆔 Passport", callback_data="passport")],
        [InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof"), InlineKeyboardButton("🎰 Lucky", callback_data="lucky")],
        [InlineKeyboardButton("🏆 Tasks Hub", callback_data="tasks"), InlineKeyboardButton("👛 Wallet", callback_data="wallet")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite", callback_data="invite")],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest")]
    ])
    
    text = f"🕊️ **OWPC PROTOCOL**\n\nRank: `{s['rank']['name']}`\nBalance: `{s['total']:.2f}` OWPC"
    
    # Correction : On utilise reply_photo pour le message initial et edit_media pour les retours
    if update.callback_query:
        try:
            await update.callback_query.message.edit_media(
                media=InputMediaPhoto(media=open(LOGO_PATH, 'rb'), caption=text, parse_mode="Markdown"),
                reply_markup=kb
            )
        except:
            await update.callback_query.message.reply_photo(photo=open(LOGO_PATH, 'rb'), caption=text, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_photo(photo=open(LOGO_PATH, 'rb'), caption=text, reply_markup=kb, parse_mode="Markdown")

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id
    s = get_stats(uid)

    if q.data == "back_to_main":
        await start_menu(update, context)

    elif q.data == "wallet":
        status = f"`{s['wallet']}`" if s['wallet'] else "Not connected"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Connect TON Wallet", url="https://tonkeeper.com/")], # Exemple
            [InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
        ])
        await q.message.edit_media(media=InputMediaPhoto(media=open(LOGO_PATH, 'rb'), caption=f"👛 **WALLET SETTINGS**\n\nAddress: {status}\n\n*Withdrawals will be available after the TGE.*", parse_mode="Markdown"), reply_markup=kb)

    elif q.data == "tasks":
        status = "✅" if s['task_sub'] else "⏳"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Sub to @owpc_co {status}", callback_data="check_sub")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
        ])
        await q.message.edit_media(media=InputMediaPhoto(media=open(LOGO_PATH, 'rb'), caption="🏆 **TASKS HUB**\nComplete missions to earn Genesis coins.", parse_mode="Markdown"), reply_markup=kb)

    elif q.data == "check_sub":
        if not s['task_sub']:
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE users SET points_genesis = points_genesis + 50, tasks_sub_channel = 1 WHERE user_id = ?", (uid,))
            conn.commit(); conn.close()
            await q.answer("✅ 50 OWPC Added!", show_alert=True)
        await start_menu(update, context)

    elif q.data == "daily":
        today = date.today().isoformat()
        if s['last_bonus'] == today:
            await q.answer("❌ Already claimed today", show_alert=True)
        else:
            bonus = 1.0 * s['rank']['mult']
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE users SET points_genesis = points_genesis + ?, last_bonus = ? WHERE user_id = ?", (bonus, today, uid))
            conn.commit(); conn.close()
            await q.answer(f"🎁 Bonus +{bonus} claimed!", show_alert=True)
        await start_menu(update, context)

    elif q.data == "stats":
        txt = f"📊 **ASSETS**\nGen: `{s['g']:.2f}`\nUni: `{s['u']:.2f}`\nVeo: `{s['v']:.2f}`"
        await q.message.edit_media(media=InputMediaPhoto(media=open(LOGO_PATH, 'rb'), caption=txt, parse_mode="Markdown"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]]))

    elif q.data == "passport":
        txt = f"🆔 **PASSPORT**\nRank: {s['rank']['name']}\nPower: x{s['rank']['mult']}"
        await q.message.edit_media(media=InputMediaPhoto(media=open(LOGO_PATH, 'rb'), caption=txt, parse_mode="Markdown"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]]))

    elif q.data == "hof":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, (points_genesis+points_unity+points_veo) as t FROM users ORDER BY t DESC LIMIT 5")
        top = c.fetchall(); conn.close()
        txt = "🏛️ **TOP PLAYERS**\n\n" + "\n".join([f"{i+1}. {u[0]} - {u[1]:.2f}" for i,u in enumerate(top)])
        await q.message.edit_media(media=InputMediaPhoto(media=open(LOGO_PATH, 'rb'), caption=txt, parse_mode="Markdown"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]]))

    elif q.data == "lucky":
        win = round(random.uniform(0.1, 0.4), 2)
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (win, uid))
        conn.commit(); conn.close()
        await q.answer(f"🎰 Win: +{win}!", show_alert=True)
        await start_menu(update, context)

    elif q.data == "invite":
        txt = f"🔗 **INVITE**\n\n`https://t.me/{BOT_USERNAME}?start={uid}`"
        await q.message.edit_media(media=InputMediaPhoto(media=open(LOGO_PATH, 'rb'), caption=txt, parse_mode="Markdown"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]]))

    elif q.data == "invest":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 Genesis", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 Unity", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 Veo AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
        ])
        await q.message.edit_media(media=InputMediaPhoto(media=open(LOGO_PATH, 'rb'), caption="💰 **INVEST**", parse_mode="Markdown"), reply_markup=kb)

# --- WEB APP PART (STAYS SAME) ---
@app.post("/update_points")
async def receive_points(request: Request):
    data = await request.json(); uid, token = data.get("user_id"), data.get("token")
    if uid and token:
        s = get_stats(uid); gain = 0.05 * s['rank']['mult']
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute(f"UPDATE users SET points_{token} = points_{token} + ? WHERE user_id = ?", (gain, uid))
        conn.commit(); conn.close()
        return {"status": "success", "new_balance": get_stats(uid)}

@app.get("/", response_class=HTMLResponse)
async def mini_app():
    return """<html><body style="background:#000; color:#0f0; text-align:center; font-family:monospace;"><h3>TERMINAL</h3><button style="width:150px; height:150px; border-radius:50%; background:#0f0;" onclick="mine()">EXTRACT</button><script>let tg=window.Telegram.WebApp; async function mine(){ let uid=tg.initDataUnsafe.user.id; await fetch('/update_points',{method:'POST',body:JSON.stringify({user_id:uid,token:'genesis'})}); alert('Extracted!'); }</script></body></html>"""

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
