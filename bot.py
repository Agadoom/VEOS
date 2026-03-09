import os
import re
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ⚠️ Assurez-vous d'avoir mis votre TOKEN
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN manquant")
    exit()

# ---------------- COMMANDES ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌐 Website", url="https://deeptrade.bio.link")],
        [InlineKeyboardButton("🚀 Base Rewards", url="https://base.app/rewards/post/0xf3db9c0c76155134fbb42a772d2563ff8cdb6576/2026-03-09-15-00?wa=0xf3db9c0c76155134fbb42a772d2563ff8cdb6576&n=networks%2Fbase-mainnet&ca=0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191&c=EUR")],
        [InlineKeyboardButton("🌸 Blum Mini App", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA")]
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
        "🚀 *VEO*\nCommunity driven meme crypto\nPart of One World Peace Coins ecosystem 🌍",
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
        "🔗 VEO Official Links\n\n"
        "💠 Coinbase / Base CA: 0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191\n"
        "💎 Blum CA: EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt"
    )
    await update.message.reply_text(text, reply_markup=reply_markup)

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📢 Invite friends and grow the VEO community 🚀")

# ---------------- WELCOME ----------------

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"👋 Welcome {member.first_name}!\n"
            "🚀 Welcome to the VEO community\n"
            "🌍 One World Peace Coins ecosystem\n\n"
            "Use /links to get official links"
        )

# ---------------- AI RESPONSE ----------------

async def ai_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    # Réponses simples d'AI pour exemple, à remplacer par intégration réelle d'OpenAI si voulu
    ai_dict = {
        "ca": "💠 VEO Contract Address:\nBase: 0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191\nBlum: EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt",
        "unity": "🚀 UNITY is live! Invest early and HODL strong: https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA",
        "ai": "🤖 Our bot will soon integrate AI to improve your investment experience in OWPC ecosystem!"
    }

    for key, response in ai_dict.items():
        if key in text:
            await update.message.reply_text(response)
            return

# ---------------- ANTI SPAM ----------------

user_messages = defaultdict(list)

async def anti_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    text = update.message.text or ""
    allowed_links = ["deeptrade.bio.link", "base.app", "t.me/blum"]

    if re.search(r"http|t\.me|\.com|\.xyz", text.lower()):
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
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_response))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam))

print("🚀 Bot started and ready!")
app.run_polling()