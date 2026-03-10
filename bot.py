from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

import os
from collections import defaultdict

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN manquant")
    exit()

# ---------------- COMMANDES ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🌐 Website", url="https://deeptrade.bio.link"),
            InlineKeyboardButton("🚀 Base Rewards", url="https://base.app/rewards/post/0xf3db9c0c76155134fbb42a772d2563ff8cdb6576/2026-03-09-15-00?wa=0xf3db9c0c76155134fbb42a772d2563ff8cdb6576&n=networks%2Fbase-mainnet&ca=0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191&c=EUR")
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
        "🚀 VEO\n\nCommunity-driven meme crypto\nBuilt for the One World Peace Coins ecosystem 🌍"
    )


async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌐 Website", url="https://deeptrade.bio.link")],
        [InlineKeyboardButton("🚀 Base Rewards", url="https://base.app/rewards/post/0xf3db9c0c76155134fbb42a772d2563ff8cdb6576/2026-03-09-15-00?wa=0xf3db9c0c76155134fbb42a772d2563ff8cdb6576&n=networks%2Fbase-mainnet&ca=0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191&c=EUR")],
        [InlineKeyboardButton("🌸 Blum Mini App", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "🔗 VEO Official Links\n\n"
        "💠 Coinbase / Base CA:\n0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191\n\n"
        "💎 Blum CA:\nEQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt"
    )
    await update.message.reply_text(text, reply_markup=reply_markup)


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
        except:
            pass


# ---------------- ANTI SPAM ----------------

user_messages = defaultdict(list)

async def anti_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    text = update.message.text or ""
    allowed_links = [
        "deeptrade.bio.link",
        "base.app",
        "t.me/blum"
    ]
    if "http" in text or "t.me" in text:
        if not any(link in text for link in allowed_links):
            try:
                await update.message.delete()
            except:
                pass
            return

    user_id = update.message.from_user.id
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 5:
        try:
            await update.message.delete()
        except:
            pass
        user_messages[user_id].clear()


# ---------------- BOT ----------------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("veos", veos))
app.add_handler(CommandHandler("links", links))
app.add_handler(CommandHandler("invite", invite))

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam))

print("🚀 Bot démarré")
app.run_polling()