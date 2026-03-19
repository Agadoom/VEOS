import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 DÉMARRER LE MINAGE", url="https://t.me/OWPCsbot")],
        [InlineKeyboardButton("📢 Canal Officiel", url="https://t.me/TonCanal")],
        [InlineKeyboardButton("🌐 Site Web", url="https://tonsite.com")],
        [InlineKeyboardButton("❓ Aide & FAQ", callback_data="help")]
    ])
    await update.message.reply_text(
        "Welcome to **OWPC Info Hub** 🕊️\n\n"
        "I am your official guide. To start earning OWPC, click the button below to join our Mining Bot.",
        reply_markup=kb, parse_mode="Markdown"
    )

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "help":
        await query.message.edit_text("Contact support at: @TonSupportAdmin", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back")]]))
    elif query.data == "back":
        await start(update, context)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))
    app.run_polling()
