import os
import re
import asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Optional: AI integration
try:
    import openai
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    openai.api_key = OPENAI_API_KEY
    AI_ENABLED = True if OPENAI_API_KEY else False
except ModuleNotFoundError:
    AI_ENABLED = False

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN manquant")
    exit()

# ---------------- COMMANDES ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🌐 VEO Website", url="https://deeptrade.bio.link"),
            InlineKeyboardButton("🚀 Base Rewards VEO", url="https://base.app/rewards/post/0xf3db9c0c76155134fbb42a772d2563ff8cdb6576/2026-03-09-15-00?wa=0xf3db9c0c76155134fbb42a772d2563ff8cdb6576&n=networks%2Fbase-mainnet&ca=0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191&c=EUR"),
        ],
        [
            InlineKeyboardButton("🌸 Blum Mini App VEO", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA")
        ],
        [
            InlineKeyboardButton("🚀 UNITY Mini App", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome to the VEO & UNITY crypto hub!\n\n"
        "🚀 Community-driven meme cryptos\n"
        "🌍 Part of One World Peace Coins (OWPC)\n\n"
        "Use /links to see all official links and contracts.",
        reply_markup=reply_markup
    )

async def veos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 *VEO*\nCommunity-driven meme crypto\n🌍 Part of One World Peace Coins ecosystem",
        parse_mode="Markdown"
    )

async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌐 VEO Website", url="https://deeptrade.bio.link")],
        [InlineKeyboardButton("🚀 Base Rewards VEO", url="https://base.app/rewards/post/0xf3db9c0c76155134fbb42a772d2563ff8cdb6576/2026-03-09-15-00?wa=0xf3db9c0c76155134fbb42a772d2563ff8cdb6576&n=networks%2Fbase-mainnet&ca=0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191&c=EUR")],
        [InlineKeyboardButton("🌸 Blum Mini App VEO", url="https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA")],
        [InlineKeyboardButton("🚀 UNITY Mini App", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "🔗 Official Links & Contract Addresses\n\n"
        "💠 VEO Base CAD:\n0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191\n\n"
        "💎 VEO Blum CAD:\nEQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt\n\n"
        "💠 UNITY CAD:\nEQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"
    )
    await update.message.reply_text(text, reply_markup=reply_markup)

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📢 Invite friends and grow the VEO & UNITY community 🚀")

# ---------------- WELCOME ----------------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        try:
            await update.message.reply_text(
                f"👋 Welcome {member.first_name}!\n"
                "🚀 Welcome to the VEO & UNITY crypto hub\n"
                "🌍 Part of One World Peace Coins ecosystem\n\n"
                "Use /links to get official links and CADs."
            )
        except:
            pass

# ---------------- AUTO CAD RESPONSE ----------------
async def auto_ca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "ca" in text or "contract" in text:
        await update.message.reply_text(
            "💠 VEO Contract Address\n"
            "Base: 0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191\n"
            "Blum: EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt\n\n"
            "💠 UNITY Contract Address\nEQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"
        )

# ---------------- AI RESPONSE ----------------
async def ai_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not AI_ENABLED:
        return
    text = update.message.text
    if len(text.strip()) < 2:
        return
    try:
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=f"Answer this question in the context of VEO & UNITY crypto: {text}",
            temperature=0.7,
            max_tokens=150
        )
        answer = response.choices[0].text.strip()
        if answer:
            await update.message.reply_text(answer)
    except Exception as e:
        print("AI error:", e)

# ---------------- ANTI-SPAM ----------------
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
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veos", veos))
    app.add_handler(CommandHandler("links", links))
    app.add_handler(CommandHandler("invite", invite))

    # Welcome
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # Auto CA + AI
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_ca))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_response))

    # Anti-spam
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam))

    # Telegram bot commands
    await app.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("veos", "About VEO"),
        BotCommand("links", "Official links & CAD"),
        BotCommand("invite", "Invite people"),
    ])

    print("🚀 Bot démarré")
    await app.run_polling(drop_pending_updates=True)  # fix conflict

# ---------------- RUN ----------------
if __name__ == "__main__":
    asyncio.run(main())