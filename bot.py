import os
import asyncio
import nest_asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN manquant")
    exit()

# -------- DATA --------
user_messages = defaultdict(list)

# ---- Contract Addresses ----
CA_GENESIS = "EQADd56FsTcaOntj-F-he1DUnkPVnsHx7WolQpWUuW6tl1eS"
CA_UNITY = "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"
CA_VEO = "EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt"

# ---- Buy Links ----
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"

# ---- Media ----
LOGO = "owpc_logo.png"
GIF_LAUNCH = "gif.gif"

# ---- Allowed links ----
allowed_links = [
    "deeptrade.bio.link",
    "base.app",
    "t.me/blum",
    "youtube.com/@deeptradex"
]

# -------- START COMMAND --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🕊️ **Welcome to OWPC Ecosystem**\n\n"
        "🧬 GENESIS | 💎 UNITY | ⚡ VEO\n\n"
        "🚀 Phase 2 is LIVE!\n"
        "Use /buy to get started\n\n"
        "🌐 Stay connected and grow with us!"
    )

    if os.path.exists(GIF_LAUNCH):
        await update.message.reply_animation(animation=open(GIF_LAUNCH, "rb"), caption=text)
    elif os.path.exists(LOGO):
        await update.message.reply_photo(photo=open(LOGO, "rb"), caption=text)
    else:
        await update.message.reply_text(text)

# -------- BUY COMMAND --------
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS)],
        [InlineKeyboardButton("💎 UNITY", url=LINK_UNITY)],
        [InlineKeyboardButton("⚡ VEO", url=LINK_VEO)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("💰 **Buy OWPC Tokens**", reply_markup=reply_markup, parse_mode="Markdown")

# -------- LINKS COMMAND --------
async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔗 **Official Links**\n\n"
        "🌐 Website: [Deeptrade.bio.link](https://deeptrade.bio.link)\n"
        "📺 YouTube: [Deeptradex](https://youtube.com/@deeptradex)\n"
        "💬 Community Telegram: [Join Here](https://t.me/+SQhKj-gWWmcyODY0)"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

# -------- WELCOME NEW MEMBERS --------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"👋 Welcome {member.first_name}!\nUse /start to see the OWPC ecosystem and /buy to get started 🚀"
        )

# -------- ANTI-SPAM --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    user_id = update.message.from_user.id
    text = (update.message.text or "").lower()

    # anti spam: max 5 messages par 30 sec
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try:
            await update.message.delete()
        except:
            pass
        user_messages[user_id].clear()
        return

    # anti scam links
    if any(link in text for link in ["http", ".com", ".xyz", "t.me"]):
        if not any(link in text for link in allowed_links):
            try:
                await update.message.delete()
            except:
                pass
            return

# -------- CALLBACK QUERY (if needed for buttons) --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer("Button clicked!")

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("links", links))

    # Welcome new members
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # Anti-spam handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # CallbackQuery handler
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 OWPC Bot running with GIF + logo + inline buttons...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())