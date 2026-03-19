import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 START MINING OWPC", url="https://t.me/OWPCsbot")],
        [InlineKeyboardButton("📢 Official Channel", url="https://t.me/OneWorldPeaceCoins")],
        [InlineKeyboardButton("🧬 Genesis (Blum)", url="https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1")],
        [InlineKeyboardButton("🌍 Unity (Blum)", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR")],
        [InlineKeyboardButton("🤖 Veo AI (Blum)", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK")],
        [InlineKeyboardButton("❓ How it works", callback_data="help")]
    ])
    
    msg = (
        "🕊️ **WELCOME TO OWPC INFO HUB**\n\n"
        "The official gateway to the One World Peace Coins ecosystem.\n\n"
        "🔹 **Mining:** Use our specialized bot to extract OWPC.\n"
        "🔹 **Tokens:** Genesis, Unity, and Veo AI are live on Blum.\n\n"
        "Click below to start your journey."
    )
    await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "help":
        txt = "📖 **GUIDE**\n\n1. Launch @OWPCsbot to mine.\n2. Collect tokens daily.\n3. Check Hall of Fame for rankings."
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back")]]), parse_mode="Markdown")
    elif query.data == "back":
        # On renvoie le menu principal
        await start(update, context)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(help_callback))
    print("✅ Info Bot is running...")
    app.run_polling()
