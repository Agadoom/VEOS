import os
import asyncio
import sqlite3
import nest_asyncio
from io import BytesIO
from datetime import datetime
from collections import defaultdict
# We make sure to have all needed Pillow parts
from PIL import Image, ImageDraw, ImageFont, ImageEnhance 
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import openai

nest_asyncio.apply()

# -------- CONFIGURATION --------
# Correct Username to match screenshots
TOKEN = os.getenv("TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", 0))
BOT_USERNAME = "OwpcInfoBot" # Case corrected from screenshots
ADMIN_ID = 1414016840 

# -------- DATABASE --------
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER, last_daily TEXT, quests_done INTEGER DEFAULT 0, referred_by INTEGER)''')
    conn.commit(); conn.close()

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

# -------- IMPROVED IMAGE LOGIC (V4.4 PREMIUM) --------

def create_visual_card(name, score, rank, uid):
    # Dimensions 800x450 (NFT/Card ratio)
    w, h = 800, 450
    
    # 1. Background: Dark Gradient (Web3 professional)
    base = Image.new('RGB', (w, h), (5, 5, 8)) # Deep space background
    draw = ImageDraw.Draw(base)
    
    # 2. Base Border: Rich Gold
    gold_color = (212, 175, 55)
    draw.rectangle([10, 10, 790, 440], outline=gold_color, width=4)
    
    # 3. Logo Watermark Background
    try:
        logo = Image.open("media/owpc_logo.png").convert("RGBA")
        logo_w, logo_h = logo.size
        
        # Bottom Right Watermark (Enriched looks)
        watermark = logo.resize((150, 150))
        enhancer = ImageEnhance.Brightness(watermark)
        watermark = enhancer.enhance(0.4) # Darker so text is readable
        base.paste(watermark, (600, 260), watermark)
        
        # Upper Right Official Logo
        small_logo = logo.resize((80, 80))
        base.paste(small_logo, (680, 40), small_logo)
    except Exception as e:
        print(f"Image Error: {e}") # Debug but no crash
        pass

    # 4. Text and Data (All English, Rich Gold/White)
    try: font_main = ImageFont.load_default()
    except: font_main = None

    # Text Colors
    c_gold = (212, 175, 55)
    c_white = (245, 245, 245)
    c_gray = (160, 160, 160)

    # Upper Left: Ecosystem ID
    draw.text((40, 40), "OWPC DIGITAL CITIZEN", fill=c_gold)
    draw.text((40, 60), "━━━━━━━━━━━━━━━━━━", fill=c_gold)
    
    # Main Data (White for holder, Gold for rank/points)
    draw.text((40, 150), f"HOLDER: {name.upper()}", fill=c_white)
    
    # If Legend, make it extra golden
    is_legend = "Legend" in rank
    draw.text((40, 210), f"RANK: {rank}", fill=c_gold if is_legend else c_gray)
    
    # Point Bar Visualization (Simplified but visual)
    draw.text((40, 270), f"CREDITS: {score} OWPC PTS", fill=c_white)
    draw.text((40, 290), "━━━━━━━━━━━━━━━━━━", fill=c_gray)
    
    # UID at the bottom, small and professional
    draw.text((40, 390), f"UID: {uid}", fill=c_gray)
    
    # Lower Right Status
    draw.text((580, 400), "OFFICIAL PASSPORT v1.1", fill=c_gold)

    # 5. Output Preparation
    bio = BytesIO()
    bio.name = 'citizen_passport.png'
    base.save(bio, 'PNG')
    bio.seek(0)
    return bio

# -------- TOOLS & DATA --------
LOGO_PATH = "media/owpc_logo.png"

def get_rank_info(score):
    if score >= 1000: return "👑 ALPHA LEGEND", "MAX", "Legend Power Unlocked."
    if score >= 500:  return "💎 UNITY GUARDIAN", 1000, "Progress to Legend"
    if score >= 100:  return "🛠️ BUILDER", 500, "Progress to Guardian"
    return "🐣 SEEKER", 100, "Progress to Builder"

def generate_progress_bar(score, next_val):
    if next_val == "MAX": return "██████████ 100%"
    percent = min(100, int((score / next_val) * 100))
    filled = int(percent / 10)
    return f"{'█' * filled}{'░' * (10 - filled)} {percent}%"

# -------- HANDLERS --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    #
    score_res = update_user(user.id, user.first_name)
    
    # Anglicized Buttons to match screenshots
    kb = [
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🆔 My Passport", callback_data="my_card")],
        [InlineKeyboardButton("🚀 Quest Center", callback_data="open_q"), InlineKeyboardButton("📊 Global Stats", callback_data="view_stats")],
        [InlineKeyboardButton("📅 Daily Points", callback_data="daily"), InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ]
    
    # English Caption
    cap = (
        f"🕊️ **OWPC Core v4.4**\n\nRank: {get_rank_info(score_res[0])[0]}\nPoints: {score_res[0]}\n\n"
        f"Build the future of decentralized peace with us. 🚀"
    )
    
    try: await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    except: await update.message.reply_text(cap, reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid, name = query.from_user.id, query.from_user.first_name
    await query.answer()

    if query.data == "my_card":
        score = update_user(uid, name)[0]
        rank, next_val, msg = get_rank_info(score)
        # bar = generate_progress_bar(score, next_val) # No longer needed in v4.4 private caption

        # English Wait Message
        wait_msg = await query.message.reply_text("⏳ *Generating your Elite Citizen Passport...*", parse_mode="Markdown")
        
        # Generated Visual Card (NEW)
        try:
            card_img = create_visual_card(name, score, rank, uid)
            
            # English Share Link
            share_text = f"Claiming my status on OWPC. Rank: {rank}! 🕊️ Join: https://t.me/{BOT_USERNAME}?start=ref_{uid}"
            share_url = f"https://t.me/share/url?url={share_text}"
            kb = [[InlineKeyboardButton("📣 Share on X", url=f"https://twitter.com/intent/tweet?text={share_text}")],
                  [InlineKeyboardButton("Transférer sur Telegram", url=share_url)]]
            
            await query.message.reply_photo(
                photo=card_img,
                caption=f"🆔 **{name}**, here is your official OWPC Citizen Passport.\n\nThis document proves your active dedication to the ecosystem. 🕊️",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            await wait_msg.delete()
        except Exception as e:
            await wait_msg.edit_text(f"❌ Error generating image: {e}")

    elif query.data == "view_stats":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT COUNT(*), SUM(score) FROM users")
        stats = c.fetchone()
        
        txt = (
            f"📊 **OWPC GLOBAL STATS**\n\n"
            f"👥 **Total Citizens:** {stats[0]}\n"
            f"💰 **Total Points Issued:** {stats[1]} pts\n\n"
            f"We are growing together. 🕊️"
        )
        await query.message.reply_text(txt, parse_mode="Markdown")

    elif query.data == "view_lb":
        # ... (Leaderboard Logic) ...
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
        rows = c.fetchall()
        txt = "🏆 **GLOBAL TOP 10**\n\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]} pts" for i, r in enumerate(rows)])
        await query.message.reply_text(txt)

    elif query.data == "get_invite":
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        await query.message.reply_text(f"🔗 **INVITE LINK:**\n\n`{link}`\n\nEarn +50 PTS for every new referral! 🚀", parse_mode="Markdown")
        
    elif query.data == "open_q":
        # ... Quests English Logic ...
        kb = [[InlineKeyboardButton("📢 Channel", url="..."), InlineKeyboardButton("🐦 Follow X", url="...")], [InlineKeyboardButton("Claim Reward", callback_data="claim_q")]]
        await query.message.reply_text("🚀 **QUEST CENTER**", reply_markup=InlineKeyboardMarkup(kb))
    
    # ... Other Handlers Daily, Claim ...

# -------- MESSAGES HANDLERS & ELITE ALERT --------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #
    if not update.message or not update.message.from_user: return
    user = update.message.from_user
    chat_id = update.effective_chat.id
    text = (update.message.text or "").lower()

    if chat_id == GROUP_CHAT_ID:
        old_res = update_user(user.id, user.first_name)
        new_res = update_user(user.id, user.first_name, score_inc=1) # Message bonus
        
        # 1. SPECIAL ELITE ALERT (Level up notification)
        old_rank = get_rank_info(old_res[0])[0]
        new_rank = get_rank_info(new_res[0])[0]
        
        if old_rank != new_rank and "Legend" in new_rank:
            # Send private message only
            await context.bot.send_message(
                chat_id=user.id, 
                text=f"👑 **Congratulations ALPHA LEGEND!**\n\n"
                     "You have officially unlocked the highest rank in the OWPC hive.\n"
                     "Perks and special benefits will be announced soon. This is your moment. 🕊️"
            )

    if update.effective_chat.type == "private":
        # IA Private logic...
        pass

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 OWPC Elite v4.4 - All English, Visual Card & Perks LIVE")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
