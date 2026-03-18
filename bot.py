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

# --- ⚙️ CONFIG (RESTAURÉE) ---
TOKEN = os.getenv("TOKEN") # Ton Token pour @OwpcInfoBot
ADMIN_ID = 1414016840 
BOT_USERNAME = "OwpcInfoBot"
LOGO_PATH = "media/owpc_logo.png"
CHANNEL_ID = "@owpc_co" 
# URL DE TA MINI APP (Celle de @OWPCsbot)
WEBAPP_URL = "https://veos-production.up.railway.app" 

# --- 📊 DB PATH (HARMONISÉ) ---
DB_PATH = "owpc_data.db" 

def get_rank_info(score):
    if score >= 15000: return "👑 OVERLORD", (212, 175, 55)
    if score >= 5000:  return "💎 ELITE", (0, 191, 255)
    if score >= 1500:  return "⚔️ COMMANDER", (220, 20, 60)
    if score >= 500:   return "🛡️ GUARDIAN", (50, 205, 50)
    return "🆕 SEEKER", (200, 200, 200)

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0, 
                  rank TEXT DEFAULT 'NEWBIE', last_checkin TEXT DEFAULT '')''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('live_feed', 'Welcome to the Hive! 🚀')")
    conn.commit(); conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points, last_checkin, rank FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close(); return res

def update_user_db(user_id, name, score_inc=0, daily=None):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, name, points, rank) VALUES (?, ?, ?, ?)", (user_id, name, 0, 'NEWBIE'))
    if score_inc:
        c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (score_inc, user_id))
    if daily:
        c.execute("UPDATE users SET last_checkin = ? WHERE user_id = ?", (daily, user_id))
    conn.commit(); conn.close()
    return get_user_data(user_id)

def create_visual_card(name, score, uid):
    w, h = 1200, 700
    base = Image.new('RGB', (w, h), (10, 10, 18))
    draw = ImageDraw.Draw(base); gold = (212, 175, 55)
    rank_name, rank_color = get_rank_info(score)
    draw.rectangle([20, 20, 1180, 680], outline=rank_color, width=12)
    draw.text((60, 60), "ONE WORLD PEACE COINS", fill=gold)
    draw.text((60, 150), "DIGITAL PASSPORT", fill=(180, 180, 180))
    draw.text((60, 300), f"RANK: {rank_name}", fill=rank_color)
    draw.text((60, 420), f"HOLDER: {name.upper()}", fill=(255, 255, 255))
    draw.text((60, 540), f"CREDITS: {score:,} OWPC", fill=(255, 255, 255))
    bio = BytesIO(); bio.name = 'passport.png'; base.save(bio, 'PNG'); bio.seek(0)
    return bio

# --- ⌨️ KEYBOARDS (RESTAURÉS ET AMÉLIORÉS) ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH HIVE APP", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb")],
        [InlineKeyboardButton("📡 Live Feed", callback_data="live_feed"), InlineKeyboardButton("💎 Staking Sim", callback_data="staking_sim")],
        [InlineKeyboardButton("🆔 My Passport", callback_data="my_card"), InlineKeyboardButton("🚀 Quests", callback_data="open_q")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("🗺️ Roadmap", callback_data="view_roadmap"), InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ])

def back_btn(): return [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]

# --- 🛠️ HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user_db(user.id, user.first_name)
    score = res[0] if res else 0
    rank = get_rank_info(score)[0]
    cap = f"🕊️ **Welcome to OWPC HIVE**\n\nRank: {rank}\nCredits: {score:,} OWPC"
    
    if os.path.exists(LOGO_PATH):
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name
    res = get_user_data(uid)
    score = res[0] if res else 0

    if query.data == "back_home":
        await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nCredits: {score:,} OWPC", reply_markup=main_menu_kb(), parse_mode="Markdown")

    elif query.data == "my_card":
        await query.message.reply_photo(photo=create_visual_card(name, score, uid), caption=f"🆔 Passport: {name}")

    elif query.data == "view_stats":
        await query.message.edit_caption(caption=f"📊 **YOUR HIVE STATS**\n\nRank: {get_rank_info(score)[0]}\nTotal: {score:,} OWPC", reply_markup=InlineKeyboardMarkup([back_btn()]), parse_mode="Markdown")

    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("💎 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            back_btn()
        ])
        await query.message.edit_caption(caption="💰 **INVEST HUB**\nSelect your pillar:", reply_markup=kb)

    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, points FROM users ORDER BY points DESC LIMIT 5")
        top = c.fetchall(); conn.close()
        txt = "🏛️ **HALL OF FAME**\n\n" + "\n".join([f"👑 {u[0]} — {u[1]:,} PTS" for u in top])
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if res and res[1] == today: await query.message.reply_text("⏳ Already claimed! Return tomorrow.")
        else:
            win = random.randint(20, 100)
            update_user_db(uid, name, score_inc=win, daily=today)
            await query.message.reply_text(f"🎰 Lucky Draw: +{win} OWPC Credits!")

async def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Community Bot (DESIGN RESTAURED) is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
