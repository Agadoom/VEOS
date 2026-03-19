import os, sqlite3, asyncio, uvicorn, random
from datetime import date, datetime, timedelta
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

# --- 📊 RANGS ---
def get_rank_info(total_points):
    if total_points < 50: return {"name": "🆕 NOVICE", "mult": 1.0, "next": 50}
    elif total_points < 250: return {"name": "🛠️ SPECIALIST", "mult": 2.5, "next": 250}
    elif total_points < 1000: return {"name": "⚡ EXTRACTOR", "mult": 5.0, "next": 1000}
    else: return {"name": "🐋 WHALE", "mult": 12.0, "next": 5000}

# --- 🗄️ DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, 
                  points_genesis REAL DEFAULT 0.0, points_unity REAL DEFAULT 0.0, 
                  points_veo REAL DEFAULT 0.0, referred_by INTEGER,
                  last_bonus TEXT DEFAULT '', tasks_sub_channel INTEGER DEFAULT 0,
                  wallet_address TEXT DEFAULT '', streak INTEGER DEFAULT 0, 
                  last_lucky TEXT DEFAULT '')''')
    
    # Migration pour le Lucky Draw (ajout colonne si absente)
    try: c.execute("ALTER TABLE users ADD COLUMN last_lucky TEXT DEFAULT ''")
    except: pass
    conn.commit(); conn.close()

def get_stats(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT points_genesis, points_unity, points_veo, last_bonus, tasks_sub_channel, wallet_address, streak, last_lucky FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    
    # Compteur Niveau 1
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,))
    lv1 = c.fetchone()[0]
    
    # Compteur Niveau 2 (Les gens invités par ceux que tu as invités)
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by IN (SELECT user_id FROM users WHERE referred_by=?)", (uid,))
    lv2 = c.fetchone()[0]
    
    conn.close()
    if res:
        total = sum(res[:3])
        return {
            "g": res[0], "u": res[1], "v": res[2], "total": total, 
            "rank": get_rank_info(total), "last_bonus": res[3], 
            "wallet": res[5], "streak": res[6], "last_lucky": res[7],
            "lv1": lv1, "lv2": lv2
        }
    return None

# --- 🤖 BOT LOGIC ---
async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    
    # Parrainage à l'inscription
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
        [InlineKeyboardButton("📊 My Network", callback_data="btn_stats"), InlineKeyboardButton("🔗 Invite", callback_data="btn_invite")],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="btn_invest")]
    ])
    
    text = f"🕊️ **OWPC PROTOCOL**\n\nRank: `{s['rank']['name']}`\nBalance: `{s['total']:.2f}` OWPC\nNetwork: `{s['lv1'] + s['lv2']}` members"
    
    if update.callback_query:
        await update.callback_query.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_photo(photo=open(LOGO_PATH, 'rb'), caption=text, reply_markup=kb, parse_mode="Markdown")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id
    s = get_stats(uid)

    if q.data == "btn_back":
        await start_menu(update, context)

    elif q.data == "btn_lucky":
        now = datetime.now()
        can_play = True
        if s['last_lucky']:
            last_play = datetime.fromisoformat(s['last_lucky'])
            if now < last_play + timedelta(hours=6): # LIMITE : 6 HEURES
                can_play = False
                wait_time = (last_play + timedelta(hours=6)) - now
                minutes = int(wait_time.total_seconds() // 60)
                await q.answer(f"⏳ Recharge en cours... Revient dans {minutes} min", show_alert=True)
        
        if can_play:
            win = round(random.uniform(0.05, 0.25), 2)
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("UPDATE users SET points_veo = points_veo + ?, last_lucky = ? WHERE user_id = ?", (win, now.isoformat(), uid))
            conn.commit(); conn.close()
            await q.answer(f"🎰 GAGNÉ : +{win} VEO AI!", show_alert=True)
            await start_menu(update, context)

    elif q.data == "btn_stats":
        txt = (
            f"📊 **MY NETWORK (2 LEVELS)**\n\n"
            f"👥 **Level 1** (Direct): `{s['lv1']}` friends\n"
            f"📩 **Level 2** (Indirect): `{s['lv2']}` friends\n\n"
            f"💰 **Rewards**:\n"
            f"L1: 10% extraction bonus\n"
            f"L2: 3% extraction bonus\n"
        )
        await q.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]]), parse_mode="Markdown")

    elif q.data == "btn_passport":
        progress = min(int((s['total'] / s['rank']['next']) * 10), 10)
        bar = "🟩" * progress + "⬜" * (10 - progress)
        txt = f"🆔 **PASSPORT**\n\nRank: {s['rank']['name']}\nStreak: {s['streak']} days\n\nProgress:\n{bar}\n`{s['total']:.2f} / {s['rank']['next']}`"
        await q.message.edit_caption(caption=txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]]), parse_mode="Markdown")

    elif q.data == "btn_daily":
        # (Logique Daily Streak identique à la V8...)
        await q.answer("Fonction Daily active", show_alert=False)
        await start_menu(update, context)

    elif q.data == "btn_invite":
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        txt = f"🔗 **INVITE & EARN**\n\nL1: 10% Commission\nL2: 3% Commission\n\nLink:\n`{link}`"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}")],[InlineKeyboardButton("⬅️ BACK", callback_data="btn_back")]])
        await q.message.edit_caption(caption=txt, reply_markup=kb, parse_mode="Markdown")

# --- 🌐 WEB APP API (2-LEVEL REWARDS) ---
@app.post("/update_points")
async def receive_points(request: Request):
    data = await request.json(); uid, token = data.get("user_id"), data.get("token")
    if uid and token:
        s = get_stats(uid); gain = 0.05 * s['rank']['mult']
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
