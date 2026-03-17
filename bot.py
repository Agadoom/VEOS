import os
import asyncio
import nest_asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
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

# ---- Media ----
LOGO = "owpc_logo.png"
GIF_LAUNCH = "Iv_O_20260310200554.gif"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send GIF if exists, otherwise send logo, with welcome text."""
    text = (
        "🕊️ **Welcome to OWPC Ecosystem**\n\n"
        "🧬 GENESIS | 💎 UNITY | ⚡ VEO\n\n"
        "🚀 Phase 2 is LIVE!\n"
        "Use /buy to get started\n\n"
        "🌐 Stay connected and grow with us!"
    )

    # Vérifie si le GIF existe
    if os.path.exists(GIF_LAUNCH):
        try:
            await update.message.reply_animation(animation=open(GIF_LAUNCH, "rb"), caption=text, parse_mode="Markdown")
            return
        except Exception as e:
            print("❌ Impossible d'envoyer le GIF:", e)

    # Sinon, envoie le logo
    if os.path.exists(LOGO):
        try:
            await update.message.reply_photo(photo=open(LOGO, "rb"), caption=text, parse_mode="Markdown")
        except Exception as e:
            print("❌ Impossible d'envoyer le logo:", e)
    else:
        # Si rien n'existe, envoie juste le texte
        await update.message.reply_text(text, parse_mode="Markdown")

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

    # Envoie GIF puis logo
    if update.message:
        await update.message.reply_animation(animation=open(GIF_LAUNCH, "rb"))
        await update.message.reply_photo(
            photo=open(LOGO, "rb"),
            caption=text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

# -------- BUTTON HANDLER --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # ferme le chargement

    if query.data == "buy":
        await query.message.reply_text(
            f"💰 Buy OWPC Tokens:\n🧬 GENESIS: {LINK_GENESIS}\n💎 UNITY: {LINK_UNITY}\n⚡ VEO: {LINK_VEO}",
            disable_web_page_preview=True
        )
    elif query.data == "links":
        await query.message.reply_text(
            "🔗 Official Links:\n🌐 Website: https://deeptrade.bio.link\n📺 YouTube: https://youtube.com/@deeptradex\n💬 Telegram: https://t.me/+SQhKj-gWWmcyODY0",
            disable_web_page_preview=True
        )
    elif query.data == "invite":
        await query.message.reply_text(
            "📢 Invite friends and grow the OWPC community!"
        )
    elif query.data == "ecosystem":
        await query.message.reply_text(
            "🌍 OWPC Ecosystem Overview:\n🧬 GENESIS → Foundation\n💎 UNITY → Liquidity & staking\n⚡ VEO → Utility token"
        )

# -------- WELCOME NEW MEMBERS --------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"👋 Welcome {member.first_name}!\nUse /start to see the OWPC ecosystem 🚀"
        )

# -------- ANTI-SPAM --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return
    user_id = update.message.from_user.id
    text = (update.message.text or "").lower()

    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try: await update.message.delete()
        except: pass
        user_messages[user_id].clear()
        return

    if any(link in text for link in ["http", ".com", ".xyz", "t.me"]):
        if not any(link in text for link in allowed_links):
            try: await update.message.delete()
            except: pass
            return

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Commandes
    app.add_handler(CommandHandler("start", start))

    # Inline buttons
    app.add_handler(CallbackQueryHandler(button_handler))

    # Nouveaux membres
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # Anti-spam
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 OWPC Bot running with GIF + logo + inline buttons...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())