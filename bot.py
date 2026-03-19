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

# --- 📊 DATABASE AUTO-REPAIR ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # On crée la table avec TOUTES les colonnes nécessaires si elle n'existe pas
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis INTEGER DEFAULT 0, points_unity INTEGER DEFAULT 0,
                  points_veo REAL DEFAULT 0.0, referrals INTEGER DEFAULT 0,
                  rank TEXT DEFAULT '🆕 SEEKER', last_checkin TEXT DEFAULT '')''')
    
    # Sécurité : On vérifie si les colonnes spécifiques existent (au cas où la table était vieille)
    c.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in c.fetchall()]
    if 'points_genesis' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN points_genesis INTEGER DEFAULT 0")
    if 'points_unity' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN points_unity INTEGER DEFAULT 0")
    if 'points_veo' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN points_veo REAL DEFAULT 0.0")
        
    conn.commit()
    conn.close()

def get_user_full_data(user_id):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo, last_checkin, referrals FROM users WHERE user_id = ?", (user_id,))
        res = c.fetchone(); conn.close()
        if res:
            g, u, v = (res[0] or 0), (res[1] or 0), (res[2] or 0.0)
            total = g + u + v
            return {
                "genesis": g, "unity": u, "veo": v, "total": int(total),
                "last_checkin": res[3], "refs": res[4] or 0, "rank": calculate_rank(total)
            }
    except: pass
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
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()
    
    data = get_user_full_data(user.id)
    cap = (f"🕊️ **OWPC PROTOCOL**\n\n"
           f"👤 **Commander:** {user.first_name}\n"
           f"🏆 **Rank:** {data['rank']}\n"
           f"💰 **Credits:** {data['total']:,} OWPC")
    
    # On force l'envoi du menu
    if os.path.exists(LOGO_PATH):
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Indispensable pour que le bouton ne "charge" pas dans le vide
    
    uid, name = query.from_user.id, query.from_user.first_name
    data = get_user_full_data(uid)

    if query.data == "back_home":
        cap = f"🕊️ **Main Menu**\nRank: {data['rank']}\nCredits: {data['total']:,} OWPC"
        await query.message.edit_caption(caption=cap, reply_markup=main_menu_kb(), parse_mode="Markdown")

    elif query.data == "view_stats":
        stats_text = (f"📊 **ASSETS DETAILS**\n\n"
                      f"🧬 Genesis: {data['genesis']:,}\n"
                      f"🌍 Unity: {data['unity']:,}\n"
                      f"🤖 Veo AI: {data['veo']:.2f}\n"
                      f"──────────────\n"
                      f"💰 Total: {data['total']:,} OWPC")
        await query.message.edit_caption(caption=stats_text, reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "my_card":
        await query.message.edit_caption(caption=f"🆔 **PASSPORT**\n\nHolder: {name}\nRank: {data['rank']}\nStatus: ACTIVE ✅", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "get_invite":
        link = f"https://t.me/owpcsbot?start={uid}"
        await query.message.edit_caption(caption=f"🔗 **REFERRAL**\n\nInvite link:\n`{link}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([back_btn()]))

    elif query.data == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        if data['last_checkin'] == today:
            await query.message.reply_text("⏳ Already claimed today!")
        else:
            win = random.randint(50, 150)
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE users SET points_genesis = points_genesis + ?, last_checkin = ? WHERE user_id = ?", (win, today, uid))
            conn.commit(); conn.close()
            await query.message.reply_text(f"🎰 Lucky Draw: +{win} OWPC!")

# --- MAIN ---
async def main():
    init_db() # On répare la DB au lancement
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot One World Peace Coins Online & Synced...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
