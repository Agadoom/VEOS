import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import openai

# ===== VARIABLES DYNAMIQUES VIA RAILWAY =====
TOKEN = os.environ.get("TOKEN")  # Telegram Bot Token
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GROUP_ID = os.environ.get("GROUP_ID")  # Groupe Telegram pour signaux
OWPC_PRICE = os.environ.get("OWPC_PRICE", "0.0001")
OWPC_HOLDERS = os.environ.get("OWPC_HOLDERS", "12")
OWPC_VOLUME = os.environ.get("OWPC_VOLUME", "907")
OWPC_SIGNAL = os.environ.get("OWPC_SIGNAL", "Early Whale Activity Detected!")
TELEGRAM_LINK = os.environ.get("TELEGRAM_LINK", "https://t.me/OWPC_early")

openai.api_key = OPENAI_API_KEY

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
            f"📊 OWPC Market (Pre-Launch)\n\n"
            f"💰 Price: ${OWPC_PRICE}\n"
            f"👥 Holders: {OWPC_HOLDERS}\n"
            f"🔄 Volume: {OWPC_VOLUME}\n"
            f"📈 Trend: Bullish 🟢\n\n"
            f"Stay early. Early whales are positioning."
        )

    elif data == "ai":
        text = "🧠 AI Crypto Assistant\n\nAsk me anything about OWPC or crypto.\n💬 Type your question below..."

    elif data == "signals":
        text = f"📢 Early Signals\n\n{OWPC_SIGNAL}\n🚀 Limited spots for early positioning\n👥 Smart money accumulating"

    elif data == "buy":
        text = f"🔥 Early Access to OWPC\n\nToken not publicly listed yet.\n📩 Contact team for allocation: {TELEGRAM_LINK}\n⚠️ Only limited positions available"

    elif data == "wallet":
        text = "💰 Wallet Dashboard\n\nComing soon...\n🔐 Track assets\n📊 Portfolio insights"

    elif data == "settings":
        text = "⚙️ Settings\n\n🔔 Notifications: ON\n🌍 Language: EN"

    else:
        text = "Unknown option."

    await query.edit_message_text(text=text, reply_markup=main_menu())

# ===== AI RESPONSE =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    try:
        # Requête OpenAI
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=f"Give a short crypto market insight based on: {user_text}",
            max_tokens=100,
            temperature=0.7
        )
        answer = response.choices[0].text.strip()
    except Exception:
        answer = "🤖 AI Response:\nCrypto market is volatile. Always do your own research."

    await update.message.reply_text(answer)

# ===== SEND SIGNAL AUTOMATIQUE =====
async def send_signal(context: ContextTypes.DEFAULT_TYPE):
    signal_text = f"📢 WHALE SIGNAL\n\n{OWPC_SIGNAL}\n🚀 Limited early positions!"
    await context.bot.send_message(chat_id=GROUP_ID, text=signal_text)

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Timer automatique pour signals (ex: toutes les 6h)
    app.job_queue.run_repeating(send_signal, interval=21600, first=10)

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()