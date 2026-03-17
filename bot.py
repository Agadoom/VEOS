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
    # Create table with is_verified column
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER, last_daily TEXT, 
                  quests_done INTEGER DEFAULT 0, referred_by INTEGER, is_verified INTEGER DEFAULT 0)''')
    
    # Migration: Add is_verified if it doesn't exist (safety)
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

# -------- PREMIUM IMAGE GENERATOR (V4.5) --------

def create_visual_card(name, score, rank, uid, is_verified=False):
    w, h = 800, 450
    base = Image.new('RGB', (w, h), (5, 5, 10))
    draw = ImageDraw.Draw(base)
    gold = (212, 175, 55)
    white = (245, 245, 245)
    
    # 1. Border
    draw.rectangle([15, 15, 785, 435], outline=gold, width=4)
    
    # 2. Logos
    try:
        logo = Image.open("media/owpc_logo.png").convert("RGBA")
        # Watermark
        watermark = logo.resize((180, 180))
        enhancer = ImageEnhance.Brightness(watermark)
        base.paste(enhancer.enhance(0.3), (580, 240), enhancer.enhance(0.3))
        # Top Logo
        base.paste(logo.resize((70, 70)), (690, 30), logo.resize((70, 70)))
    except: pass

    # 3. Texts (English Only)
    draw.text((50, 40), "OWPC DIGITAL PASSPORT", fill=gold)
    draw.text((50, 150), f"HOLDER: {name.upper()}", fill=white)
    draw.text((50, 210), f"RANK: {rank}", fill=gold)
    draw.text((50, 270), f"CREDITS: {score} OWPC PTS", fill=white)
    
    # 4. VERIFIED BADGE
    if is_verified:
        draw.ellipse([600, 100, 740, 240], outline=gold, width=3)
        draw.text((630, 160), "VERIFIED", fill=gold)
        draw.text((50, 310), "STATUS: VERIFIED CITIZEN", fill=gold)
    else:
        draw.text((50, 310), "STATUS: ACTIVE SEEKER", fill=(150, 150, 150))

    draw.text((50, 390), f"UID: {uid}", fill=(100, 100, 100))
    draw.text((580, 400), "VERIFIED BY OWPC CORE", fill=gold)

    bio = BytesIO()
    bio.name = 'passport.png'
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
    # Referral logic (v4.4 legacy)
    if context.args and context.args[0].startswith("ref_"):
        ref_id = int(context.args[0].replace("ref_", ""))
        if ref_id != user.id:
            update_user(ref_id, "Referrer", score_inc=50)
            update_user(user.id, user.first_name, referred_by=ref_id)

    res = update_user(user.id, user.first_name)
    kb = [
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🆔 My Passport", callback_data="my_card")],
        [InlineKeyboardButton("🚀 Quest Center", callback_data="open_q"), InlineKeyboardButton("📊 Global Stats", callback_data="view_stats")],
        [InlineKeyboardButton("📅 Daily Points", callback_data="daily"), InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ]
    caption = f"🕊️ **OWPC Core v4.5**\n\nRank: {get_rank_info(res[0])[0]}\nPoints: {res[0]}\n\nBuild the future of decentralized peace. 🚀"
    try: await update.message.reply_photo(photo=open("media/owpc_logo.png", "rb"), caption=caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    except: await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(kb))

async def verify_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_id = int(context.args[0])
        update_user(target_id, "Verified", verify=1, score_inc=500)
        await update.message.reply_text(f"✅ User {target_id} is now VERIFIED. +500 PTS added.")
        await context.bot.send_message(chat_id=target_id, text="🎊 **CONGRATULATIONS!**\n\nYour profile has been verified by the OWPC Core. Your **Verified Badge** is now active on your passport! 👑")
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
        
        wait = await query.message.reply_text("⏳ *Syncing Citizen Data...*")
        card_img = create_visual_card(name, score, rank, uid, is_verified=(is_v == 1))
        
        # Twitter shilling link
        share_txt = f"I am a verified citizen of the OWPC ecosystem! 🕊️\nRank: {rank}\n\nJoin the hive: https://t.me/{BOT_USERNAME}?start=ref_{uid}\n\n$OWPC #Crypto #Web3"
        twitter_url = f"https://twitter.com/intent/tweet?text={share_txt.replace(' ', '%20').replace('#', '%23')}"
        
        kb = [
            [InlineKeyboardButton("🐦 Share on X (Get +500 PTS)", url=twitter_url)],
            [InlineKeyboardButton("📩 I have posted (Verify)", callback_data="req_verify")]
        ]
        
        await query.message.reply_photo(
            photo=card_img,
            caption=f"🆔 **{name}**, here is your digital identity.\n\nStatus: {'✅ VERIFIED' if is_v else '🐣 ACTIVE'}\n\nShare on X and click Verify to claim your badge!",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        await wait.delete()

    elif query.data == "req_verify":
        await query.message.reply_text("✅ **Request Received!**\n\nAn admin will check your Twitter post. Make sure you used the hashtag #OWPC and your link is public! ⏳")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 **VERIFICATION REQUEST**\n\nUser: {name}\nID: `{uid}`\n\nCheck their Twitter and use `/verify {uid}` to approve.")

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
        await query.message.reply_text(f"🔗 **INVITE LINK:**\n\n`https://t.me/{BOT_USERNAME}?start=ref_{uid}`\n\nEarn +50 PTS per friend! 🚀")

    elif query.data == "open_q":
        kb = [[InlineKeyboardButton("📢 Channel", url="..."), InlineKeyboardButton("🐦 Follow X", url="...")], [InlineKeyboardButton("Claim Reward", callback_data="claim_q")]]
        await query.message.reply_text("🚀 **QUEST CENTER**", reply_markup=InlineKeyboardMarkup(kb))

# -------- MAIN --------

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("verify", verify_user))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: None)) # Quiet mode in group
    print("🚀 OWPC v4.5 COMPLETE - Viral Social Proof Edition LIVE")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
