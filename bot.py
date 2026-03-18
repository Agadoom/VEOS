import os
import asyncio
import sqlite3
import random
import nest_asyncio
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

nest_asyncio.apply()

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 1414016840 
BOT_USERNAME = "OwpcInfoBot"
LOGO_PATH = "media/owpc_logo.png"
CHANNEL_ID = "@owpc_co" 

# --- LINKS ---
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LINK_CHANNEL = "https://t.me/owpc_co"

# --- DB & LOGIC ---
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def get_rank_info(score):
    if score >= 15000: return "👑 OVERLORD", (255, 215, 0)
    if score >= 5000:  return "💎 ELITE", (0, 191, 255)
    if score >= 1500:  return "⚔️ COMMANDER", (220, 20, 60)
    if score >= 500:   return "🛡️ GUARDIAN", (50, 205, 50)
    return "🆕 SEEKER", (200, 200, 200)

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0, last_daily TEXT DEFAULT '', 
                  quests_done INTEGER DEFAULT 0, referred_by INTEGER DEFAULT 0, is_verified INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('live_feed', 'Welcome to the OWPC Hive! 🚀')")
    conn.commit(); conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT score, last_daily, quests_done, is_verified, referred_by FROM users WHERE id = ?", (user_id,))
    res = c.fetchone(); conn.close(); return res

def update_user(user_id, name, score_inc=0, daily=None, ref_by=0):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (id, name, score, referred_by) VALUES (?, ?, ?, ?)", (user_id, name, 50 if ref_by else 0, ref_by))
        if ref_by: c.execute("UPDATE users SET score = score + 100 WHERE id = ?", (ref_by,))
    if score_inc: c.execute("UPDATE users SET score = score + ? WHERE id = ?", (score_inc, user_id))
    if daily: c.execute("UPDATE users SET last_daily = ? WHERE id = ?", (daily, user_id))
    conn.commit(); conn.close()
    return get_user_data(user_id)

# --- BROADCAST COMMAND (The Admin Power) ---
async def set_feed_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    msg_text = " ".join(context.args)
    if not msg_text:
        await update.message.reply_text("Usage: `/setfeed Your News Here`")
        return

    # Update DB for the Live Feed Button
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE settings SET value = ? WHERE key = 'live_feed'", (msg_text,))
    c.execute("SELECT id FROM users"); all_users = c.fetchall(); conn.commit(); conn.close()

    await update.message.reply_text(f"📡 Updating Feed and Broadcasting to {len(all_users)} users...")

    success = 0
    for user in all_users:
        try:
            await context.bot.send_message(chat_id=user[0], text=f"🔔 **OWPC UPDATE**\n\n{msg_text}", parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.05) # Prevent flood
        except: pass

    await update.message.reply_text(f"✅ Done! {success} members notified.")

# --- KEYBOARDS & HANDLERS (Simplified English) ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb")],
        [InlineKeyboardButton("📡 Live Feed", callback_data="live_feed"), InlineKeyboardButton("💎 Staking Sim", callback_data="staking_sim")],
        [InlineKeyboardButton("🆔 My Passport", callback_data="my_card"), InlineKeyboardButton("🚀 Quests", callback_data="open_q")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ])

def back_btn(): return [InlineKeyboardButton("⬅️ Back", callback_data="back_home")]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name, ref_by=int(context.args[0].replace("ref_","")) if context.args and context.args[0].startswith("ref_") else 0)
    await update.effective_message.reply_text(f"🕊️ **Welcome, {user.first_name}!**\nCredits: {res[0]} PTS", reply_markup=main_menu_kb(), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name
    res = get_user_data(uid)

    if query.data == "back_home":
        await query.message.edit_text(f"🕊️ **Main Menu**\nPoints: {res[0]}", reply_markup=main_menu_kb(), parse_mode="Markdown")

    elif query.data == "live_feed":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT value FROM settings WHERE key = 'live_feed'"); feed = c.fetchone()[0]; conn.close()
        await query.message.edit_text(f"📡 **LIVE FEED**\n\n{feed}", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "staking_sim":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Simulate 10k $OWPC", callback_data="sim_10k")], back_btn()])
        await query.message.edit_text("💎 **STAKING SIMULATOR**\nGet your monthly estimates:", reply_markup=kb)

    elif query.data == "sim_10k":
        await query.message.edit_text("📊 **ESTIMATES (10k tokens)**\n\nUnity: 208/mo\nGenesis: 100/mo", reply_markup=InlineKeyboardMarkup([back_btn()]))

    # ... [Keep other buttons: my_card, stats, daily, etc. from v6.9.2]

async def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setfeed", set_feed_cmd)) # ADMIN ONLY
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 OWPC v6.9.4 BROADCAST READY")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
