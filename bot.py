import os
import re
import asyncio
import nest_asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import openai

# ----------- ASYNCIO FIX FOR SERVERS -----------
nest_asyncio.apply()

# ----------- VARIABLES D'ENVIRONNEMENT -----------
TOKEN = os.getenv("TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

resp = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello, are you working?"}]
)
print(resp.choices[0].message.content)

if not TOKEN or not OPENAI_API_KEY:
    print("❌ TOKEN ou OPENAI_API_KEY manquant")
    exit()

# ----------- ANTI SPAM -----------
user_messages = defaultdict(list)
allowed_links = [
    "deeptrade.bio.link",
    "base.app",
    "t.me/blum"
]

# ----------- COMMANDES -----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌐 Website", url="https://deeptrade.bio.link"),
         InlineKeyboardButton("🚀 Base Rewards", url="https://base.app/rewards/post/0xf3db9c0c76155134fbb42a772d2563ff8cdb6576/2026-03-09-15-00?wa=0xf3db9c0c76155134fbb42a772d2563ff8cdb6576&n=networks%2Fbase-mainnet&ca=0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191&c=EUR")],
        [InlineKeyboardButton("🌸 Blum Mini App", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 Welcome to the VEO & UNITY community!\n\n"
        "🚀 Community-driven meme crypto\n"
        "🌍 Part of One World Peace Coins ecosystem\n\n"
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
        [InlineKeyboardButton("🌸 Blum Mini App", url="https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "🔗 VEO & UNITY Official Links\n\n"
        "💠 Base / Coinbase CAD:\n0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191\n\n"
        "💎 Blum CAD:\nEQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"
    )

    await update.message.reply_text(text, reply_markup=reply_markup)

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📢 Invite friends and grow the VEO & UNITY community 🚀")

# ----------- WELCOME NOUVEAUX MEMBRES -----------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"👋 Welcome {member.first_name}!\n\n"
            "🚀 Welcome to the VEO & UNITY community\n"
            "🌍 One World Peace Coins ecosystem\n\n"
            "Use /links to get official links"
        )

# ----------- AUTO CAD / AI RESPONSE -----------
async def auto_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").lower()
    user_id = update.message.from_user.id

    # CAD quick reply
    if "ca" in text or "contract" in text:
        await update.message.reply_text(
            "💠 VEO & UNITY Contract Addresses\n\n"
            "Base/Coinbase: 0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191\n"
            "Blum: EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"
        )
        return

    # AI reply
    try:
        resp = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": text}],
            temperature=0.7,
            max_tokens=200
        )
        answer = resp.choices[0].message.content
        await update.message.reply_text(f"🤖 {answer}")
    except Exception as e:
        await update.message.reply_text("🤖 Sorry, AI is temporarily unavailable.")

# ----------- ANTI SPAM -----------
async def anti_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    user_id = update.message.from_user.id
    user_messages[user_id].append(update.message.date)

    if len(user_messages[user_id]) > 5:
        try:
            await update.message.delete()
        except:
            pass
        user_messages[user_id].clear()

    # blocage liens non-officiels
    text = update.message.text or ""
    if re.search(r"http|t\.me|\.com|\.xyz", text.lower()):
        if not any(link in text for link in allowed_links):
            try:
                await update.message.delete()
            except:
                pass

# ----------- BOT INIT -----------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veos", veos))
    app.add_handler(CommandHandler("links", links))
    app.add_handler(CommandHandler("invite", invite))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_response))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam))

    print("🚀 Bot démarré")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())