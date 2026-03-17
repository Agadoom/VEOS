import os
import asyncio
import nest_asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN manquant")
    exit()

# -------- DATA --------
user_messages = defaultdict(list)

# ---- Contract Addresses & Buy Links ----
TOKENS = {
    "GENESIS": {
        "contract": "EQADd56FsTcaOntj-F-he1DUnkPVnsHx7WolQpWUuW6tl1eS",
        "link": "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
    },
    "UNITY": {
        "contract": "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx",
        "link": "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
    },
    "VEO": {
        "contract": "EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt",
        "link": "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
    }
}

# ---- Media ----
LOGO = "https://i.ibb.co/2nQ0F2P/OWPC-golden-pigeon.png"

# ---- Allowed links ----
allowed_links = [
    "deeptrade.bio.link",
    "base.app",
    "t.me/blum",
    "youtube.com/@deeptradex"
]

# -------- COMMANDS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🧬 GENESIS", url=TOKENS["GENESIS"]["link"])],
        [InlineKeyboardButton("💎 UNITY", url=TOKENS["UNITY"]["link"])],
        [InlineKeyboardButton("⚡ VEO", url=TOKENS["VEO"]["link"])],
        [InlineKeyboardButton("🌐 Links", callback_data="links")],
        [InlineKeyboardButton("📢 Invite", callback_data="invite")],
        [InlineKeyboardButton("🌍 Ecosystem", callback_data="ecosystem")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "🕊️ **Welcome to OWPC Ecosystem**\n\n"
        "🧬 GENESIS | 💎 UNITY | ⚡ VEO\n\n"
        "🚀 Phase 2 is LIVE!\n"
        "Use the buttons below to explore and get started!"
    )
    await update.message.reply_photo(photo=LOGO, caption=text, parse_mode="Markdown", reply_markup=reply_markup)

# Callback handler for buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "links":
        text = (
            "🔗 **Official Links**\n\n"
            "🌐 Website: [Deeptrade.bio.link](https://deeptrade.bio.link)\n"
            "📺 YouTube: [Deeptradex](https://youtube.com/@deeptradex)\n"
            "💬 Community Telegram: [Join Here](https://t.me/+SQhKj-gWWmcyODY0)"
        )
        await query.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

    elif query.data == "invite":
        await query.message.reply_text(
            "📢 Invite friends and grow the OWPC community 🚀\n"
            "Use the links above and build the legacy!"
        )

    elif query.data == "ecosystem":
        text = (
            "🌍 **OWPC Ecosystem Overview**\n\n"
            "🧬 GENESIS → Foundation & long-term growth\n"
            "💎 UNITY → Main liquidity & staking\n"
            "⚡ VEO → Fast utility token\n\n"
            "🚀 Together they form a unified world crypto ecosystem!"
        )
        await query.message.reply_text(text, parse_mode="Markdown")

# -------- WELCOME NEW MEMBERS --------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_photo(
            photo=LOGO,
            caption=f"👋 Welcome {member.first_name}!\nUse /start to explore OWPC 🚀",
            parse_mode="Markdown"
        )

# -------- ANTI-SPAM --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    user_id = update.message.from_user.id
    text = (update.message.text or "").lower()

    # Anti-spam: max 5 messages per 30 sec
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try:
            await update.message.delete()
        except:
            pass
        user_messages[user_id].clear()
        return

    # Anti-scam links
    if any(link in text for link in ["http", ".com", ".xyz", "t.me"]):
        if not any(link in text for link in allowed_links):
            try:
                await update.message.delete()
            except:
                pass
            return

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))

    # Callback query handler for buttons
    app.add_handler(MessageHandler(filters.CallbackQuery.ALL, button_handler))

    # Welcome new members
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # Anti-spam handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 OWPC Bot PRO running...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())