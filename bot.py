import os
import re
import asyncio
import nest_asyncio
import openai
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

if not TOKEN or not OPENAI_API_KEY:
    print("❌ TOKEN ou OPENAI_API_KEY manquant")
    exit()

# -------- DATA --------
user_messages = defaultdict(list)

CA_BASE = "0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191"
CA_BLUM = "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"

allowed_links = [
    "deeptrade.bio.link",
    "base.app",
    "t.me/blum"
]

# -------- COMMANDS --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = (
        "👋 Welcome to VEO & UNITY\n\n"
        "🚀 Community driven crypto\n"
        "🌍 One World Peace Coins ecosystem\n\n"
        "Use /links for official links"
    )

    await update.message.reply_text(text)


async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = (
        "🔗 Official Links\n\n"
        f"💠 Base CA\n{CA_BASE}\n\n"
        f"💎 Blum CA\n{CA_BLUM}\n\n"
        "🌐 Website\nhttps://deeptrade.bio.link"
    )

    await update.message.reply_text(text)


async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📢 Invite friends and grow the VEO & UNITY community 🚀"
    )


# -------- WELCOME --------

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):

    for member in update.message.new_chat_members:

        await update.message.reply_text(
            f"👋 Welcome {member.first_name}\n\n"
            "🚀 Welcome to VEO & UNITY\n"
            "Use /links to see official links"
        )


# -------- AI CHAT --------

async def ask_ai(prompt):

    try:

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful crypto community assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )

        return response["choices"][0]["message"]["content"]

    except Exception as e:

        print("AI error:", e)
        return "🤖 AI temporarily unavailable."


# -------- MESSAGE HANDLER --------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.from_user.is_bot:
        return

    text = (update.message.text or "").lower()
    user_id = update.message.from_user.id

    # -------- QUICK CRYPTO ANSWERS --------

    if "ca" in text or "contract" in text:

        await update.message.reply_text(
            f"💠 Contract Address\n\nBase:\n{CA_BASE}\n\nBlum:\n{CA_BLUM}"
        )
        return

    if "buy" in text:

        await update.message.reply_text(
            "🚀 Buy VEO / UNITY\n\n"
            "https://base.app\n"
            "or use Blum Mini App"
        )
        return

    if "price" in text:

        await update.message.reply_text(
            "📈 Price tracking coming soon.\nStay tuned 🚀"
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

    # -------- ANTI SCAM LINKS --------

    if re.search(r"http|t\.me|\.com|\.xyz", text):

        if not any(link in text for link in allowed_links):

            try:
                await update.message.delete()
            except:
                pass

            return

    # -------- AI RESPONSE --------

    reply = await ask_ai(text)

    await update.message.reply_text(f"🤖 {reply}")


# -------- MAIN --------

async def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("links", links))
    app.add_handler(CommandHandler("invite", invite))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 Bot démarré")

    await app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())