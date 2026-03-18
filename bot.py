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

# --- ⚙️ CONFIG ---
TOKEN = os.getenv("TOKEN") # Token pour @OwpcInfoBot
ADMIN_ID = 1414016840 
LOGO_PATH = "media/owpc_logo.png"
CHANNEL_ID = "@owpc_co" 
WEBAPP_URL = "https://veos-production.up.railway.app" # Lien vers ta Mini App
DB_PATH = "owpc_data.db" 

# --- 📊 LOGIC ---
def get_rank_info(score):
    if score >= 15000: return "👑 OVERLORD", (212, 175, 55)
    if score >= 5000:  return "💎 ELITE", (0, 191, 255)
    if score >= 1500:  return "⚔️ COMMANDER", (220, 20, 60)
    if score >= 500:   return "🛡️ GUARDIAN", (50, 205, 50)
    return "🆕 SEEKER", (200, 200, 200)

def get_user_data(user_id):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points, last_checkin, rank FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close(); return res

def update_user_db(user_id, name, score_inc=0, daily=None):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name, points, rank) VALUES (?, ?, 0, 'NEWBIE')", (user_id, name))
    if score_inc: c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (score_inc, user_id))
    if daily: c.execute("UPDATE users SET last_checkin = ? WHERE user_id = ?", (daily, user_id))
    conn.commit(); conn.close()
    return get_user_data(user_id)

# --- ⌨️ KEYBOARDS ---
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
    cap = f"🕊️ **Welcome to One World Peace Coins**\n\nCommander: {user.first_name}\nCredits: {res[0]:,} OWPC\nRank: {get_rank_info(res[0])[0]}"
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

    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            back_btn()
        ])
        await query.message.edit_caption(caption="💰 **INVEST HUB**\nBuild the ecosystem through our 3 pillars.", reply_markup=kb)

    elif query.data == "staking_sim":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📊 Calculate Rewards", callback_data="sim_now")], back_btn()])
        await query.message.edit_caption(caption="💎 **STAKING SIMULATOR**\nProject your future earnings.", reply_markup=kb)

    elif query.data == "sim_now":
        await query.message.edit_caption(caption="📈 **ESTIMATED YIELD**\n- Unity: 208/mo\n- Genesis: 100/mo\n- Total: 308 OWPC/mo", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "open_q":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Channel", url="https://t.me/owpc_co")],
            [InlineKeyboardButton("Check & Claim", callback_data="claim_q")],
            back_btn()
        ])
        await query.message.edit_caption(caption="🚀 **UNITY QUESTS**\nEarn credits by supporting the community.", reply_markup=kb)

    elif query.data == "claim_q":
        # Simulation de vérification
        update_user_db(uid, name, score_inc=50)
        await query.message.reply_text("🔥 Quest Validated: +50 OWPC!")

    elif query.data == "view_stats":
        await query.message.edit_caption(caption=f"📊 **HIVE STATUS**\n\nRank: {get_rank_info(score)[0]}\nTotal Credits: {score:,} PTS", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "get_invite":
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        await query.message.edit_caption(caption=f"🔗 **REFERRAL**\nInvite friends and earn 100 PTS.\n\n`{link}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "view_lb":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT name, points FROM users ORDER BY points DESC LIMIT 5")
        top = c.fetchall(); conn.close()
        txt = "🏛️ **TOP COMMANDERS**\n\n" + "\n".join([f"👑 {u[0]} — {u[1]:,} PTS" for u in top])
        await query.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if res and res[1] == today:
            await query.message.reply_text("⏳ Come back tomorrow!")
        else:
            win = random.randint(20, 100)
            update_user_db(uid, name, score_inc=win, daily=today)
            await query.message.reply_text(f"🎰 Lucky Draw: +{win} PTS!")

# --- MAIN ---
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("One World Peace Coins Bot is online.")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
