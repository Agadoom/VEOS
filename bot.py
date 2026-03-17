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
GROUP_ID = os.getenv("GROUP_ID")

if not TOKEN or not OPENAI_API_KEY:
    print("❌ TOKEN ou OPENAI_API_KEY manquant")
    exit()

openai.api_key = OPENAI_API_KEY

# -------- DATA --------
user_messages = defaultdict(list)
user_points = defaultdict(int)

GIF_FILE = "lv_0_20260310200554.gif"

CA_BASE = "0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191"
CA_BLUM = "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"

allowed_links = ["deeptrade.bio.link", "base.app", "t.me/blum"]

# -------- AI --------
async def ask_ai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a crypto community assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=80
        )
        return response["choices"][0]["message"]["content"]
    except:
        return "🤖 AI unavailable."

# -------- MENU --------
def get_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("GENESIS", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"),
            InlineKeyboardButton("UNITY", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"),
            InlineKeyboardButton("VEO", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA")
        ],
        [
            InlineKeyboardButton("Links 🔗", callback_data="links"),
            InlineKeyboardButton("Invite 📢", callback_data="invite")
        ],
        [
            InlineKeyboardButton("Leaderboard 🏆", callback_data="leaderboard"),
            InlineKeyboardButton("Hype 🔥", callback_data="hype")
        ]
    ])

# -------- START --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_animation(
        chat_id=update.effective_chat.id,
        animation=open(GIF_FILE, "rb"),
        caption="🌍 Welcome to OWPC 🚀\nChoose an option below:",
        reply_markup=get_menu()
    )

# -------- WELCOME --------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await context.bot.send_animation(
            chat_id=update.effective_chat.id,
            animation=open(GIF_FILE, "rb"),
            caption=f"👋 Welcome {member.first_name} 🚀",
            reply_markup=get_menu()
        )

# -------- BUTTONS --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "links":
        await query.edit_message_text(
            "🔗 Official Links\n\n"
            "🌐 https://deeptrade.bio.link\n"
            "📺 https://youtube.com/@deeptradex\n"
            "💬 https://t.me/+SQhKj-gWWmcyODY0"
        )

    elif query.data == "invite":
        await query.edit_message_text("📢 Invite your friends and grow OWPC 🚀")

    elif query.data == "leaderboard":
        lines = ["🏆 Top Active Members:"]
        for i, (uid, pts) in enumerate(sorted(user_points.items(), key=lambda x: x[1], reverse=True), 1):
            try:
                user = await context.bot.get_chat(uid)
                name = user.first_name
            except:
                name = f"User {uid}"
            lines.append(f"{i}. {name} - {pts} pts")

        await query.edit_message_text("\n".join(lines))

    elif query.data == "hype":
        await query.edit_message_text("🔥 Stay active & HOLD your tokens 🚀")

# -------- MESSAGE --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    text = (update.message.text or "").lower()
    user_id = update.message.from_user.id

    # points
    user_points[user_id] += 1

    # anti-spam
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try:
            await update.message.delete()
        except:
            pass
        user_messages[user_id].clear()
        return

    # anti-scam
    if re.search(r"http|t\.me|\.com|\.xyz", text):
        if not any(link in text for link in allowed_links):
            try:
                await update.message.delete()
            except:
                pass
            return

    # réponses rapides
    if "ca" in text:
        await update.message.reply_text(f"💠 Base:\n{CA_BASE}\n\n💎 Blum:\n{CA_BLUM}")
        return

    if "buy" in text:
        await update.message.reply_text("🚀 Buy on Base or Blum Mini App")
        return

    # AI
    reply = await ask_ai(text)
    await update.message.reply_text(f"🤖 {reply}")

# -------- AUTO HYPE --------
async def auto_hype(context: ContextTypes.DEFAULT_TYPE):
    if GROUP_ID:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text="🚀 OWPC Hype Alert 🔥 Stay active & HOLD!"
        )

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if app.job_queue:
        app.job_queue.run_repeating(auto_hype, interval=14400, first=10)

    print("🚀 BOT ONLINE")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())