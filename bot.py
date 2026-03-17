import os
import re
import asyncio
import nest_asyncio
import openai
from datetime import datetime
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
)

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROUP_ID = os.getenv("GROUP_ID")  # Pour auto-hype

openai.api_key = OPENAI_API_KEY

if not TOKEN or not OPENAI_API_KEY:
    exit("❌ TOKEN ou OPENAI_API_KEY manquant")

AUTO_HYPE_ENABLED = bool(GROUP_ID)

# -------- DATA --------
user_messages = defaultdict(list)
user_activity = defaultdict(int)

ALLOWED_LINKS = [
    "deeptrade.bio.link",
    "base.app",
    "t.me/blum"
]

BUY_LINKS = {
    "GENESIS": "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA",
    "UNITY": "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA",
    "VEO": "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
}

OFFICIAL_LINKS = {
    "Website": "https://deeptrade.bio.link",
    "YouTube": "https://youtube.com/@deeptradex",
    "Telegram": "https://t.me/+SQhKj-gWWmcyODY0"
}

# -------- MENU INLINE --------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🧬 GENESIS", url=BUY_LINKS["GENESIS"]),
         InlineKeyboardButton("💎 UNITY", url=BUY_LINKS["UNITY"]),
         InlineKeyboardButton("⚡ VEO", url=BUY_LINKS["VEO"])],
        [InlineKeyboardButton("🌐 Links", callback_data="links"),
         InlineKeyboardButton("📢 Invite", callback_data="invite")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")]
    ]
    return InlineKeyboardMarkup(keyboard)

# -------- AI FUNCTION --------
async def ask_ai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional OWPC crypto assistant."},
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
    text = "🌍 Welcome to OWPC Ecosystem\n🧬 GENESIS | 💎 UNITY | ⚡ VEO\n🚀 Phase 2 is LIVE\nUse the menu below 👇"
    await update.message.reply_text(text, reply_markup=main_menu())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use the menu or type your question for AI support 🤖")

# -------- CALLBACK HANDLER --------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "links":
        text = "🌐 Official Links:\n" + "\n".join([f"{k}: {v}" for k, v in OFFICIAL_LINKS.items()])
        await query.edit_message_text(text=text, reply_markup=main_menu())

    elif data == "invite":
        text = "📢 Invite friends and grow the OWPC community 🚀\nhttps://t.me/+SQhKj-gWWmcyODY0"
        await query.edit_message_text(text=text, reply_markup=main_menu())

    elif data == "leaderboard":
        leaderboard = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:5]
        text = "🏆 Top Active Members:\n"
        for i, (user_id, score) in enumerate(leaderboard, start=1):
            try:
                user = await context.bot.get_chat(user_id)
                name = user.first_name
            except:
                name = str(user_id)
            text += f"{i}. {name} - {score} pts\n"

        # Envoyer avec GIF
        try:
            await query.message.reply_animation(
                animation=open("lv_0_20260310200554.gif", "rb"),
                caption=text,
                reply_markup=main_menu()
            )
            await query.message.delete()
        except Exception as e:
            print("Error sending leaderboard GIF:", e)
            await query.edit_message_text(text=text, reply_markup=main_menu())
    else:
        text = "🌍 OWPC Menu"
        await query.edit_message_text(text=text, reply_markup=main_menu())

# -------- MESSAGE HANDLER --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    text = (update.message.text or "").strip().lower()
    user_id = update.message.from_user.id
    user_activity[user_id] += 1

    # Anti-spam
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try: await update.message.delete()
        except: pass
        user_messages[user_id].clear()
        return

    # Anti-scam
    if re.search(r"http|t\.me|\.com|\.xyz", text):
        if not any(link in text for link in ALLOWED_LINKS):
            try: await update.message.delete()
            except: pass
            return

    # Quick buy command
    if "buy" in text:
        await update.message.reply_text("🚀 Buy OWPC Tokens 👇", reply_markup=main_menu())
        return

    if "links" in text:
        await update.message.reply_text("🌐 Official Links:", reply_markup=main_menu())
        return

    # AI response
    reply = await ask_ai(text)
    await update.message.reply_text(f"🤖 {reply}")

# -------- WELCOME NEW MEMBERS --------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        text = f"👋 Welcome {member.first_name}!\n🚀 Welcome to OWPC Ecosystem!\nUse /start to explore tokens and links."
        await update.message.reply_text(text, reply_markup=main_menu())

# -------- AUTO-HYPE IMAGE --------
async def auto_hype(app):
    if not AUTO_HYPE_ENABLED:
        return
    while True:
        try:
            await app.bot.send_photo(
                chat_id=int(GROUP_ID),
                photo=open("owpc_logo.png", "rb"),
                caption=(
                    "🚀 Phase 2 Hype!\n"
                    "Check GENESIS, UNITY, VEO and stay active in the community.\n"
                    "🌐 Use the menu below 👇"
                ),
                reply_markup=main_menu()
            )
        except Exception as e:
            print("Auto-hype error:", e)
        await asyncio.sleep(60*60)  # toutes les 60 minutes

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    asyncio.create_task(auto_hype(app))

    print("🚀 OWPC Ultimate Pro Bot started")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())