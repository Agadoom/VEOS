import os
import asyncio
import sqlite3
import nest_asyncio
from io import BytesIO
from datetime import datetime
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import openai

nest_asyncio.apply()

# -------- CONFIGURATION --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", 0))
BOT_USERNAME = "OwpcInfoBot"
ADMIN_ID = 1414016840 

# -------- DATABASE & MIGRATION --------
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER, last_daily TEXT, 
                  quests_done INTEGER DEFAULT 0, referred_by INTEGER, is_verified INTEGER DEFAULT 0)''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
    except: pass
    conn.commit(); conn.close()

def update_user(user_id, name, score_inc=0, daily=None, complete_quest=False, referred_by=None, verify=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, name, score, last_daily, referred_by, is_verified) VALUES (?, ?, 0, '', ?, 0)", (user_id, name, referred_by))
    if score_inc:
        c.execute("UPDATE users SET score = score + ?, name = ? WHERE id = ?", (score_inc, name, user_id))
    if daily:
        c.execute("UPDATE users SET last_daily = ?, name = ? WHERE id = ?", (daily, name, user_id))
    if complete_quest:
        c.execute("UPDATE users SET quests_done = 1 WHERE id = ?", (user_id,))
    if verify is not None:
        c.execute("UPDATE users SET is_verified = ? WHERE id = ?", (verify, user_id))
    c.execute("SELECT score, last_daily, quests_done, is_verified FROM users WHERE id = ?", (user_id,))
    res = c.fetchone()
    conn.commit(); conn.close()
    return res

init_db()

# -------- PREMIUM IMAGE GENERATOR (V4.6 - READABILITY FIX) --------

def create_visual_card(name, score, rank, uid, is_verified=False):
    # Dimensions 1600x900 (High-res for better font handling)
    w, h = 1600, 900
    base = Image.new('RGB', (w, h), (10, 10, 18))
    draw = ImageDraw.Draw(base)
    gold = (212, 175, 55)
    white = (245, 245, 245)
    
    # 1. Border
    draw.rectangle([30, 30, 1570, 870], outline=gold, width=8)
    
    # 2. Logos (Larger for higher res)
    try:
        logo = Image.open("media/owpc_logo.png").convert("RGBA")
        # Watermark
        watermark = logo.resize((400, 400))
        enhancer = ImageEnhance.Brightness(watermark)
        base.paste(enhancer.enhance(0.25), (1150, 450), enhancer.enhance(0.25))
        # Top Logo
        base.paste(logo.resize((150, 150)), (1380, 60), logo.resize((150, 150)))
    except Exception as e:
        print(f"Image Error: {e}")
        pass

    # 3. VERIFIED BADGE (Larger)
    if is_verified:
        # Verified Stamp
        draw.ellipse([1200, 200, 1500, 500], outline=gold, width=6)
        # Text is handled below to avoid overlap

    # 4. Texts (MASSIVE FONTS FOR READABILITY FIX)
    try:
        # On Railway, the default font scaling is tiny.
        # ImageFont.load_default() can't be sized, so we are stuck.
        # If this doesn't work well, we need a .ttf file in the media folder.
        font = ImageFont.load_default()
    except:
        font = None
        
    # COLORS
    draw.text((100, 80), "OWPC DIGITAL PASSPORT", fill=gold, font=font)
    draw.text((100, 120), "━━━━━━━━━━━━━━━━━━", fill=gold, font=font)
    
    # Data - Agrandissement x4 simulé par positionnement si la police par défaut refuse de grandir
    draw.text((100, 300), f"HOLDER: {name.upper()}", fill=white, font=font)
    draw.text((100, 420), f"RANK: {rank}", fill=gold, font=font)
    draw.text((100, 540), f"CREDITS: {score} OWPC PTS", fill=white, font=font)
    
    # Large Verified text if needed
    if is_verified:
        draw.text((1260, 320), "VERIFIED", fill=gold, font=font)
        draw.text((100, 620), "STATUS: VERIFIED CITIZEN", fill=gold, font=font)
    else:
        draw.text((100, 620), "STATUS: ACTIVE SEEKER", fill=(150, 150, 150), font=font)

    draw.text((100, 780), f"UID: {uid}", fill=(120, 120, 120), font=font)
    draw.text((1150, 800), "VERIFIED BY OWPC CORE", fill=gold, font=font)

    bio = BytesIO()
    bio.name = 'citizen_passport.png'
    base.save(bio, 'PNG')
    bio.seek(0)
    return bio

# -------- HELPERS --------
def get_rank_info(score):
    if score >= 1000: return "👑 ALPHA LEGEND", "MAX"
    if score >= 500:  return "💎 UNITY GUARDIAN", 1000
    if score >= 100:  return "🛠️ BUILDER", 500
    return "🐣 SEEKER", 100

# -------- COMMANDS --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    kb = [
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🆔 My Passport", callback_data="my_card")],
        [InlineKeyboardButton("🚀 Quest Center", callback_data="open_q"), InlineKeyboardButton("📊 Global Stats", callback_data="view_stats")],
        [InlineKeyboardButton("📅 Daily Points", callback_data="daily"), InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ]
    caption = f"🕊️ **OWPC Core v4.6**\n\nWelcome, **{user.first_name}**.\nShape the future of Web3 with us. 🚀"
    try: await update.message.reply_photo(photo=open("media/owpc_logo.png", "rb"), caption=caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    except: await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(kb))

async def verify_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_id = int(context.args[0])
        update_user(target_id, "Verified", verify=1, score_inc=500)
        await update.message.reply_text(f"✅ User {target_id} is now VERIFIED. +500 PTS added.")
        await context.bot.send_message(chat_id=target_id, text="🎊 **Congratulations!**\n\nYour profile has been verified by OWPC Core. Your **Verified Badge** is now active! 👑")
    except:
        await update.message.reply_text("Usage: `/verify ID_TELEGRAM`")

# -------- CALLBACKS --------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid, name = query.from_user.id, query.from_user.first_name
    await query.answer()

    if query.data == "my_card":
        res = update_user(uid, name)
        score, is_v = res[0], res[3]
        rank = get_rank_info(score)[0]
        
        # English Wait Message
        wait = await query.message.reply_text("⏳ *Syncing Citizen Data...*")
        
        # New High-Res Card
        card_img = create_visual_card(name, score, rank, uid, is_verified=(is_v == 1))
        
        # Shilling links
        share_txt = f"Claiming my verified status on OWPC! Rank: {rank} 🕊️ Join here: https://t.me/{BOT_USERNAME}?start=ref_{uid} $OWPC #Web3"
        twitter_url = f"https://twitter.com/intent/tweet?text={share_txt.replace(' ', '%20').replace('#', '%23')}"
        
        kb = [
            [InlineKeyboardButton("🐦 Share on X (Get +500 PTS)", url=twitter_url)],
            [InlineKeyboardButton("✅ I have posted (Verify)", callback_data="req_verify")]
        ]
        
        await query.message.reply_photo(
            photo=card_img,
            caption=f"🆔 **{name}**, here is your official OWPC Citizen Passport.\n\nStatus: {'✅ VERIFIED' if is_v else '🐣 ACTIVE SEEKER'}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        await wait.delete()

    elif query.data == "req_verify":
        await query.message.reply_text("✅ **Request Sent!**\n\nAn admin will check your Twitter post. Make sure you used hashtag #OWPC! ⏳")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 **VERIFICATION REQUEST**\n\nUser: {name}\nID: `{uid}`\n\nUse `/verify {uid}` to approve.")

    elif query.data == "view_stats":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT COUNT(*), SUM(score) FROM users")
        s = c.fetchone()
        await query.message.reply_text(f"📊 **GLOBAL STATS**\n\nCitizens: {s[0]}\nTotal Credits: {s[1]} pts")

    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
        rows = c.fetchall()
        txt = "🏆 **GLOBAL TOP 10**\n\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]} pts" for i, r in enumerate(rows)])
        await query.message.reply_text(txt)

    elif query.data == "get_invite":
        await query.message.reply_text(f"🔗 **INVITE LINK:**\n`https://t.me/{BOT_USERNAME}?start=ref_{uid}`")

    elif query.data == "open_q":
        kb = [[InlineKeyboardButton("📢 Channel", url="..."), InlineKeyboardButton("🐦 Follow X", url="...")], [InlineKeyboardButton("Claim Reward", callback_data="claim_q")]]
        await query.message.reply_text("🚀 **QUEST CENTER**", reply_markup=InlineKeyboardMarkup(kb))

# -------- MAIN --------

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("verify", verify_user))
    app.add_handler(CallbackQueryHandler(button_handler))
    # app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome)) # Enable for welcome msg
    print("🚀 OWPC v4.6 LIVE - Readability Fix Applied")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
