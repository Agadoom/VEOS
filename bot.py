import os
import re
from collections import defaultdict
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("❌ TOKEN manquant")
    exit()

# --------- COMMANDES ---------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to VEO community!\n\n"
        "Use /veos to learn about VEO\n"
        "Use /links for official links"
    )


async def veos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "VEO is a community-driven meme crypto 🚀\n"
        "Part of the One World Peace Coins ecosystem 🌍"
    )


async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
🔗 *VEO Official Links*

🌐 Website  
https://deeptrade.bio.link

🚀 Base Rewards  
https://base.app/rewards/post/0xf3db9c0c76155134fbb42a772d2563ff8cdb6576/2026-03-09-15-00?wa=0xf3db9c0c76155134fbb42a772d2563ff8cdb6576&n=networks%2Fbase-mainnet&ca=0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191&c=EUR

💠 Coinbase / Base CA  
`0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191`

🌸 Blum Mini App  
https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA

💎 Blum CA  
`EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt`
"""

    await update.message.reply_text(text, parse_mode="Markdown")

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📢 Invite friends and grow the VEO community 🚀"
    )


# --------- WELCOME ---------

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"Welcome {member.first_name}! 🚀\n"
            "You joined the VEO community.\n\n"
            "Start here 👉 https://deeptrade.bio.link"
        )


# --------- ANTI SPAM ---------

user_messages = defaultdict(list)

async def anti_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.from_user.is_bot:
        return

    text = update.message.text or ""

    # 🔹 blocage liens
    if re.search(r"http|t\.me|\.com|\.xyz", text.lower()):
        try:
            await update.message.delete()
        except:
            pass
        return

    # 🔹 anti flood
    user_id = update.message.from_user.id
    user_messages[user_id].append(update.message.date)

    if len(user_messages[user_id]) > 5:
        try:
            await update.message.delete()
        except:
            pass
        user_messages[user_id].clear()


# --------- BOT ---------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("veos", veos))
app.add_handler(CommandHandler("links", links))
app.add_handler(CommandHandler("invite", invite))

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam))


# --------- COMMANDES TELEGRAM ---------

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("veos", "About VEO"),
        BotCommand("links", "Official links"),
        BotCommand("invite", "Invite people"),
    ])


print("🚀 Bot démarré")
app.run_polling()