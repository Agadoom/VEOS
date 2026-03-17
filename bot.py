from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = "YOUR_BOT_TOKEN_HERE"

# ===== MENU PRINCIPAL =====
def main_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Market", callback_data="market")],
        [InlineKeyboardButton("🧠 AI Analyse", callback_data="ai")],
        [InlineKeyboardButton("📢 Signals", callback_data="signals")],
        [InlineKeyboardButton("🔥 Buy OWPC", callback_data="buy")],
        [InlineKeyboardButton("💰 Wallet", callback_data="wallet")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🚀 Welcome to VEO Crypto Bot\n\n"
        "The smart gateway to the OWPC ecosystem 🌍\n\n"
        "📊 Live Market Data\n"
        "🧠 AI Crypto Analysis\n"
        "📢 Early Signals & Opportunities\n\n"
        "Start exploring now 👇"
    )
    await update.message.reply_text(text, reply_markup=main_menu())

# ===== CALLBACK HANDLER =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "market":
        text = (
            "📊 OWPC Market Overview\n\n"
            "💰 Price: $0.0001\n"
            "📈 Market Cap: $890K\n"
            "👥 Holders: 120\n"
            "🔄 Volume: $907\n\n"
            "📊 Trend: Bullish 🟢"
        )

    elif data == "ai":
        text = (
            "🧠 AI Crypto Assistant\n\n"
            "Ask me anything about OWPC or crypto.\n\n"
            "💬 Type your question below..."
        )

    elif data == "signals":
        text = (
            "📢 Early Signals\n\n"
            "🚀 OWPC Momentum Detected\n"
            "📊 Volume increasing\n"
            "👥 New holders rising\n\n"
            "🔥 Potential early entry zone"
        )

    elif data == "buy":
        text = (
            "🔥 Buy OWPC Now\n\n"
            "👉 https://your-link-here.com\n\n"
            "⚠️ Always DYOR"
        )

    elif data == "wallet":
        text = (
            "💰 Wallet Dashboard\n\n"
            "Coming soon...\n"
            "🔐 Track assets\n"
            "📊 Portfolio insights"
        )

    elif data == "settings":
        text = (
            "⚙️ Settings\n\n"
            "🔔 Notifications: ON\n"
            "🌍 Language: EN"
        )

    else:
        text = "Unknown option."

    await query.edit_message_text(text=text, reply_markup=main_menu())

# ===== AI RESPONSE (FAKE INTELLIGENCE POUR L’INSTANT) =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.lower()

    if "owpc" in user_text:
        response = (
            "📊 AI Insight:\n\n"
            "OWPC is an early-stage project with growth potential.\n"
            "Low market cap + increasing activity = opportunity.\n\n"
            "⚠️ High risk, high reward."
        )
    else:
        response = (
            "🤖 AI Response:\n\n"
            "Crypto market is volatile.\n"
            "Always do your own research."
        )

    await update.message.reply_text(response)

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()