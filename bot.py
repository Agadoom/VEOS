import os
import asyncio
import sqlite3
import random
import nest_asyncio
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest

nest_asyncio.apply()

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 1414016840 
BOT_USERNAME = "OwpcInfoBot"
LOGO_PATH = "media/owpc_logo.png"
CHANNEL_ID = "@owpc_co" # <--- REMPLACE PAR LE NOM DE TON CANAL (ex: @OwpcAnnouncements)

# --- LINKS ---
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LINK_CHANNEL = "https://t.me/+SQhKj-gWWmcyODY0"

# --- DB & RANK LOGIC ---
DB_PATH = "data/owpc_data.db"
os.makedirs("data", exist_ok=True)

def get_rank_info(score):
    if score >= 15000: return "👑 OVERLORD", (255, 215, 0)
    if score >= 5000:  return "💎 ELITE", (0, 191, 255)
    if score >= 1500:  return "⚔️ COMMANDER", (220, 20, 60)
    if score >= 500:   return "🛡️ GUARDIAN", (50, 205, 50)
    return "🆕 SEEKER", (200, 200, 200)

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, name TEXT, score INTEGER DEFAULT 0, last_daily TEXT DEFAULT '', 
                  quests_done INTEGER DEFAULT 0, referred_by INTEGER DEFAULT 0, is_verified INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('live_feed', 'Welcome to the Hive!')")
    conn.commit(); conn.close()

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

# --- CHECK MEMBERSHIP ---
async def is_subscribed(context, user_id):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

# --- KEYBOARDS ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb")],
        [InlineKeyboardButton("📡 Live Feed", callback_data="live_feed"), InlineKeyboardButton("💎 Staking Sim", callback_data="staking_sim")],
        [InlineKeyboardButton("🆔 My Passport", callback_data="my_card"), InlineKeyboardButton("🚀 Quests", callback_data="open_q")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("🔗 Invite Friends", callback_data="get_invite")]
    ])

def back_btn():
    return [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ref_id = 0
    if context.args and context.args[0].startswith("ref_"):
        try: ref_id = int(context.args[0].replace("ref_", ""))
        except: pass
    res = update_user(user.id, user.first_name, ref_by=ref_id)
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

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if res[1] == today:
            await query.message.reply_text("⏳ Already claimed! Come back tomorrow.")
        else:
            if await is_subscribed(context, uid):
                win = random.choices([10, 25, 50, 100], weights=[50, 30, 15, 5])[0]
                update_user(uid, name, score_inc=win, daily=today)
                await query.message.reply_text(f"🎰 **LUCKY DRAW**\n\nYou won **{win} OWPC PTS**! 🔥")
            else:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=LINK_CHANNEL)], [InlineKeyboardButton("🔄 Check again", callback_data="daily")]])
                await query.message.reply_text("🚫 **ACCESS DENIED**\nYou must join our channel to claim your daily points!", reply_markup=kb)

    elif query.data == "open_q":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Channel", url=LINK_CHANNEL)], [InlineKeyboardButton("✅ Claim +100", callback_data="claim_q")], back_btn()])
        await query.message.edit_caption(caption="🚀 **QUESTS**\nRequirement: Join channel to verify.", reply_markup=kb)

    elif query.data == "claim_q":
        if await is_subscribed(context, uid):
            update_user(uid, name, score_inc=100)
            await query.message.reply_text("🔥 Verification Success! +100 PTS")
        else:
            await query.message.reply_text("❌ Not a member yet! Join the channel first.")

    # --- REPRISE DU CODE FONCTIONNEL v6.8 ---
    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS)], [InlineKeyboardButton("💎 UNITY", url=LINK_UNITY)], [InlineKeyboardButton("⚡ VEO", url=LINK_VEO)], back_btn()])
        await query.message.edit_caption(caption="💰 **INVESTOR HUB**", reply_markup=kb)

    elif query.data == "staking_sim":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("10k Sim", callback_data="sim_10k")], [InlineKeyboardButton("50k Sim", callback_data="sim_50k")], back_btn()])
        await query.message.edit_caption(caption="💎 **STAKING SIMULATOR**", reply_markup=kb)

    elif query.data.startswith("sim_"):
        amt = 10000 if "10k" in query.data else 50000
        txt = f"📊 **RESULTS ({amt:,})**\nUnity (25%): {(amt*0.25/12):.1f}/mo"
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "my_card":
        from bot_logic import create_visual_card # Si séparé, sinon garder la fonction
        await query.message.reply_photo(photo=create_visual_card(name, res[0], uid), caption=f"🆔 Passport: {name}")

    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 5"); top = c.fetchall(); conn.close()
        txt = "🏛️ **HALL OF FAME**\n\n" + "\n".join([f"👑 {u[0]} — {u[1]} PTS" for u in top])
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([back_btn()]))

async def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🚀 OWPC v6.9 GROWTH ENGINE LIVE")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
