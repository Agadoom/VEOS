import os
import asyncio
import sqlite3
import nest_asyncio
from io import BytesIO
from datetime import datetime
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont # <--- Nouvelle librairie pour l'image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import openai

nest_asyncio.apply()

# -------- CONFIGURATION --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", 0))
BOT_USERNAME = "OWPCinfobot" 
ADMIN_ID = 1414016840 

# -------- DATABASE --------
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER, last_daily TEXT, quests_done INTEGER DEFAULT 0, referred_by INTEGER)''')
    conn.commit()
    conn.close()

def update_user(user_id, name, score_inc=0, daily=None, complete_quest=False, referred_by=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, name, score, last_daily, referred_by) VALUES (?, ?, 0, '', ?)", (user_id, name, referred_by))
    if score_inc:
        c.execute("UPDATE users SET score = score + ?, name = ? WHERE id = ?", (score_inc, name, user_id))
    if daily:
        c.execute("UPDATE users SET last_daily = ?, name = ? WHERE id = ?", (daily, name, user_id))
    if complete_quest:
        c.execute("UPDATE users SET quests_done = 1 WHERE id = ?", (user_id,))
    c.execute("SELECT score, last_daily, quests_done FROM users WHERE id = ?", (user_id,))
    res = c.fetchone()
    conn.commit(); conn.close()
    return res

init_db()

# -------- LOGIQUE IMAGE (V4.3) --------

def create_visual_card(name, score, rank, uid):
    # Création du fond (800x450 - format carte de crédit)
    width, height = 800, 450
    # Fond dégradé sombre (Bleu nuit vers Noir)
    base = Image.new('RGB', (width, height), (10, 10, 15))
    draw = ImageDraw.Draw(base)
    
    # Bordure Or stylisée
    draw.rectangle([15, 15, 785, 435], outline=(212, 175, 55), width=3)
    
    # Ajout du logo en petit sur le côté si présent
    try:
        logo = Image.open("media/owpc_logo.png").convert("RGBA")
        logo = logo.resize((100, 100))
        base.paste(logo, (650, 40), logo)
    except: pass

    # Éléments de texte (Utilisation de la police par défaut)
    draw.text((50, 40), "OWPC ECOSYSTEM", fill=(212, 175, 55))
    draw.text((50, 60), "━━━━━━━━━━━━━━━━━━", fill=(212, 175, 55))
    
    draw.text((50, 150), f"HOLDER: {name.upper()}", fill=(255, 255, 255))
    draw.text((50, 210), f"RANK: {rank}", fill=(212, 175, 55))
    draw.text((50, 270), f"CREDITS: {score} OWPC PTS", fill=(255, 255, 255))
    draw.text((50, 380), f"UID: {uid}", fill=(100, 100, 100))
    draw.text((550, 380), "OFFICIAL PASSPORT v1.0", fill=(212, 175, 55))

    # Préparation pour Telegram
    bio = BytesIO()
    bio.name = 'passport.png'
    base.save(bio, 'PNG')
    bio.seek(0)
    return bio

# -------- TOOLS --------
LOGO_PATH = "media/owpc_logo.png"

def get_rank_info(score):
    if score >= 1000: return "👑 Alpha Legend", "MAX"
    if score >= 500:  return "💎 Unity Guardian", 1000
    if score >= 100:  return "🛠️ Builder", 500
    return "🐣 Seeker", 100

# -------- HANDLERS --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    score_res = update_user(user.id, user.first_name)
    kb = [
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🆔 My Passport", callback_data="my_card")],
        [InlineKeyboardButton("🚀 Quest Center", callback_data="open_q"), InlineKeyboardButton("📊 Global Stats", callback_data="view_stats")],
        [InlineKeyboardButton("📅 Daily", callback_data="daily"), InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ]
    caption = f"🕊️ **OWPC Core v4.3**\n\nRank: {get_rank_info(score_res[0])[0]}\n\nAccédez à votre Passeport Digital visuel ci-dessous. 🚀"
    try:
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    except:
        await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid, name = query.from_user.id, query.from_user.first_name
    await query.answer()

    if query.data == "my_card":
        score = update_user(uid, name)[0]
        rank = get_rank_info(score)[0]
        
        # Petit message d'attente car l'image prend 0.5s à se créer
        wait_msg = await query.message.reply_text("💠 *Génération de votre Passeport Quantique...*", parse_mode="Markdown")
        
        # Génération de l'image
        card_img = create_visual_card(name, score, rank, uid)
        
        # Share Link
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start=ref_{uid}&text=Regarde%20mon%20rang%20sur%20OWPC!%20[{rank}]"
        kb = [[InlineKeyboardButton("📣 Share my Status", url=share_url)]]
        
        await query.message.reply_photo(
            photo=card_img,
            caption=f"🆔 **{name}**, voici votre passeport officiel.\n\nCe document prouve votre engagement dans l'écosystème OWPC. 🕊️",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        await wait_msg.delete()

    elif query.data == "view_stats":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT COUNT(*), SUM(score) FROM users")
        stats = c.fetchone()
        await query.message.reply_text(f"📊 **STATS GLOBAL**\n\nMembres: {stats[0]}\nPoints: {stats[1]}")

    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
        rows = c.fetchall()
        txt = "🏆 **TOP 10**\n\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]} pts" for i, r in enumerate(rows)])
        await query.message.reply_text(txt)

    elif query.data == "get_invite":
        await query.message.reply_text(f"🔗 `https://t.me/{BOT_USERNAME}?start=ref_{uid}`")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 OWPC v4.3 - Visual Passport Ready")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
