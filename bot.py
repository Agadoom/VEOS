import os
import re
import asyncio
import nest_asyncio
import openai
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROUP_ID = os.getenv("GROUP_ID")  # pour auto-hype si nécessaire

if not TOKEN or not OPENAI_API_KEY:
    print("❌ TOKEN ou OPENAI_API_KEY manquant")
    exit()

openai.api_key = OPENAI_API_KEY

# -------- DATA --------
user_messages = defaultdict(list)

CA_BASE = "0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191"
CA_BLUM = "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"

allowed_links = [
    "deeptrade.bio.link",
    "base.app",
    "t.me/blum"
]

GIF_FILE = "lv_0_20260310200554.gif"

top_members = defaultdict(int)  # ex: user_id -> points

# -------- AI Chat --------
async def ask_ai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful crypto community assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        return response["choices"][0]["message"]["content"]
    except:
        return "🤖 AI temporarily unavailable."

# -------- COMMANDS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # GIF + message de bienvenue
    await context.bot.send_animation(
        chat_id=update.effective_chat.id,
        animation=open(GIF_FILE, "rb"),
        caption="🌍 Welcome to One World Peace Coins! 🚀\n\nChoose an option below:"
    )

    keyboard = [
        [
            InlineKeyboardButton("GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"),
            InlineKeyboardButton("UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"),
            InlineKeyboardButton("VEO", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA")
        ],
        [
            InlineKeyboardButton("Links", callback_data="links"),
            InlineKeyboardButton("Invite", callback_data="invite"),
            InlineKeyboardButton("Leaderboard", callback_data="leaderboard")
        ],
        [
            InlineKeyboardButton("Quiz", callback_data="quiz"),
            InlineKeyboardButton("Hype Alerts", callback_data="hype")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🏆 OWPC Menu:", reply_markup=reply_markup)

# -------- CALLBACKS --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "links":
        text = (
            "🔗 Official Links\n\n"
            "🌐 Website: https://deeptrade.bio.link\n"
            "📺 YouTube: https://youtube.com/@deeptradex\n"
            "💬 Telegram Community: https://t.me/+SQhKj-gWWmcyODY0"
        )
        await query.edit_message_text(text=text)

    elif query.data == "invite":
        await query.edit_message_text("📢 Invite friends and grow the VEO & UNITY community 🚀")

    elif query.data == "leaderboard":
        # Leaderboard dynamique
        lines = ["🏆 Top Active Members:"]
        for i, (uid, pts) in enumerate(sorted(top_members.items(), key=lambda x: x[1], reverse=True), 1):
            user = await context.bot.get_chat(uid)
            lines.append(f"{i}. {user.first_name} - {pts} pts")
        await query.edit_message_text("\n".join(lines) if lines else "No active members yet.")

    elif query.data == "quiz":
        await query.edit_message_text("📝 Quiz coming soon! Stay tuned 🚀")

    elif query.data == "hype":
        await query.edit_message_text("🔥 Hype alerts activated! Check back soon for updates.")

# -------- MESSAGE HANDLER --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    text = (update.message.text or "").lower()
    user_id = update.message.from_user.id

    # Track top members
    top_members[user_id] += 1

    # Anti-spam
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try: await update.message.delete()
        except: pass
        user_messages[user_id].clear()
        return

    # Anti-scam links
    if re.search(r"http|t\.me|\.com|\.xyz", text):
        if not any(link in text for link in allowed_links):
            try: await update.message.delete()
            except: pass
            return

    # AI response
    reply = await ask_ai(text)
    await update.message.reply_text(f"🤖 {reply}")

# -------- AUTO-HYPE --------
async def auto_hype(context: ContextTypes.DEFAULT_TYPE):
    if GROUP_ID:
        await context.bot.send_message(chat_id=GROUP_ID, text="🚀 OWPC Hype Alert! Remember to hold your tokens and stay active!")

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # JobQueue pour auto-hype
    if not app.job_queue:
        print("⚠️ JobQueue not available. Install python-telegram-bot[job-queue]")
    else:
        app.job_queue.run_repeating(auto_hype, interval=60*60*4, first=10)

    print("🚀 Bot démarré")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())