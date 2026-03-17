import os, asyncio, nest_asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from collections import defaultdict
from datetime import datetime, timedelta

nest_asyncio.apply()

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    exit("❌ TOKEN manquant")

# ----- DATA -----
user_messages = defaultdict(list)
LOGO = "https://i.ibb.co/2nQ0F2P/OWPC-golden-pigeon.png"

CA_GENESIS = "EQADd56FsTcaOntj-F-he1DUnkPVnsHx7WolQpWUuW6tl1eS"
CA_UNITY = "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"
CA_VEO = "EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt"

LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"

GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")  # ID du groupe Telegram pour auto-hype

# ----- COMMANDS -----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🕊️ **Welcome to OWPC Ecosystem**\n\n"
        "🧬 GENESIS | 💎 UNITY | ⚡ VEO\n\n"
        "🚀 Phase 2 is LIVE!\n"
        "Use /buy to get started\n\n"
        "🌐 Stay connected and grow with us!"
    )
    await update.message.reply_photo(photo=LOGO, caption=text, parse_mode="Markdown")

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
        "🌐 Website: [Deeptrade.bio.link](https://deeptrade.bio.link)\n"
        "📺 YouTube: [Deeptradex](https://youtube.com/@deeptradex)\n"
        "💬 Community Telegram: [Join Here](https://t.me/+SQhKj-gWWmcyODY0)"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📢 Invite friends and grow the OWPC community 🚀"
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

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"👋 Welcome {member.first_name}!\n"
            "Use /start to see the OWPC ecosystem and /buy to get started 🚀"
        )

# ----- ANTI-SPAM -----
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return
    user_id = update.message.from_user.id
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try: await update.message.delete()
        except: pass
        user_messages[user_id].clear()
        return

# ----- AUTO-HYPE -----
async def auto_hype(app):
    while True:
        if GROUP_CHAT_ID:
            text = (
                "🚀 **OWPC Phase 2 Live Reminder!**\n\n"
                "💎 UNITY & 🧬 GENESIS are progressing\n"
                "⚡ Don’t miss out, join the movement now!\n\n"
                "🌐 Links: /buy /links /ecosystem"
            )
            await app.bot.send_message(chat_id=int(GROUP_CHAT_ID), text=text, parse_mode="Markdown")
        await asyncio.sleep(1800)  # toutes les 30 minutes

# ----- MAIN -----
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("links", links))
    app.add_handler(CommandHandler("invite", invite))
    app.add_handler(CommandHandler("ecosystem", ecosystem))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 OWPC Pro Mini App Bot running...")
    asyncio.create_task(auto_hype(app))  # start auto-hype
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())