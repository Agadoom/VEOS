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
    exit(1)

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
    text = (
        "🕊️ **Welcome to OWPC Ecosystem**\n\n"
        "🧬 GENESIS | 💎 UNITY | ⚡ VEO\n\n"
        "🚀 Phase 2 is LIVE!\n"
        "Use the buttons below to explore and /buy to get started!\n\n"
        "🌐 Stay connected and grow with us!"
    )

    keyboard = [
        [InlineKeyboardButton("Buy Tokens 💰", callback_data="buy")],
        [InlineKeyboardButton("Official Links 🔗", callback_data="links")],
        [InlineKeyboardButton("Invite Friends 📢", callback_data="invite")],
        [InlineKeyboardButton("Ecosystem 🌍", callback_data="ecosystem")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_photo(
        photo=LOGO, caption=text, parse_mode="Markdown", reply_markup=reply_markup
    )

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💰 **Buy OWPC Tokens**\n\n"
        f"🧬 GENESIS: [Buy Here]({LINK_GENESIS})\n"
        f"💎 UNITY: [Buy Here]({LINK_UNITY})\n"
        f"⚡ VEO: [Buy Here]({LINK_VEO})\n\n"
        "🚀 Early holders build the future!"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔗 **Official Links**\n\n"
        f"🌐 Website: [Deeptrade.bio.link](https://deeptrade.bio.link)\n"
        f"📺 YouTube: [Deeptradex](https://youtube.com/@deeptradex)\n"
        f"💬 Community Telegram: [Join Here](https://t.me/+SQhKj-gWWmcyODY0)"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📢 Invite friends and grow the OWPC community 🚀\n"
        "Use the links above and build the legacy!"
    )

async def ecosystem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🌍 **OWPC Ecosystem Overview**\n\n"
        "🧬 GENESIS → Foundation & long-term growth\n"
        "💎 UNITY → Main liquidity & staking\n"
        "⚡ VEO → Fast utility token\n\n"
        "🚀 Together they form a unified world crypto ecosystem!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# -------- WELCOME NEW MEMBERS --------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"👋 Welcome {member.first_name}!\n"
            "Use /start to see the OWPC ecosystem and /buy to get started 🚀"
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

# -------- BUTTON HANDLER --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "buy":
        await query.message.reply_text(
            f"🧬 GENESIS: {LINK_GENESIS}\n💎 UNITY: {LINK_UNITY}\n⚡ VEO: {LINK_VEO}"
        )
    elif query.data == "links":
        await links(update, context)
    elif query.data == "invite":
        await invite(update, context)
    elif query.data == "ecosystem":
        await ecosystem(update, context)

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("links", links))
    app.add_handler(CommandHandler("invite", invite))
    app.add_handler(CommandHandler("ecosystem", ecosystem))

    # Welcome new members
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # Anti-spam handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # CallbackQuery handler for inline buttons
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 OWPC Bot PRO running...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())