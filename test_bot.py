import os, sqlite3, asyncio, uvicorn, random
from datetime import date, datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- ⚙️ CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "owpc_data.db"
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://veos-production.up.railway.app")
LOGO_PATH = "media/owpc_logo.png"
BOT_USERNAME = "OWPCsbot"

app = FastAPI()

# --- 📊 LOGIQUE DE PROGRESSION & RANGS ---
def get_rank_info(total_points):
    if total_points < 50:
        return {"name": "🆕 NOVICE", "mult": 1.0, "next": 50, "color": "⬜"}
    elif total_points < 250:
        return {"name": "🛠️ SPECIALIST", "mult": 2.5, "next": 250, "color": "🟩"}
    elif total_points < 1000:
        return {"name": "⚡ EXTRACTOR", "mult": 5.0, "next": 1000, "color": "🟦"}
    else:
        return {"name": "🐋 WHALE", "mult": 12.0, "next": 5000, "color": "🟨"}

# --- 🗄️ DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # Table principale
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, points_unity REAL DEFAULT 0.0, 
                  points_veo REAL DEFAULT 0.0, referred_by INTEGER,
                  last_bonus TEXT DEFAULT '', tasks_sub_channel INTEGER DEFAULT 0,
                  wallet_address TEXT DEFAULT '', streak INTEGER DEFAULT 0, xp INTEGER DEFAULT 0)''')
    
    # Vérification et ajout des colonnes si migration nécessaire
    try: c.execute("ALTER TABLE users ADD COLUMN streak INTEGER DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE users ADD COLUMN xp INTEGER DEFAULT 0")
    except: pass
    
    conn.commit(); conn.close()

def get_stats(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, last_bonus, tasks_sub_channel, wallet_address, streak, xp FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,))
    ref_count = c.fetchone()[0]
    conn.close()
    if res:
        total = sum(res[:3])
        rank = get_rank_info(total)
        return {
            "g": res[0], "u": res[1], "v": res[2], "total": total, 
            "rank": rank, "last_bonus": res[3], "task_sub": res[4], 
            "wallet": res[5], "ref": ref_count, "streak": res[6], "xp": res[7]
        }
    return None

# --- 🤖 BOT LOGIC ---
async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    
    # Parrainage
    ref_id = None
    if context.args:
        try:
            p_ref = int(context.args[0])
            if p_ref != user.id: ref_id = p_ref
        except: pass

    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name, referred_by) VALUES (?, ?, ?)", (user.id, user.first_name, ref_id))
    conn.commit(); conn.close()
    
    s = get_stats(user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="btn_daily"), InlineKeyboardButton("🆔 Passport", callback_data="btn_passport")],
        [InlineKeyboardButton("🏛️ Hall of Fame", callback_data="btn_hof"), InlineKeyboardButton("🎰 Lucky Draw", callback_data="btn_lucky")],
        [InlineKeyboardButton("🏆 Tasks Hub", callback_data="btn_tasks"), InlineKeyboardButton("👛 Wallet", callback_data="btn_wallet")],
        [InlineKeyboardButton("📊 My Stats", callback_data="btn_stats"), InlineKeyboardButton("🔗 Invite Friends", callback_data="btn_invite")],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="btn_invest")]
    ])
    
    text = (
        f"🕊️ **OWPC PROTOCOL**\n\n"
        f"Rank: `{s['rank']['name']}`\n"
        f"Balance: `{s['total']:.2f}` OWPC\n"
        f"🔥 Streak: `{s['streak']} Days`"
    )
    
    if update.callback_query:
        await update.callback_query.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_photo(photo=open(LOGO_PATH, 'rb'), caption=text, reply_markup=kb, parse_mode="Markdown")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id
    s = get_stats(uid)

    if q.data == "btn_back":
        await start_menu(update, context)

    elif q.data == "btn_daily":
        today = date.today()
        today_str = today.isoformat()
        
        if s['last_bonus'] == today_str:
            await q.answer("⏳ Already claimed today!", show_alert=True)
        else:
            # Calcul du Streak
            new_streak = 1
            if s['last_bonus']:
                last_d = date.fromisoformat(s['last_bonus'])
                if (today - last_d).days == 1: new_streak = s['streak'] + 1
            
            # Bonus = Base (1.0) * Mult Rang * (1 + Streak/10)
            bonus_base = 1.0 * s['rank']['mult']
            streak_bonus = bonus_base * (new_streak * 0.1)
            total_gain = bonus_base + streak_bonus
            
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE users SET points_genesis = points_genesis + ?, last_bonus = ?, streak = ? WHERE user_id = ?", (total_gain, today_str, new_streak, uid))
            conn.commit(); conn.close()
            await q.answer(f"🎁 +{total_gain:.2f} OWPC! (Streak: {new_streak}j)", show_alert=True)
            await start_menu(update, context)

    elif q.data == "btn_passport":
        # Barre de progression XP
        progress = min(int((s['total'] / s['rank']['next']) * 10), 10)
        bar = "🟩" * progress + "⬜" * (10 - progress)
        
        txt = (
            f"🆔 **OWPC DIGITAL PASSPORT**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 Holder: `{q.from_user.first_name}`\n"
            f"🔥 Current Streak: `{s['streak']} Days`\n"
            f"🏆 Rank: **{s['rank']['name']}**\n\n"
            f"📊 XP Progress to Next Level:\n"
            f"`{s['total']:.2f} / {s['rank']['next']}`\n"
            f"{bar}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✨ Extraction Power: `x{s['rank']['mult']}`"
        )
        await q.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]]), parse_mode="Markdown")

    elif q.data == "btn_stats":
        txt = (
            f"📊 **FINANCIAL ASSETS**\n\n"
            f"🔹 Genesis: `{s['g']:.2f}`\n"
            f"🔹 Unity: `{s['u']:.2f}`\n"
            f"🔹 Veo AI: `{s['v']:.2f}`\n\n"
            f"👥 Network: `{s['ref']} friends`"
        )
        await q.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]]), parse_mode="Markdown")

    elif q.data == "btn_invite":
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        share_url = f"https://t.me/share/url?url={link}&text=Join my OWPC mining network! 🕊️"
        txt = f"🔗 **INVITE FRIENDS**\n\nEarn 10% of their mining rewards!\n\nLink:\n`{link}`"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📤 Share with Friends", url=share_url)],[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]])
        await q.message.edit_caption(caption=txt, reply_markup=kb, parse_mode="Markdown")

    elif q.data == "btn_lucky":
        win = round(random.uniform(0.1, 0.4), 2)
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE users SET points_veo = points_veo + ? WHERE user_id = ?", (win, uid))
        conn.commit(); conn.close()
        await q.answer(f"🎰 System Breach: +{win} VEO!", show_alert=True)
        await start_menu(update, context)

    elif q.data == "btn_wallet":
        txt = "👛 **WALLET HUB**\n\nConnect your TON wallet for future airdrops.\n\nStatus: `Not Linked`"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Connect (Coming Soon)", callback_data="soon")],[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]])
        await q.message.edit_caption(caption=txt, reply_markup=kb, parse_mode="Markdown")
    
    elif q.data == "soon":
        await q.answer("🔒 Feature locked until TGE.", show_alert=True)

# --- 🌐 WEB APP API ---
@app.post("/update_points")
async def receive_points(request: Request):
    data = await request.json(); uid, token = data.get("user_id"), data.get("token")
    if uid and token:
        s = get_stats(uid); gain = 0.05 * s['rank']['mult']
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute(f"UPDATE users SET points_{token} = points_{token} + ? WHERE user_id = ?", (gain, uid))
        conn.commit(); conn.close()
        return {"status": "success", "new_balance": get_stats(uid)}

@app.get("/", response_class=HTMLResponse)
async def mini_app():
    return "<html><body style='background:#000;color:#0f0;text-align:center;'><h3>TERMINAL ONLINE</h3></body></html>"

# --- RUN ---
async def main():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start_menu))
    bot.add_handler(CallbackQueryHandler(handle_buttons))
    await bot.initialize(); await bot.start()
    asyncio.create_task(bot.updater.start_polling(drop_pending_updates=True))
    await uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()

if __name__ == "__main__":
    asyncio.run(main())
