import logging
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import openai

# CONFIG
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TOKEN or not OPENAI_API_KEY:
    print("❌ TOKEN ou OPENAI_API_KEY manquant")
    exit(1)

openai.api_key = OPENAI_API_KEY

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# MENU ULTRA PRO
menu = [
    ["📊 Market", "🧠 AI Analyse"],
    ["💰 Wallet", "📢 Signal"],
    ["⚙️ Settings"]
]

reply_markup = ReplyKeyboardMarkup(menu, resize_keyboard=True)

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Welcome to VEO Crypto Bot\n\n"
        "Your all-in-one Web3 assistant.\n"
        "Choose an option below 👇",
        reply_markup=reply_markup
    )

# MARKET
async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Market data coming soon...")

# WALLET
async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 Wallet feature coming soon...")

# SIGNAL
async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📢 Signals coming soon...")

# SETTINGS
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ Settings panel coming soon...")

# AI
async def ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_text}]
        )

        reply = response.choices[0].message.content
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"❌ AI Error: {e}")

# ROUTER
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📊 Market":
        await market(update, context)

    elif text == "💰 Wallet":
        await wallet(update, context)

    elif text == "📢 Signal":
        await signal(update, context)

    elif text == "⚙️ Settings":
        await settings(update, context)

    elif text == "🧠 AI Analyse":
        await update.message.reply_text("💬 Send me your question...")

    else:
        await ai(update, context)

# MAIN
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()