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

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 1414016840 
BOT_USERNAME = "OwpcInfoBot"
LOGO_PATH = "media/owpc_logo.png"

# --- LINKS ---
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LINK_CHANNEL = "https://t.me/+SQhKj-gWWmcyODY0"
LINK_X = "https://x.com/DeepTradeX"

# --- DB ---
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0, last_daily TEXT DEFAULT '', 
                  quests_done INTEGER DEFAULT 0, referred_by INTEGER DEFAULT 0, is_verified INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

def update_user(user_id, name, score_inc=0, daily=None, verify=None):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, name, score, last_daily, referred_by, is_verified) VALUES (?, ?, 0, '', 0, 0)", (user_id, name))
    if score_inc: c.execute("UPDATE users SET score = score + ? WHERE id = ?", (score_inc, user_id))
    if daily: c.execute("UPDATE users SET last_daily = ? WHERE id = ?", (daily, user_id))
    if verify is not None: c.execute("UPDATE users SET is_verified = ? WHERE id = ?", (verify, user_id))
    c.execute("SELECT score, last_daily, quests_done, is_verified FROM users WHERE id = ?", (user_id,))
    res = c.fetchone(); conn.commit(); conn.close()
    return res

def get_rank_info(score):
    if score >= 1000: return "👑 ALPHA LEGEND"
    if score >= 500:  return "💎 UNITY GUARDIAN"
    if score >= 100:  return "🛠️ BUILDER"
    return "🐣 SEEKER"

# --- IMAGE GENERATOR ---
def create_visual_card(name, score, rank, uid, is_verified=False):
    w, h = 1600, 900
    base = Image.new('RGB', (w, h), (10, 10, 18))
    draw = ImageDraw.Draw(base)
    gold, white = (212, 175, 55), (245, 245, 245)
    draw.rectangle([30, 30, 1570, 870], outline=gold, width=8)
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            base.paste(logo.resize((200, 200)), (1300, 70), logo.resize((200, 200)))
            wm = logo.resize((500, 500))
            base.paste(ImageEnhance.Brightness(wm).enhance(0.15), (1000, 350), ImageEnhance.Brightness(wm).enhance(0.15))
        except: pass
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

# --- LOGIC ---
async def send_passport(update: Update):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    rank = get_rank_info(res[0])
    wait = await update.effective_message.reply_text("⏳ *Generating your official Passport...*", parse_mode="Markdown")
    card = create_visual_card(user.first_name, res[0], rank, user.id, is_verified=(res[3] == 1))
    await update.effective_message.reply_photo(photo=card, caption=f"🆔 Official Citizen ID for {user.first_name}")
    await wait.delete()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Invest in OWPC", callback_data="invest_hub")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🆔 My Passport", callback_data="my_card")],
        [InlineKeyboardButton("🚀 Quest Center", callback_data="open_q"), InlineKeyboardButton("📊 Global Stats", callback_data="view_stats")]
    ])
    cap = f"🕊️ **Welcome, {user.first_name}!**\nCredits: {res[0]} OWPC PTS"
    if os.path.exists(LOGO_PATH):
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, reply_markup=kb)
    else:
        await update.message.reply_text(cap, reply_markup=kb)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "my_card": await send_passport(query)
    elif query.data == "back_home":
        # Logique de retour déjà présente en v5.7...
        pass 
    # (Le reste des callback_data de la v5.7 à garder ici)

async def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["passport", "passeport"], lambda u, c: send_passport(u)))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 OWPC v5.8 - Passport Online")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
