import os
import asyncio
import sqlite3
import nest_asyncio
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

nest_asyncio.apply()

# -------- CONFIGURATION --------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 1414016840 
BOT_USERNAME = "OwpcInfoBot"

# -------- LIENS & ASSETS --------
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LINK_CHANNEL = "https://t.me/+SQhKj-gWWmcyODY0"
LINK_X = "https://x.com/DeepTradeX"

# -------- DATABASE --------
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER, last_daily TEXT, 
                  quests_done INTEGER DEFAULT 0, referred_by INTEGER, is_verified INTEGER DEFAULT 0)''')
    try: c.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
    except: pass
    conn.commit(); conn.close()

def update_user(user_id, name, score_inc=0, daily=None, complete_quest=False, referred_by=None, verify=None):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, name, score, last_daily, referred_by, is_verified) VALUES (?, ?, 0, '', ?, 0)", (user_id, name, referred_by))
    if score_inc: c.execute("UPDATE users SET score = score + ?, name = ? WHERE id = ?", (score_inc, name, user_id))
    if daily: c.execute("UPDATE users SET last_daily = ?, name = ? WHERE id = ?", (daily, name, user_id))
    if complete_quest: c.execute("UPDATE users SET quests_done = 1 WHERE id = ?", (user_id,))
    if verify is not None: c.execute("UPDATE users SET is_verified = ? WHERE id = ?", (verify, user_id))
    c.execute("SELECT score, last_daily, quests_done, is_verified FROM users WHERE id = ?", (user_id,))
    res = c.fetchone(); conn.commit(); conn.close()
    return res

init_db()

# -------- FONCTIONS DE RÉPONSE RÉUTILISABLES --------

def get_rank_info(score):
    if score >= 1000: return "👑 ALPHA LEGEND"
    if score >= 500:  return "💎 UNITY GUARDIAN"
    if score >= 100:  return "🛠️ BUILDER"
    return "🐣 SEEKER"

async def stats_function(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(score) FROM users"); s = c.fetchone(); conn.close()
    await update.effective_message.reply_text(f"📊 **OWPC GLOBAL STATS**\n\nCitizens: {s[0]}\nTotal Credits: {s[1]} pts")

async def leaderboard_function(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
    txt = "🏆 **GLOBAL TOP 10**\n\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]} pts" for i, r in enumerate(c.fetchall())])
    conn.close()
    await update.effective_message.reply_text(txt)

async def passport_function(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, name = update.effective_user.id, update.effective_user.first_name
    res = update_user(uid, name); rank = get_rank_info(res[0])
    # On importe ici la fonction de création d'image v5.1 (simplifiée pour l'espace)
    from io import BytesIO
    w, h = 1600, 900
    img = Image.new('RGB', (w, h), (10, 10, 18))
    draw = ImageDraw.Draw(img)
    draw.rectangle([30, 30, 1570, 870], outline=(212, 175, 55), width=8)
    draw.text((100, 300), f"HOLDER: {name.upper()}", fill=(245, 245, 245))
    draw.text((100, 420), f"RANK: {rank}", fill=(212, 175, 55))
    bio = BytesIO(); bio.name = 'passport.png'; img.save(bio, 'PNG'); bio.seek(0)
    await update.effective_message.reply_photo(photo=bio, caption=f"🆔 Passport for {name}")

# -------- HANDLERS --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    kb = [[InlineKeyboardButton("💰 Invest in OWPC", callback_data="invest_hub")],
          [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🆔 My Passport", callback_data="my_card")],
          [InlineKeyboardButton("🚀 Quest Center", callback_data="open_q"), InlineKeyboardButton("📊 Global Stats", callback_data="view_stats")]]
    await update.message.reply_text(f"🕊️ **OWPC Core v5.2**\n\nRank: {get_rank_info(res[0])}", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "view_stats": await stats_function(query, context)
    elif query.data == "view_lb": await leaderboard_function(query, context)
    elif query.data == "my_card": await passport_function(query, context)
    # ... (les autres callback_data : open_q, daily, etc.)

# -------- MAIN --------

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # AJOUT DES COMMANDES MANQUANTES
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_function))
    app.add_handler(CommandHandler("leaderboard", leaderboard_function))
    app.add_handler(CommandHandler("passport", passport_function))
    app.add_handler(CommandHandler("invest", start)) # Redirige vers le menu
    app.add_handler(CommandHandler("invite", lambda u, c: u.message.reply_text(f"🔗 `https://t.me/{BOT_USERNAME}?start=ref_{u.effective_user.id}`")))
    
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🚀 OWPC v5.2 - Command Fix LIVE")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
