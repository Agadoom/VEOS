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

# --- DB & LOGIC ---
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

# --- PASSPORT ENGINE ---
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

# --- INTERFACE ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Invest in OWPC", callback_data="invest_hub")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_lb"), InlineKeyboardButton("🆔 My Passport", callback_data="my_card")],
        [InlineKeyboardButton("🚀 Quest Center", callback_data="open_q"), InlineKeyboardButton("📊 Global Stats", callback_data="view_stats")],
        [InlineKeyboardButton("📅 Daily Points", callback_data="daily"), InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ])

def back_btn():
    return [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    cap = f"🕊️ **Welcome, {user.first_name}!**\n\nRank: {get_rank_info(res[0])}\nCredits: {res[0]} OWPC PTS"
    if os.path.exists(LOGO_PATH):
        await update.effective_message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.effective_message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def passport_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    rank = get_rank_info(res[0])
    card = create_visual_card(user.first_name, res[0], rank, user.id, is_verified=(res[3] == 1))
    await update.effective_message.reply_photo(photo=card, caption=f"🆔 Passport for {user.first_name}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name
    res = update_user(uid, name)

    if query.data == "back_home":
        await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nCitizen: {name}\nPoints: {res[0]}", reply_markup=main_menu_kb())

    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS)], [InlineKeyboardButton("💎 UNITY", url=LINK_UNITY)], [InlineKeyboardButton("⚡ VEO", url=LINK_VEO)], back_btn()])
        await query.message.edit_caption(caption="💰 **INVESTOR HUB**", reply_markup=kb)

    elif query.data == "open_q":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Channel", url=LINK_CHANNEL)], [InlineKeyboardButton("🐦 X", url=LINK_X)], [InlineKeyboardButton("💰 Claim (+100)", callback_data="claim_q")], back_btn()])
        await query.message.edit_caption(caption="🚀 **QUEST CENTER**", reply_markup=kb)

    elif query.data == "claim_q":
        # Logique simplifiée pour l'exemple
        update_user(uid, name, score_inc=100)
        await query.message.reply_text("🔥 Quest Complete! +100 Points.")

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if res[1] == today: await query.message.reply_text("⏳ Come back tomorrow!")
        else:
            update_user(uid, name, score_inc=15, daily=today)
            await query.message.reply_text("✅ +15 Points added!")

    elif query.data == "view_stats":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT COUNT(*) FROM users"); count = c.fetchone()[0]; conn.close()
        await query.message.edit_caption(caption=f"📊 **STATS**\n\nCitizens: {count}", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 5")
        lb = "🏆 **TOP 5**\n\n" + "\n".join([f"{r[0]}: {r[1]}" for r in c.fetchall()])
        await query.message.edit_caption(caption=lb, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "get_invite":
        await query.message.edit_caption(caption=f"🔗 **INVITE**\n`https://t.me/{BOT_USERNAME}?start=ref_{uid}`", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "my_card":
        await passport_cmd(update, context)

# --- MAIN ---
async def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["passport", "passeport"], passport_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 OWPC v5.9 Master LIVE")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
