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

def update_user(user_id, name, score_inc=0, daily=None, ref_by=0):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    exists = c.fetchone()
    
    if not exists:
        # Nouveau membre : 50 PTS si parrainé, sinon 0
        bonus_start = 50 if ref_by else 0
        c.execute("INSERT INTO users (id, name, score, referred_by) VALUES (?, ?, ?, ?)", 
                  (user_id, name, bonus_start, ref_by))
        if ref_by:
            # Bonus de 100 PTS pour le parrain
            c.execute("UPDATE users SET score = score + 100 WHERE id = ?", (ref_by,))
    
    if score_inc: c.execute("UPDATE users SET score = score + ? WHERE id = ?", (score_inc, user_id))
    if daily: c.execute("UPDATE users SET last_daily = ? WHERE id = ?", (daily, user_id))
    
    c.execute("SELECT score, last_daily, quests_done, is_verified, referred_by FROM users WHERE id = ?", (user_id,))
    res = c.fetchone(); conn.commit(); conn.close()
    return res

# --- KEYBOARDS ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Invest in OWPC", callback_data="invest_hub")],
        [InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb"), InlineKeyboardButton("📡 Live Feed", callback_data="live_feed")],
        [InlineKeyboardButton("💎 Staking Simulator", callback_data="staking_sim")],
        [InlineKeyboardButton("🆔 My Passport", callback_data="my_card"), InlineKeyboardButton("🚀 Quests", callback_data="open_q")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("📅 Daily", callback_data="daily")],
        [InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ])

def back_btn():
    return [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    ref_id = 0
    
    # Détection du lien de parrainage
    if args and args[0].startswith("ref_"):
        try:
            potential_ref = int(args[0].replace("ref_", ""))
            if potential_ref != user.id: ref_id = potential_ref
        except: pass

    res = update_user(user.id, user.first_name, ref_by=ref_id)
    
    cap = f"🕊️ **Welcome to the Hive, {user.first_name}!**\n"
    if ref_id: cap += "🎁 *You received 50 Welcome PTS!*\n"
    cap += f"\nCredits: {res[0]} OWPC PTS"

    if os.path.exists(LOGO_PATH):
        await update.effective_message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.effective_message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg = " ".join(context.args)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT id FROM users"); users = c.fetchall(); conn.close()
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid[0], text=f"🚨 **OWPC ALERT**\n\n{msg}", parse_mode="Markdown")
            await asyncio.sleep(0.05)
        except: continue

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name
    res = update_user(uid, name)

    if query.data == "back_home":
        await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nPoints: {res[0]}", reply_markup=main_menu_kb())
    
    elif query.data == "get_invite":
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        txt = f"🔗 **INVITATION LINK**\n\nShare this link to grow the hive:\n`{link}`\n\n🎁 **Rewards:**\n• Friend joins: +100 PTS for you\n• Friend joins: +50 PTS for them"
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([back_btn()]), parse_mode="Markdown")

    elif query.data == "view_stats":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users"); total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (uid,))
        invited = c.fetchone()[0]
        conn.close()
        await query.message.edit_caption(caption=f"📊 **STATS**\n\nGlobal Citizens: {total}\nYour Referrals: {invited} 🤝", reply_markup=InlineKeyboardMarkup([back_btn()]))

    # (Garder toutes les autres fonctions de la v6.3 : invest_hub, staking_sim, view_lb, my_card, open_q, daily...)
    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS)], [InlineKeyboardButton("💎 UNITY", url=LINK_UNITY)], [InlineKeyboardButton("⚡ VEO", url=LINK_VEO)], back_btn()])
        await query.message.edit_caption(caption="💰 **INVESTOR HUB**", reply_markup=kb)

    elif query.data == "live_feed":
        news = "📡 **LIVE FEED**\n\nReferral 2.0 is LIVE! Earn 100 PTS per invite. 🚀"
        await query.message.edit_caption(caption=news, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 5"); top = c.fetchall(); conn.close()
        txt = "🏛️ **HALL OF FAME**\n\n" + "\n".join([f"👑 {u[0]} — {u[1]} PTS" for u in top])
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([back_btn()]))

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
    print("🚀 OWPC v6.4 VIRAL SYSTEM LIVE")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
