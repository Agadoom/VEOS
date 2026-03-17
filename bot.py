import os
import re
import asyncio
import random
import nest_asyncio
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("❌ TOKEN manquant")
    exit()

# -------- DATA --------
user_messages = defaultdict(list)

# Contracts
GENESIS_CA = "EQADd56FsTcaOntj-F-he1DUnkPVnsHx7WolQpWUuW6tl1eS"
UNITY_CA = "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"
VEO_CA = "EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt"

# Links
GENESIS_LINK = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
UNITY_LINK = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
VEO_LINK = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"

WEBSITE = "https://deeptrade.bio.link"
YOUTUBE = "https://youtube.com/@deeptradex"
TELEGRAM = "https://t.me/+SQhKj-gWWmcyODY0"

allowed_links = [
    "deeptrade.bio.link",
    "t.me/blum",
    "youtube.com"
]

# -------- COMMANDS --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 Welcome to OWPC Ecosystem\n\n"
        "🧬 GENESIS | 💎 UNITY | ⚡ VEO\n\n"
        "🚀 Phase 2 is LIVE\n"
        "Use /buy to get started"
    )

async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔗 OFFICIAL LINKS\n\n"
        f"🌐 Website:\n{WEBSITE}\n\n"
        f"📺 YouTube:\n{YOUTUBE}\n\n"
        f"💬 Community:\n{TELEGRAM}"
    )

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 BUY OWPC ECOSYSTEM\n\n"

        "🧬 GENESIS\n"
        f"{GENESIS_CA}\n{GENESIS_LINK}\n\n"

        "💎 UNITY\n"
        f"{UNITY_CA}\n{UNITY_LINK}\n\n"

        "⚡ VEO\n"
        f"{VEO_CA}\n{VEO_LINK}\n\n"

        "🌍 You are still early.\n"
        "Strong holders build the future 💎"
    )

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ SELLING NOW?\n\n"
        "Most people sell before growth.\n"
        "Smart investors hold during quiet phases.\n\n"
        "🚀 Phase 2 just started.\n"
        "The real move hasn't begun."
    )

async def ecosystem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 OWPC ECOSYSTEM\n\n"
        "🧬 GENESIS → Foundation\n"
        "💎 UNITY → Community\n"
        "⚡ VEO → Expansion\n\n"
        "One vision. One future."
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 OWPC STATUS\n\n"
        "Phase: 2\n"
        "Development: Active\n"
        "Community: Growing\n\n"
        "We are building long-term 🌍"
    )

# -------- AUTO ACTIVITY --------

async def auto_hype(app):

    messages = [
        "🌍 OWPC is building silently...",
        "💎 Strong holders are accumulating...",
        "🚀 Phase 2 energy is rising...",
        "⚡ Big move can happen anytime 👀"
    ]

    while True:
        await asyncio.sleep(1800)

        try:
            await app.bot.send_message(
                chat_id=-100XXXXXXXXXX,  # ⚠️ METS TON CHAT ID
                text=random.choice(messages)
            )
        except:
            pass

# -------- MESSAGE HANDLER --------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.from_user.is_bot:
        return

    text = (update.message.text or "").lower()
    user_id = update.message.from_user.id

    # -------- QUICK TRIGGERS --------

    if "buy" in text:
        await buy(update, context)
        return

    if "sell" in text:
        await sell(update, context)
        return

    if "ca" in text:
        await update.message.reply_text(
            f"🧬 GENESIS:\n{GENESIS_CA}\n\n"
            f"💎 UNITY:\n{UNITY_CA}\n\n"
            f"⚡ VEO:\n{VEO_CA}"
        )
        return

    # -------- ANTI SPAM --------

    user_messages[user_id].append(update.message.date)

    if len(user_messages[user_id]) > 6:
        try:
            await update.message.delete()
        except:
            pass
        user_messages[user_id].clear()
        return

    # -------- ANTI SCAM --------

    if re.search(r"http|t\.me|\.com|\.xyz", text):
        if not any(link in text for link in allowed_links):
            try:
                await update.message.delete()
            except:
                pass
            return

# -------- MAIN --------

async def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("links", links))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("ecosystem", ecosystem))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 OWPC Bot Running")

    asyncio.create_task(auto_hype(app))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())