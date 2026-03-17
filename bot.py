import os
import asyncio
import nest_asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
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

# ---- Media Locaux ----
LOGO = "owpc_logo.png"       # ton logo local
GIF_LAUNCH = "Iv_O_20260310200554.gif" # ton GIF local

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

    # On envoie le GIF puis le logo avec texte
    if update.message:
        await update.message.reply_animation(animation=open(GIF_LAUNCH, "rb"))
        await update.message.reply_photo(
            photo=open(LOGO, "rb"),
            caption=text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.message.reply_photo(
            photo=open(LOGO, "rb"),
            caption=text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

# -------- Les autres fonctions (buy, links, invite, ecosystem, welcome, handle_message, button_handler) restent identiques --------
# (tu peux copier la version précédente pour ces fonctions)

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Commandes
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", lambda u, c: asyncio.create_task(buy(u, c))))

    # Boutons inline
    app.add_handler(CallbackQueryHandler(button_handler))

    # Nouveaux membres
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # Anti-spam
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 OWPC Bot Ultra-Pro running with local media...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())