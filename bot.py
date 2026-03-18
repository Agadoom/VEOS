import os
import asyncio
import sqlite3
import random
import nest_asyncio
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

nest_asyncio.apply()

# --- CONFIG ---
TOKEN = os.getenv("TOKEN") # Ton Token de bot communautaire
ADMIN_ID = 1414016840 
BOT_USERNAME = "OwpcInfoBot"
LOGO_PATH = "media/owpc_logo.png"
CHANNEL_ID = "@owpc_co" 
# URL de ta Mini App déployée sur Railway
WEBAPP_URL = "https://veos-production.up.railway.app" 

# --- DB PATH (Harmonisé avec test_bot.py) ---
DB_PATH = "owpc_data.db" 

def get_rank_info(score):
    if score >= 15000: return "👑 OVERLORD", (212, 175, 55)
    if score >= 5000:  return "💎 ELITE", (0, 191, 255)
    if score >= 1500:  return "⚔️ COMMANDER", (220, 20, 60)
    if score >= 500:   return "🛡️ GUARDIAN", (50, 205, 50)
    return "🆕 SEEKER", (200, 200, 200)

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # On s'assure que la table 'users' a les colonnes nécessaires pour les deux bots
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0, 
                  rank TEXT DEFAULT 'NEWBIE', last_checkin TEXT DEFAULT '')''')
    conn.commit(); conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # On utilise 'points' et 'user_id' pour matcher avec test_bot.py
    c.execute("SELECT points, last_checkin, rank FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close(); return res

def update_user_points(user_id, name, amount):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name, points, rank) VALUES (?, ?, ?, ?)", (user_id, name, amount, "NEWBIE"))
    else:
        c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
    conn.commit(); conn.close()

def create_visual_card(name, score, uid):
    w, h = 1200, 700
    base = Image.new('RGB', (w, h), (10, 10, 18))
    draw = ImageDraw.Draw(base); gold = (212, 175, 55)
    rank_name, rank_color = get_rank_info(score)
    draw.rectangle([20, 20, 1180, 680], outline=rank_color, width=10)
    draw.text((60, 60), "ONE WORLD PEACE COINS", fill=gold)
    draw.text((60, 150), f"DIGITAL PASSPORT", fill=(200,200,200))
    draw.text((60, 280), f"RANK: {rank_name}", fill=rank_color)
    draw.text((60, 400), f"HOLDER: {name.upper()}", fill=(255, 255, 255))
    draw.text((60, 520), f"CREDITS: {score:,} OWPC", fill=(255, 255, 255))
    bio = BytesIO(); bio.name = 'passport.png'; base.save(bio, 'PNG'); bio.seek(0)
    return bio

# --- KEYBOARDS ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Launch HIVE App", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("🆔 My Passport", callback_data="my_card"), InlineKeyboardButton("📊 Stats", callback_data="view_stats")],
        [InlineKeyboardButton("🏛️ Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🗺️ Roadmap", callback_data="view_roadmap")]
    ])

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Initialisation silencieuse
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()
    
    res = get_user_data(user.id)
    score = res[0] if res else 0
    cap = f"🕊️ **Welcome to OWPC HIVE**\n\nCommander: {user.first_name}\nCredits: {score:,} OWPC\n\nUse the button below to enter the terminal."
    await update.effective_message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name
    res = get_user_data(uid)
    score = res[0] if res else 0

    if query.data == "my_card":
        await query.message.reply_photo(photo=create_visual_card(name, score, uid), caption=f"🆔 Passport updated for {name}")

    elif query.data == "view_stats":
        await query.message.reply_text(f"📊 **YOUR HIVE STATS**\n\nScore: {score:,} OWPC\nRank: {get_rank_info(score)[0]}", parse_mode="Markdown")

    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, points FROM users ORDER BY points DESC LIMIT 5")
        top = c.fetchall(); conn.close()
        txt = "🏛️ **HALL OF FAME**\n\n" + "\n".join([f"👑 {u[0]} — {u[1]:,} PTS" for u in top])
        await query.message.reply_text(txt, parse_mode="Markdown")

    elif query.data == "view_roadmap":
        txt = "🗺️ **ROADMAP**\nPhase 1: Genesis\nPhase 2: Unity (LIVE)\nPhase 3: VEO AI"
        await query.message.reply_text(txt)

async def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Community Bot Online...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
