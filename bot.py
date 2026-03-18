import os
import asyncio
import sqlite3
import random
import nest_asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

nest_asyncio.apply()

# --- ⚙️ CONFIG ---
TOKEN = os.getenv("TOKEN") 
DB_PATH = "owpc_data.db" 
WEBAPP_URL = "https://veos-production.up.railway.app" 
LOGO_PATH = "media/owpc_logo.png"

# --- 📊 SYNCHRONIZED RANK LOGIC ---
def calculate_rank(points):
    if points >= 100000: return "💎 LEGEND"
    if points >= 50000:  return "👑 ELITE"
    if points >= 15000:  return "🎖️ COMMANDER"
    if points >= 5000:   return "⚔️ WARRIOR"
    if points >= 1000:   return "🛡️ GUARDIAN"
    return "🆕 SEEKER"

# --- 📊 DATABASE ACCESS ---
def get_user_full_data(user_id):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo, last_checkin, referrals FROM users WHERE user_id = ?", (user_id,))
        res = c.fetchone(); conn.close()
        if res:
            g = res[0] or 0
            u = res[1] or 0
            v = res[2] or 0.0
            total = g + u + v
            return {
                "genesis": g, "unity": u, "veo": v, "total": int(total),
                "last_checkin": res[3], "refs": res[4] or 0, "rank": calculate_rank(total)
            }
    except Exception as e:
        print(f"DB Error: {e}")
    return {"genesis": 0, "unity": 0, "veo": 0, "total": 0, "last_checkin": None, "refs": 0, "rank": "🆕 SEEKER"}

# --- ⌨️ KEYBOARDS ---
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb")],
        [InlineKeyboardButton("🆔 Passport", callback_data="my_card"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🔗 Invite", callback_data="get_invite")]
    ])

def back_btn(): return [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]

# --- 🛠️ HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Ensure user entry exists
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()
    
    data = get_user_full_data(user.id)
    cap = (f"🕊️ **OWPC PROTOCOL**\n"
           f"──────────────────\n"
           f"👤 **Commander:** {user.first_name}\n"
           f"🏆 **Rank:** {data['rank']}\n"
           f"💰 **Balance:** {data['total']:,} OWPC")
    
    if os.path.exists(LOGO_PATH):
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid, name = query.from_user.id, query.from_user.first_name
    
    # Validation tactile (petit feedback)
    await query.answer()
    
    data = get_user_full_data(uid)

    if query.data == "back_home":
        cap = (f"🕊️ **Main Menu**\n"
               f"Rank: {data['rank']}\n"
               f"Balance: {data['total']:,} OWPC")
        await query.message.edit_caption(caption=cap, reply_markup=main_menu_kb(), parse_mode="Markdown")

    elif query.data == "invest_hub":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS (Memepad)", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY (Memepad)", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI (Memepad)", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [back_btn()]
        ])
        await query.message.edit_caption(caption="💰 **INVEST HUB**\n\nUpgrade your protocol rank by acquiring assets.", reply_markup=kb)

    elif query.data == "view_stats":
        stats_text = (f"📊 **TERMINAL DATA**\n"
                      f"──────────────────\n"
                      f"🧬 Genesis: {data['genesis']:,} OWPC\n"
                      f"🌍 Unity: {data['unity']:,} OWPC\n"
                      f"🤖 Veo AI: {data['veo']:.2f} OWPC\n"
                      f"──────────────────\n"
                      f"🔥 **TOTAL: {data['total']:,} OWPC**")
        await query.message.edit_caption(caption=stats_text, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "my_card":
        card_text = (f"🆔 **OWPC PASSPORT**\n"
                     f"──────────────────\n"
                     f"Holder: {name}\n"
                     f"Rank: {data['rank']}\n"
                     f"Status: VERIFIED COMMANDER ✅\n"
                     f"Network: {data['refs']} nodes connected")
        await query.message.edit_caption(caption=card_text, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "get_invite":
        link = f"https://t.me/owpcsbot?start={uid}"
        invite_text = (f"🔗 **HIVE REFERRAL**\n\n"
                       f"Share your link to expand the network:\n"
                       f"`{link}`\n\n"
                       f"Current Hive Size: {data['refs']} members")
        await query.message.edit_caption(caption=invite_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if data['last_checkin'] == today:
            await query.message.reply_text("⏳ Security Protocol: Already claimed. Come back in 24h.")
        else:
            win = random.randint(75, 200)
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE users SET points_genesis = points_genesis + ?, last_checkin = ? WHERE user_id = ?", (win, today, uid))
            conn.commit(); conn.close()
            await query.message.reply_text(f"🎰 Lucky Draw Success!\n+{win} OWPC has been added to your Genesis balance.")
            # Refresh menu
            data_new = get_user_full_data(uid)
            await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nRank: {data_new['rank']}\nBalance: {data_new['total']:,} OWPC", reply_markup=main_menu_kb(), parse_mode="Markdown")

    elif query.data == "view_lb":
        await query.message.edit_caption(caption="🏛️ **HALL OF FAME**\n\nTop 10 Commanders ranking is currently being synchronized with the blockchain...", reply_markup=InlineKeyboardMarkup([back_btn()]))

# --- MAIN ---
async def main():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, points_genesis INTEGER DEFAULT 0, points_unity INTEGER DEFAULT 0, points_veo REAL DEFAULT 0.0, referrals INTEGER DEFAULT 0, rank TEXT, last_checkin TEXT)")
    conn.commit(); conn.close()
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("OWPC Terminal Sync Bot Online...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
