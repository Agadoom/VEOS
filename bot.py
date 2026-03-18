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

# --- Ranks Logic ---
def get_rank_info(score):
    if score >= 15000: return "👑 OVERLORD", (255, 215, 0)
    if score >= 5000:  return "💎 ELITE", (0, 191, 255)
    if score >= 1500:  return "⚔️ COMMANDER", (220, 20, 60)
    if score >= 500:   return "🛡️ GUARDIAN", (50, 205, 50)
    return "🆕 SEEKER", (200, 200, 200)

# --- DATABASE ---
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0, last_daily TEXT DEFAULT '', 
                  quests_done INTEGER DEFAULT 0, referred_by INTEGER DEFAULT 0, is_verified INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('live_feed', 'Welcome to the OWPC Live Feed!')")
    conn.commit(); conn.close()

def get_feed():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'live_feed'")
    res = c.fetchone(); conn.close()
    return res[0] if res else "No news yet."

def update_user(user_id, name, score_inc=0, daily=None, ref_by=0):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (id, name, score, referred_by) VALUES (?, ?, ?, ?)", (user_id, name, 50 if ref_by else 0, ref_by))
        if ref_by: c.execute("UPDATE users SET score = score + 100 WHERE id = ?", (ref_by,))
    if score_inc: c.execute("UPDATE users SET score = score + ? WHERE id = ?", (score_inc, user_id))
    if daily: c.execute("UPDATE users SET last_daily = ? WHERE id = ?", (daily, user_id))
    conn.commit(); conn.close()
    return get_user_data(user_id)

def get_user_data(user_id):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT score, last_daily, quests_done, is_verified, referred_by FROM users WHERE id = ?", (user_id,))
    res = c.fetchone(); conn.close(); return res

# --- IMAGE ENGINE ---
def create_visual_card(name, score, uid, is_verified=False):
    w, h = 1600, 900
    base = Image.new('RGB', (w, h), (10, 10, 18))
    draw = ImageDraw.Draw(base); gold = (212, 175, 55)
    rank_name, rank_color = get_rank_info(score)
    draw.rectangle([30, 30, 1570, 870], outline=rank_color, width=12)
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            base.paste(logo.resize((200, 200)), (1300, 70), logo.resize((200, 200)))
        except: pass
    draw.text((100, 80), "OWPC DIGITAL PASSPORT", fill=gold)
    draw.text((100, 220), f"RANK: {rank_name}", fill=rank_color)
    draw.text((100, 380), f"HOLDER: {name.upper()}", fill=(245, 245, 245))
    draw.text((100, 540), f"CREDITS: {score} OWPC PTS", fill=(245, 245, 245))
    bio = BytesIO(); bio.name = 'passport.png'; base.save(bio, 'PNG'); bio.seek(0)
    return bio

# --- KEYBOARDS ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb")],
        [InlineKeyboardButton("📡 Live Feed", callback_data="live_feed"), InlineKeyboardButton("💎 Staking Sim", callback_data="staking_sim")],
        [InlineKeyboardButton("🆔 My Passport", callback_data="my_card"), InlineKeyboardButton("🚀 Quests", callback_data="open_q")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("📅 Daily", callback_data="daily")],
        [InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ])

def back_btn():
    return [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name, ref_by=int(context.args[0].replace("ref_","")) if context.args and context.args[0].startswith("ref_") else 0)
    rank, _ = get_rank_info(res[0])
    cap = f"🕊️ **Welcome, {user.first_name}!**\nRank: {rank}\nPoints: {res[0]}"
    if os.path.exists(LOGO_PATH):
        await update.effective_message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.effective_message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name
    res = get_user_data(uid)

    if query.data == "back_home":
        await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nPoints: {res[0]}", reply_markup=main_menu_kb())

    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS)],
            [InlineKeyboardButton("💎 UNITY", url=LINK_UNITY)],
            [InlineKeyboardButton("⚡ VEO", url=LINK_VEO)], # VEO REVENU !
            back_btn()
        ])
        await query.message.edit_caption(caption="💰 **INVESTOR HUB**\nAccess our 3 main pillars:", reply_markup=kb)

    elif query.data == "staking_sim":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Simulate 10k", callback_data="sim_10k")],
            [InlineKeyboardButton("Simulate 50k", callback_data="sim_50k")],
            back_btn()
        ])
        await query.message.edit_caption(caption="💎 **STAKING SIMULATOR**\nEstimate your passive income:", reply_markup=kb)

    elif query.data.startswith("sim_"):
        amt = 10000 if "10k" in query.data else 50000
        txt = f"📊 **RESULTS ({amt:,})**\n\n💎 UNITY (25%): {(amt*0.25/12):.1f}/mo\n🧬 GENESIS (12%): {(amt*0.12/12):.1f}/mo"
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "open_q":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=LINK_CHANNEL)],
            [InlineKeyboardButton("✅ Claim Reward (+100)", callback_data="claim_q")],
            back_btn()
        ])
        await query.message.edit_caption(caption="🚀 **QUEST CENTER**\nComplete tasks to earn points!", reply_markup=kb)

    elif query.data == "claim_q":
        update_user(uid, name, score_inc=100)
        await query.message.reply_text("🔥 Quest Complete! +100 PTS")

    elif query.data == "my_card":
        card = create_visual_card(name, res[0], uid)
        await query.message.reply_photo(photo=card, caption=f"🆔 Passport: {name}")

    elif query.data == "live_feed":
        await query.message.edit_caption(caption=f"📡 **LIVE FEED**\n\n{get_feed()}", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 5"); top = c.fetchall(); conn.close()
        txt = "🏛️ **HALL OF FAME**\n\n" + "\n".join([f"👑 {u[0]} — {u[1]} PTS" for u in top])
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "get_invite":
        await query.message.edit_caption(caption=f"🔗 **INVITE LINK**\n`https://t.me/{BOT_USERNAME}?start=ref_{uid}`", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "view_stats":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT COUNT(*) FROM users"); total = c.fetchone()[0]; conn.close()
        await query.message.edit_caption(caption=f"📊 **TOTAL CITIZENS:** {total}", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if res[1] == today: await query.message.reply_text("⏳ Come back tomorrow!")
        else:
            update_user(uid, name, score_inc=15, daily=today)
            await query.message.reply_text("✅ +15 PTS!")

async def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 OWPC v6.8 MASTER FIXED")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
