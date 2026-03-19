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
BOT_USERNAME = "OWPCsbot"

app = FastAPI()

# --- 📊 LOGIQUE DE PROGRESSION ---
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
    # Récupérer les infos de l'utilisateur
    c.execute("SELECT points_genesis, points_unity, points_veo, last_bonus, tasks_sub_channel, wallet_address FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    
    # Compter le nombre de filleuls (ceux qui ont referred_by = uid)
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,))
    ref_count = c.fetchone()[0]
    
    conn.close()
    if res:
        total = sum(res[:3])
        return {
            "g": res[0], "u": res[1], "v": res[2], "total": total, 
            "rank": get_rank_info(total), "last_bonus": res[3], 
            "task_sub": res[4], "wallet": res[5], "ref_count": ref_count
        }
    return None

# --- 🤖 BOT LOGIC ---
async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    
    # Gestion de l'invitation à l'inscription
    ref_id = None
    if context.args:
        try:
            potential_ref = int(context.args[0])
            if potential_ref != user.id: ref_id = potential_ref
        except: pass

    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (user.id, user.first_name, ref_id))
    conn.commit(); conn.close()
    
    s = get_stats(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily"), InlineKeyboardButton("🆔 Passport", callback_data="passport")],
        [InlineKeyboardButton("🏛️ Hall of Fame", callback_data="hof"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="lucky")],
        [InlineKeyboardButton("🏆 Tasks Hub", callback_data="tasks"), InlineKeyboardButton("👛 Wallet", callback_data="wallet")],
        [InlineKeyboardButton("📊 My Stats", callback_data="stats"), InlineKeyboardButton("🔗 Invite Friends", callback_data="invite")],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest")]
    ])
    
    text = (
        f"🕊️ **OWPC PROTOCOL**\n\n"
        f"Rank: `{s['rank']['name']}`\n"
        f"Total Balance: `{s['total']:.2f}` OWPC\n"
        f"Network Size: `{s['ref_count']}` friends"
    )
    
    if update.callback_query:
        try:
            await update.callback_query.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
        except:
            await update.callback_query.message.reply_photo(photo=open(LOGO_PATH, 'rb'), caption=text, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_photo(photo=open(LOGO_PATH, 'rb'), caption=text, reply_markup=kb, parse_mode="Markdown")

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id
    s = get_stats(uid)

    if q.data == "back_to_main":
        await start_menu(update, context)

    elif q.data == "stats":
        txt = (
            f"📊 **DETAILED ASSETS**\n\n"
            f"🔹 Genesis: `{s['g']:.2f}`\n"
            f"🔹 Unity: `{s['u']:.2f}`\n"
            f"🔹 Veo AI: `{s['v']:.2f}`\n\n"
            f"👥 **Referrals**: `{s['ref_count']}`\n"
            f"📈 **Power**: `x{s['rank']['mult']}`"
        )
        await q.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]]), parse_mode="Markdown")

    elif q.data == "invite":
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        share_url = f"https://t.me/share/url?url={link}&text=🚀 Join my mining network on OWPC! Extract Genesis, Unity and Veo AI tokens for free! 🕊️"
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share Link", url=share_url)],
            [InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
        ])
        
        txt = (
            f"🔗 **INVITE FRIENDS**\n\n"
            f"Share your link and earn **10%** of everything your friends mine!\n\n"
            f"Current Network: `{s['ref_count']}` active friends\n\n"
            f"Your link:\n`{link}`"
        )
        await q.message.edit_caption(caption=txt, reply_markup=kb, parse_mode="Markdown")

    # (Conserve les autres elif : daily, passport, hof, lucky, tasks, wallet de la V6)
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
        
    # ... (Ajoute les autres blocs s'ils manquent, sinon garde ceux de la V6)

# --- RUN (Identique) ---
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
