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

# --- DB LOGIC ---
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0, last_daily TEXT DEFAULT '', 
                  quests_done INTEGER DEFAULT 0, referred_by INTEGER DEFAULT 0, is_verified INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

def update_user(user_id, name, score_inc=0, daily=None):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, name, score, last_daily) VALUES (?, ?, 0, '')", (user_id, name))
    if score_inc: c.execute("UPDATE users SET score = score + ? WHERE id = ?", (score_inc, user_id))
    if daily: c.execute("UPDATE users SET last_daily = ? WHERE id = ?", (daily, user_id))
    c.execute("SELECT score, last_daily, quests_done, is_verified FROM users WHERE id = ?", (user_id,))
    res = c.fetchone(); conn.commit(); conn.close()
    return res

# --- IMAGE ENGINE ---
def create_visual_card(name, score, uid, is_verified=False):
    w, h = 1600, 900
    base = Image.new('RGB', (w, h), (10, 10, 18))
    draw = ImageDraw.Draw(base); gold = (212, 175, 55)
    draw.rectangle([30, 30, 1570, 870], outline=gold, width=8)
    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH).convert("RGBA")
        base.paste(logo.resize((200, 200)), (1300, 70), logo.resize((200, 200)))
    draw.text((100, 80), "OWPC DIGITAL PASSPORT", fill=gold)
    draw.text((100, 300), f"HOLDER: {name.upper()}", fill=(245, 245, 245))
    draw.text((100, 540), f"CREDITS: {score} OWPC PTS", fill=(245, 245, 245))
    if is_verified: draw.text((1250, 280), "VERIFIED", fill=gold)
    bio = BytesIO(); bio.name = 'passport.png'; base.save(bio, 'PNG'); bio.seek(0)
    return bio

# --- KEYBOARDS ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Invest in OWPC", callback_data="invest_hub")],
        [InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb"), InlineKeyboardButton("📡 Live Feed", callback_data="live_feed")],
        [InlineKeyboardButton("💎 Staking Simulator", callback_data="staking_sim")],
        [InlineKeyboardButton("🆔 My Passport", callback_data="my_card"), InlineKeyboardButton("🚀 Quests", callback_data="open_q")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("📅 Daily", callback_data="daily")]
    ])

def back_btn():
    return [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    res = update_user(user.id, user.first_name)
    cap = f"🕊️ **Welcome, {user.first_name}!**\nCredits: {res[0]} OWPC PTS"
    if os.path.exists(LOGO_PATH):
        await update.effective_message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.effective_message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: await update.message.reply_text("Usage: `/broadcast message`")
    msg = " ".join(context.args)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT id FROM users"); users = c.fetchall(); conn.close()
    count = 0
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id[0], text=f"🚨 **OWPC GLOBAL ALERT** 🚨\n\n{msg}", parse_mode="Markdown")
            count += 1
            await asyncio.sleep(0.05)
        except: continue
    await update.message.reply_text(f"✅ Alert sent to {count} citizens.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name
    res = update_user(uid, name)

    if query.data == "back_home":
        await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nPoints: {res[0]}", reply_markup=main_menu_kb())

    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS)], [InlineKeyboardButton("💎 UNITY", url=LINK_UNITY)], [InlineKeyboardButton("⚡ VEO", url=LINK_VEO)], back_btn()])
        await query.message.edit_caption(caption="💰 **INVESTOR HUB**", reply_markup=kb)

    elif query.data == "live_feed":
        news = "📡 **OWPC LIVE FEED**\n\n🟢 GENESIS: Active\n🔵 UNITY: High Staking Yields\n🟡 VEO: Flash Speed Enabled\n\n📅 Updated: March 2026"
        await query.message.edit_caption(caption=news, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 5"); top = c.fetchall(); conn.close()
        txt = "🏛️ **HALL OF FAME**\n\n" + "\n".join([f"👑 {u[0]} — {u[1]} PTS" for u in top])
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "staking_sim":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Simulate 10k", callback_data="sim_10k")], back_btn()])
        await query.message.edit_caption(caption="💎 **SIMULATOR**\nEstimate gains for Unity (25% APR).", reply_markup=kb)

    elif query.data.startswith("sim_"):
        await query.message.edit_caption(caption="📊 **Gains for 10,000 $OWPC**\nMonthly: 208 UNITY", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "my_card":
        card = create_visual_card(name, res[0], uid, is_verified=(res[3]==1))
        await query.message.reply_photo(photo=card, caption=f"🆔 Passport for {name}")

    elif query.data == "open_q":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Channel", url=LINK_CHANNEL)], [InlineKeyboardButton("💰 Claim +100", callback_data="claim_q")], back_btn()])
        await query.message.edit_caption(caption="🚀 **QUESTS**", reply_markup=kb)

    elif query.data == "claim_q":
        update_user(uid, name, score_inc=100); await query.message.reply_text("🔥 +100 PTS!")

    elif query.data == "view_stats":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT COUNT(*) FROM users"); count = c.fetchone()[0]
        await query.message.edit_caption(caption=f"📊 **TOTAL CITIZENS:** {count}", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if res[1] == today: await query.message.reply_text("⏳ Tomorrow!")
        else:
            update_user(uid, name, score_inc=15, daily=today)
            await query.message.reply_text("✅ +15 PTS!")

async def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 OWPC v6.3 ALERT SYSTEM LIVE")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
