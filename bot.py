import os
import re
import asyncio
import nest_asyncio
import openai
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
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

CA_BASE = "0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191"
CA_BLUM_GENESIS = "EQADd56FsTcaOntj-F-he1DUnkPVnsHx7WolQpWUuW6tl1eS"
CA_BLUM_UNITY = "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"
CA_BLUM_VEO = "EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt"

ALLOWED_LINKS = [
    "deeptrade.bio.link",
    "base.app",
    "t.me/blum"
]

# -------- MENU BUTTONS --------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🧬 GENESIS", callback_data="genesis")],
        [InlineKeyboardButton("💎 UNITY", callback_data="unity")],
        [InlineKeyboardButton("⚡ VEO", callback_data="veo")],
        [InlineKeyboardButton("🌐 Links", callback_data="links")],
        [InlineKeyboardButton("📢 Invite", callback_data="invite")]
    ]
    return InlineKeyboardMarkup(keyboard)

# -------- COMMANDS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🌍 Welcome to OWPC Ecosystem\n"
        "🧬 GENESIS | 💎 UNITY | ⚡ VEO\n"
        "🚀 Phase 2 is LIVE\n\n"
        "Use the menu below to explore 👇"
    )
    await update.message.reply_text(text, reply_markup=main_menu())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use the menu or type your question for AI support 🤖")

# -------- CALLBACKS --------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "genesis":
        await query.edit_message_text(
            "🧬 GENESIS Token\nBuy here:\nhttps://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
        )
    elif data == "unity":
        await query.edit_message_text(
            "💎 UNITY Token\nBuy here:\nhttps://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
        )
    elif data == "veo":
        await query.edit_message_text(
            "⚡ VEO Token\nBuy here:\nhttps://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
        )
    elif data == "links":
        await query.edit_message_text(
            "🌐 Official Links:\n\n"
            "Website: https://deeptrade.bio.link\n"
            "YouTube: @deeptradex\n"
            "Community Telegram: https://t.me/+SQhKj-gWWmcyODY0"
        )
    elif data == "invite":
        await query.edit_message_text(
            "📢 Invite friends and grow the OWPC community 🚀"
        )

# -------- AI CHAT --------
async def ask_ai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful OWPC crypto assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        print("AI error:", e)
        return "🤖 AI temporarily unavailable."

# -------- MESSAGE HANDLER --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    text = (update.message.text or "").lower()
    user_id = update.message.from_user.id

    # -------- QUICK COMMANDS --------
    if "buy" in text:
        await update.message.reply_text(
            "🚀 Buy OWPC Tokens\n🧬 GENESIS | 💎 UNITY | ⚡ VEO\nUse the menu 👇",
            reply_markup=main_menu()
        )
        return

    # -------- ANTI-SPAM --------
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try:
            await update.message.delete()
        except:
            pass
        user_messages[user_id].clear()
        return

    # -------- ANTI-SCAM LINKS --------
    if re.search(r"http|t\.me|\.com|\.xyz", text):
        if not any(link in text for link in ALLOWED_LINKS):
            try:
                await update.message.delete()
            except:
                pass
            return

    # -------- AI RESPONSE --------
    reply = await ask_ai(text)
    await update.message.reply_text(f"🤖 {reply}")

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 OWPC Pro Bot started")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())