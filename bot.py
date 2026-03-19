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

# --- 📊 LOGIQUE DE DONNÉES ---
def get_user_full_data(user_id):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT points_genesis, points_unity, points_veo, last_checkin, referrals FROM users WHERE user_id = ?", (user_id,))
        res = c.fetchone(); conn.close()
        if res:
            g, u, v = (res[0] or 0), (res[1] or 0), (res[2] or 0.0)
            total = g + u + v
            return {"genesis": g, "unity": u, "veo": v, "total": int(total), "last_checkin": res[3], "refs": res[4] or 0}
    except: pass
    return {"genesis": 0, "unity": 0, "veo": 0, "total": 0, "last_checkin": None, "refs": 0}

def calculate_rank(points):
    if points >= 100000: return "💎 LEGEND"
    if points >= 50000:  return "👑 ELITE"
    if points >= 15000:  return "🎖️ COMMANDER"
    if points >= 5000:   return "⚔️ WARRIOR"
    if points >= 1000:   return "🛡️ GUARDIAN"
    return "🆕 SEEKER"

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest_hub"), InlineKeyboardButton("🏛️ Hall of Fame", callback_data="view_lb")],
        [InlineKeyboardButton("🆔 Passport", callback_data="my_card"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="daily")],
        [InlineKeyboardButton("📊 Stats", callback_data="view_stats"), InlineKeyboardButton("🔗 Invite", callback_data="get_invite")],
        [InlineKeyboardButton("📡 Live Feed", callback_data="live_feed"), InlineKeyboardButton("🗺️ Roadmap", callback_data="view_roadmap")]
    ])

def back_btn(): return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Retour au Menu", callback_data="back_home")]])

# --- 🛠️ HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit(); conn.close()
    
    data = get_user_full_data(user.id)
    rank = calculate_rank(data['total'])
    cap = f"🕊️ **OWPC PROTOCOL**\n\n👤 **Commander:** {user.first_name}\n🏆 **Rank:** {rank}\n💰 **Balance:** {data['total']:,} OWPC"
    
    if os.path.exists(LOGO_PATH):
        await update.message.reply_photo(photo=open(LOGO_PATH, "rb"), caption=cap, parse_mode="Markdown", reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=main_menu_kb())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid, name = query.from_user.id, query.from_user.first_name

    if query.data == "back_home":
        data = get_user_full_data(uid)
        rank = calculate_rank(data['total'])
        await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nRank: {rank}\nBalance: {data['total']:,} OWPC", reply_markup=main_menu_kb(), parse_mode="Markdown")

    # FIX PASSPORT
    elif query.data == "my_card":
        data = get_user_full_data(uid)
        rank = calculate_rank(data['total'])
        txt = (f"🆔 **OWPC PASSPORT**\n\n"
               f"👤 Holder: {name}\n"
               f"🎖️ Rank: {rank}\n"
               f"📈 Network: {data['refs']} members\n"
               f"✅ Verification: SSL Encrypted")
        await query.message.edit_caption(caption=txt, reply_markup=back_btn())

    # FIX LUCKY DRAW
    elif query.data == "daily":
        data = get_user_full_data(uid)
        today = datetime.now().strftime("%Y-%m-%d")
        if data['last_checkin'] == today:
            await query.message.reply_text("⏳ Security: Accès déjà utilisé. Revenez dans 24h.")
        else:
            win = random.randint(50, 200)
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE users SET points_genesis = points_genesis + ?, last_checkin = ? WHERE user_id = ?", (win, today, uid))
            conn.commit(); conn.close()
            await query.message.reply_text(f"🎰 GAGNÉ ! +{win} OWPC ajoutés à votre compte Genesis.")
            # On rafraîchit l'affichage
            new_data = get_user_full_data(uid)
            rank = calculate_rank(new_data['total'])
            await query.message.edit_caption(caption=f"🕊️ **Main Menu**\nRank: {rank}\nBalance: {new_data['total']:,} OWPC", reply_markup=main_menu_kb(), parse_mode="Markdown")

    elif query.data == "invest_hub":
        invest_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
            [InlineKeyboardButton("🌍 UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
            [InlineKeyboardButton("🤖 VEO AI", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
            [InlineKeyboardButton("⬅️ Retour", callback_data="back_home")]
        ])
        await query.message.edit_caption(caption="💰 **INVEST HUB**\nChoisissez un pilier pour acquérir des actifs.", reply_markup=invest_kb)

    elif query.data == "view_stats":
        data = get_user_full_data(uid)
        stats = f"📊 **ASSETS**\n\nGenesis: {data['genesis']:,}\nUnity: {data['unity']:,}\nVeo: {data['veo']:.2f}\n\nTotal: {data['total']:,}"
        await query.message.edit_caption(caption=stats, reply_markup=back_btn())

    elif query.data == "get_invite":
        link = f"https://t.me/owpcsbot?start={uid}"
        await query.message.edit_caption(caption=f"🔗 **REFERRAL**\n\nPartagez votre lien :\n`{link}`", parse_mode="Markdown", reply_markup=back_btn())

    elif query.data == "view_lb" or query.data == "live_feed" or query.data == "view_roadmap":
        await query.message.edit_caption(caption="📡 Sync en cours...", reply_markup=back_btn())

# --- MAIN ---
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Bot OK - Prêt pour le déploiement final.")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
