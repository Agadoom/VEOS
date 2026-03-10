import os
import re
import asyncio
from collections import defaultdict

import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------- ENV ----------------
TOKEN = os.getenv("TOKEN")  # ${{shared.TOKEN}}
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"] = "${{shared.OPENAI_API_KEY}}"

if not TOKEN or not OPENAI_API_KEY:
    print("❌ Missing TOKEN or OPENAI_API_KEY")
    exit()

openai.api_key = OPENAI_API_KEY

# ---------------- COMMANDS ----------------
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
        "🚀 *VEO*\nCommunity driven meme crypto\nBuilt for the One World Peace Coins ecosystem 🌍",
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
        "💠 Coinbase / Base CA\n0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191\n\n"
        "💎 Blum CA\nEQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt"
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

# ---------------- AUTO CA ----------------
async def auto_ca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "ca" in text or "contract" in text:
        await update.message.reply_text(
            "💠 VEO Contract Address\n\n"
            "Base:\n0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191\n\n"
            "Blum:\nEQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt"
        )

# ---------------- AI CHAT ----------------
async def ask_ai(prompt: str) -> str:
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        ))
        return response.choices[0].message.content
    except Exception as e:
        return "🤖 Sorry, AI is temporarily unavailable."

async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    # Ignore commands
    if user_text.startswith("/"):
        return
    reply = await ask_ai(user_text)
    await update.message.reply_text(f"🤖 {reply}")


import random
import datetime

# ---------------- AI ANNOUNCEMENTS ----------------
last_announcement_time = datetime.datetime.min
announcement_cooldown = datetime.timedelta(minutes=30)  # 1 message max toutes les 30 min

async def ai_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_announcement_time

    text = update.message.text.lower()
    triggers = ["invest", "unity", "veo", "hodl", "crypto"]

    # Ignore si aucun trigger
    if not any(word in text for word in triggers):
        return

    now = datetime.datetime.utcnow()
    if now - last_announcement_time < announcement_cooldown:
        return  # Cooldown actif

    # Générer un message d'annonce persuasif via OpenAI
    prompt = (
        "You are a friendly crypto community assistant. "
        "Write a short, enthusiastic Telegram message encouraging members to invest in the UNITY token and hold it. "
        "Mention it's part of One World Peace Coins ecosystem and emphasize early support benefits."
    )
    reply = await ask_ai(prompt)

    # Ajouter un petit emoji et style
    possible_emojis = ["🚀", "💎", "🌍", "🔥", "🕊️"]
    emoji = random.choice(possible_emojis)
    final_message = f"{emoji} {reply}"

    await update.message.reply_text(final_message)
    last_announcement_time = now




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

# Commands
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("veos", veos))
app.add_handler(CommandHandler("links", links))
app.add_handler(CommandHandler("invite", invite))
# AI announcements trigger
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_announcement))

# Welcome
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

# Auto CA / AI / Anti spam
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_ca))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, anti_spam))

# ---------------- RUN ----------------
print("🚀 Bot démarré")
app.run_polling(drop_pending_updates=True)