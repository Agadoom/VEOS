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
LOGO_PATH = "media/owpc_logo.png"

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
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
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

# -------- GÉNÉRATION D'IMAGE (V5.4 FIX) --------
def create_visual_card(name, score, rank, uid, is_verified=False):
    w, h = 1600, 900
    base = Image.new('RGB', (w, h), (10, 10, 18))
    draw = ImageDraw.Draw(base)
    gold, white = (212, 175, 55), (245, 245, 245)
    
    # Bordure
    draw.rectangle([30, 30, 1570, 870], outline=gold, width=8)
    
    # Chargement Logo (Correction chemin et transparence)
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            # Logo en haut à droite
            base.paste(logo.resize((200, 200)), (1300, 70), logo.resize((200, 200)))
            # Watermark au centre
            wm = logo.resize((500, 500))
            base.paste(ImageEnhance.Brightness(wm).enhance(0.15), (1000, 350), ImageEnhance.Brightness(wm).enhance(0.15))
        except Exception as e:
            print(f"Logo error: {e}")

    draw.text((100, 80), "OWPC DIGITAL PASSPORT", fill=gold)
    draw.text((100, 300), f"HOLDER: {name.upper()}", fill=white)
    draw.text((100, 420), f"RANK: {rank}", fill=gold)
    draw.text((100, 540), f"CREDITS: {score} OWPC PTS", fill=white)
    
    if is_verified:
        draw.ellipse([1200, 150, 1500, 450], outline=gold, width=6)
        draw.text((1250, 280), "VERIFIED", fill=gold)
    
    draw.text((100, 780), f"UID: {uid}", fill=(120, 120, 120))
    bio = BytesIO(); bio.name = 'passport.png'; base.save(bio, 'PNG'); bio.seek(0)
    return bio

def get_rank_info(score):
    if score >= 1000: return "👑 ALPHA LEGEND"
    if score >= 500:  return "💎 UNITY GUARDIAN"
    if score >= 100:  return "🛠️ BUILDER"
    return "🐣 SEEKER"

# -------- FONCTIONS DE RÉPONSE --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    kb = [[InlineKeyboardButton("💰 Invest in OWPC", callback_data="invest_hub")],
          [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🆔 My Passport", callback_data="my_card")],
          [InlineKeyboardButton("🚀 Quest Center", callback_data="open_q"), InlineKeyboardButton("📊 Global Stats", callback_data="view_stats")]]
    
    cap = f"🕊️ **OWPC Core v5.4**\n\nRank: {get_rank_info(res[0])}\nPoints: {res[0]}\n\nWelcome back to the hive. 🚀"
    
    # On renvoie la photo de bienvenue (le logo)
    if os.path.exists(LOGO_PATH):
        await update.effective_message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.effective_message.reply_text(cap, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def invest_hub_function(update: Update):
    txt = "💰 **OWPC INVESTOR CENTER**\n\n🧬 **GENESIS**: The core utility token.\n💎 **UNITY**: Governance & Rewards.\n⚡ **VEO**: Transactional speed.\n\nBuy on Blum Memepad:"
    kb = [[InlineKeyboardButton("🧬 Buy GENESIS", url=LINK_GENESIS)],
          [InlineKeyboardButton("💎 Buy UNITY", url=LINK_UNITY)],
          [InlineKeyboardButton("⚡ Buy VEO", url=LINK_VEO)]]
    await update.effective_message.reply_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def passport_function(update: Update):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    rank = get_rank_info(res[0])
    card = create_visual_card(user.first_name, res[0], rank, user.id, is_verified=(res[3] == 1))
    await update.effective_message.reply_photo(photo=card, caption=f"🆔 Passport for {user.first_name}")

# -------- CALLBACKS --------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "invest_hub": await invest_hub_function(update)
    elif query.data == "my_card": await passport_function(update)
    elif query.data == "view_stats":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT COUNT(*), SUM(score) FROM users"); s = c.fetchone(); conn.close()
        await query.message.reply_text(f"📊 Citizens: {s[0]}\nTotal Credits: {s[1]} pts")
    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
        txt = "🏆 **TOP 10**\n\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]} pts" for i, r in enumerate(c.fetchall())]); conn.close()
        await query.message.reply_text(txt)
    elif query.data == "open_q":
        kb = [[InlineKeyboardButton("📢 Channel", url=LINK_CHANNEL)], [InlineKeyboardButton("🐦 X", url=LINK_X)], [InlineKeyboardButton("💰 Claim (+100)", callback_data="claim_q")]]
        await query.message.reply_text("🚀 **QUEST CENTER**", reply_markup=InlineKeyboardMarkup(kb))
    elif query.data == "claim_q":
        res = update_user(query.from_user.id, query.from_user.first_name)
        if res[2] == 1: await query.message.reply_text("❌ Already done!")
        else: update_user(query.from_user.id, query.from_user.first_name, score_inc=100, complete_quest=True); await query.message.reply_text("🔥 +100 Points!")

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("invest", lambda u, c: invest_hub_function(u)))
    app.add_handler(CommandHandler("passport", lambda u, c: passport_function(u)))
    app.add_handler(CommandHandler("stats", start))
    app.add_handler(CommandHandler("leaderboard", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 OWPC v5.4 LIVE - Logo Fix")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
