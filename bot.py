import os
import re
import logging
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN manquant")
    exit()

# Logging pour suivre les erreurs et actions
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- VARIABLES ----------------
user_messages = defaultdict(list)
allowed_links = ["deeptrade.bio.link", "base.app", "t.me/blum"]

# ---------------- COMMANDES ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🌐 Website", url="https://deeptrade.bio.link"),
            InlineKeyboardButton("🚀 Base Rewards", url="https://base.app/rewards/post/0xf3db9c0c76155134fbb42a772d2563ff8cdb6576/2026-03-09-15-00?wa=0xf3db9c0c76155134fbb42a772d2563ff8cdb6576&n=networks%2Fbase-mainnet&ca=0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191&c=EUR"),
        ],
        [
            InlineKeyboardButton("🌸 Blum Mini App", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome to the VEO community!\n\n"
        "🚀 Community-driven meme crypto\n"
        "🌍 Part of One World Peace Coins\n\n"
        "Use /links to see all official links",
        reply_markup=reply_markup
    )

async def veos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 *VEO*\n\n"
        "Community-driven meme crypto\n"
        "Built for the One World Peace Coins ecosystem 🌍",
        parse_mode="Markdown"
    )

async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌐 Website", url="https://deeptrade.bio.link")],
        [InlineKeyboardButton("🚀 Base Rewards", url="https://base.app/rewards/post/0xf3db9c0c76155134fbb42a772d2563ff8cdb6576/2026-03-09-15-00?wa=0xf3db9c0c76155134fbb42a772d2563ff8cdb6576&n=networks%2Fbase-mainnet&ca=0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191&c=EUR")],
        [InlineKeyboardButton("🌸 Blum Mini App", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "🔗 *VEO Official Links*\n\n"
        "💠 Coinbase / Base CA:\n"
        "`0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191`\n\n"
        "💎 Blum CA:\n"
        "`EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt`"
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📢 Invite friends and grow the VEO community 🚀")

# ---------------- WELCOME ----------------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        try:
            await update.message.reply_text(
                f"👋 Welcome {member.first_name}!\n\n"
                "🚀 Welcome to the VEO community\n"
                "🌍 One World Peace Coins ecosystem\n\n"
                "Use /links to get official links"
            )
        except Exception as e:
            logger.warning(f"Erreur welcome: {e}")

# ---------------- AUTO CA RESPONSE ----------------
async def auto_ca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "ca" in text or "contract" in text:
        await update.message.reply_text(
            "💠 VEO Contract Address\n\n"
            "Base:\n0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191\n\n"
            "Blum:\nEQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt"
        )

# ---------------- ANTI SPAM ----------------
async def anti_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return
    text = update.message.text or ""
    user_id = update.message.from_user.id

    # Blocage liens interdits
    if re.search(r"http|t\.me|\.com|\.xyz", text.lower()):
        if not any(link in text for link in allowed_links):
            try:
                await update.message.delete()
                logger.info(f"Message supprimé pour spam: {text}")
            except:
                pass
            return

    # Anti-flood
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 5:
        try:
            await update.message.delete()
            logger.info(f"Message flood supprimé de {user_id}")
        except:
            pass
        user_messages[user_id].clear()

# ---------------- BOT ----------------
app = ApplicationBuilder().token(TOKEN).build()

# Handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("veos", veos))
app.add_handler(CommandHandler("links", links))
app.add_handler(CommandHandler("invite", invite))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_ca))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam))

# Commandes visibles
app.bot.set_my_commands([
    BotCommand("start", "Start the bot"),
    BotCommand("veos", "About VEO"),
    BotCommand("links", "Official links"),
    BotCommand("invite", "Invite people"),
])

# ---------------- LANCEMENT ----------------
print("🚀 Bot démarré")
app.run_polling()