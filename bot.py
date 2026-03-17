import os
import re
import asyncio
import nest_asyncio
import openai
from collections import defaultdict
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

if not TOKEN or not OPENAI_API_KEY:
    print("❌ TOKEN ou OPENAI_API_KEY manquant")
    exit()

# -------- DATA --------
user_messages = defaultdict(list)
user_activity = defaultdict(int)       # messages + quiz points
quiz_active = {}                       # user_id -> {"answer": ""}
last_active = {}                       # user_id -> datetime of last message
holders_inactive_days = 3              # envoyer alertes si inactif > 3 jours

CA_BASE = "0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191"
CA_BLUM = "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"
allowed_links = ["deeptrade.bio.link","base.app","t.me/blum"]
GIF_PATH = "lv_0_20260310200554.gif"

# -------- COMMANDS --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA")],
        [InlineKeyboardButton("UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA")],
        [InlineKeyboardButton("VEO", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA")],
        [InlineKeyboardButton("Links", callback_data="links")],
        [InlineKeyboardButton("Invite", callback_data="invite")],
        [InlineKeyboardButton("Leaderboard", callback_data="leaderboard")],
        [InlineKeyboardButton("Quiz", callback_data="quiz")],
        [InlineKeyboardButton("Hype Alerts", callback_data="hype")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🌍 Welcome to OWPC Ultra Pro!\nChoose an option:", reply_markup=reply_markup)

# -------- CALLBACK BUTTONS --------

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "links":
        text = f"💠 Contract Addresses:\n\nBase:\n{CA_BASE}\nBlum:\n{CA_BLUM}\n\n🌐 Website:\nhttps://deeptrade.bio.link"
        await query.edit_message_text(text)
    elif data == "invite":
        text = "📢 Invite friends and grow the OWPC community 🚀\nhttps://t.me/+SQhKj-gWWmcyODY0"
        await query.edit_message_text(text)
    elif data == "leaderboard":
        leaderboard = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:5]
        text = "🏆 Top Active Members:\n"
        for i, (uid, pts) in enumerate(leaderboard, 1):
            try:
                user = await context.bot.get_chat(uid)
                name = user.first_name
            except:
                name = str(uid)
            text += f"{i}. {name} - {pts} pts\n"
        await query.edit_message_text(text)
        try:
            await context.bot.send_animation(chat_id=query.message.chat_id, animation=open(GIF_PATH, "rb"))
        except:
            pass
    elif data == "quiz":
        question, answer, options = "Which OWPC token has the Golden Pigeon logo?", "GENESIS", ["GENESIS","UNITY","VEO"]
        quiz_active[user_id] = {"answer": answer}
        keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz_{opt}")] for opt in options]
        await query.edit_message_text(question, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("quiz_"):
        choice = data.split("_")[1]
        correct = quiz_active.get(user_id, {}).get("answer")
        if correct:
            if choice == correct:
                user_activity[user_id] += 5
                await query.edit_message_text(f"✅ Correct! +5 pts 🎉")
            else:
                await query.edit_message_text(f"❌ Wrong! The correct answer was {correct}.")
            quiz_active.pop(user_id, None)
    elif data == "hype":
        # Liste holders inactifs
        now = datetime.now()
        inactive_users = [uid for uid, last in last_active.items() if now - last > timedelta(days=holders_inactive_days)]
        text = "⚡ Hype Alert for inactive holders:\n"
        if inactive_users:
            for uid in inactive_users:
                try:
                    user = await context.bot.get_chat(uid)
                    name = user.first_name
                except:
                    name = str(uid)
                text += f"- {name}\n"
        else:
            text += "All holders active! 🚀"
        await query.edit_message_text(text)

# -------- AI CHAT --------

async def ask_ai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":"You are a helpful crypto community assistant."},{"role":"user","content":prompt}],
            max_tokens=100,
            temperature=0.7
        )
        return response["choices"][0]["message"]["content"]
    except:
        return "🤖 AI temporarily unavailable."

# -------- MESSAGE HANDLER --------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    user_id = update.message.from_user.id
    text = (update.message.text or "").lower()

    last_active[user_id] = datetime.now()
    user_activity[user_id] += 1
    user_messages[user_id].append(update.message.date)

    # Anti spam
    if len(user_messages[user_id]) > 6:
        try: await update.message.delete()
        except: pass
        user_messages[user_id].clear()
        return

    if re.search(r"http|t\.me|\.com|\.xyz", text):
        if not any(link in text for link in allowed_links):
            try: await update.message.delete()
            except: pass
            return

    # Quick crypto answers
    if "ca" in text or "contract" in text:
        await update.message.reply_text(f"💠 Contract Addresses:\nBase: {CA_BASE}\nBlum: {CA_BLUM}")
        return
    if "buy" in text:
        await update.message.reply_text("🚀 Buy VEO / UNITY / GENESIS\nhttps://base.app\nor use Blum Mini App")
        return
    if "price" in text:
        await update.message.reply_text("📈 Price tracking coming soon. Stay tuned 🚀")
        return

    reply = await ask_ai(text)
    await update.message.reply_text(f"🤖 {reply}")

# -------- WELCOME --------

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(f"👋 Welcome {member.first_name}!\nUse /start to see the menu 🌍")

# -------- STATS --------

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    pts = user_activity.get(user_id, 0)
    await update.message.reply_text(f"📊 You have {pts} points 🌟")

# -------- MAIN --------

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_buttons))

    print("🚀 OWPC Ultra Pro Bot démarré")
    # Auto-hype JobQueue temporairement désactivé
     app.job_queue.run_repeating(auto_hype, interval=60*60*4, first=10)

    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())