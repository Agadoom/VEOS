import os
import asyncio
import nest_asyncio
from collections import defaultdict
from telegram import Update, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from openai import OpenAI

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TOKEN:
    print("❌ TOKEN Telegram manquant")
    exit()
if not OPENAI_API_KEY:
    print("❌ OPENAI_API_KEY manquant")
    exit()

# -------- DATA --------
user_messages = defaultdict(list)

# ---- Contract Addresses ----
CA_GENESIS = "EQADd56FsTcaOntj-F-he1DUnkPVnsHx7WolQpWUuW6tl1eS"
CA_UNITY = "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"
CA_VEO = "EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt"

# ---- Buy Links ----
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"

# ---- Media ----
LOGO = "owpc_logo.png"
GIF_LAUNCH = "gif.gif"

# ---- Allowed links ----
allowed_links = [
    "deeptrade.bio.link",
    "base.app",
    "t.me/blum",
    "youtube.com/@deeptradex"
]

# -------- AI Client --------
ai_client = OpenAI(api_key=OPENAI_API_KEY)

# -------- COMMANDS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Inline buttons pour les achats
    keyboard = [
        [InlineKeyboardButton("GENESIS 🧬", url=LINK_GENESIS)],
        [InlineKeyboardButton("UNITY 💎", url=LINK_UNITY)],
        [InlineKeyboardButton("VEO ⚡", url=LINK_VEO)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_photo(
        photo=open(LOGO, "rb"),
        caption="🕊️ **Welcome to OWPC Ecosystem**\nPhase 2 is LIVE!\nUse the buttons below to buy tokens 🚀",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

    # Animation GIF de lancement
    await update.message.reply_animation(animation=open(GIF_LAUNCH, "rb"))

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
        f"🌐 Website: [Deeptrade.bio.link](https://deeptrade.bio.link)\n"
        f"📺 YouTube: [Deeptradex](https://youtube.com/@deeptradex)\n"
        f"💬 Community Telegram: [Join Here](https://t.me/+SQhKj-gWWmcyODY0)"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📢 Invite friends and grow the OWPC community 🚀\nUse the links above and build the legacy!"
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

# -------- WELCOME NEW MEMBERS --------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"👋 Welcome {member.first_name}!\nUse /start to see the OWPC ecosystem and /buy to get started 🚀"
        )

# -------- ANTI-SPAM --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    user_id = update.message.from_user.id
    text = (update.message.text or "").lower()

    # anti spam: max 5 messages par 30 sec
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try:
            await update.message.delete()
        except:
            pass
        user_messages[user_id].clear()
        return

    # anti scam links
    if any(link in text for link in ["http", ".com", ".xyz", "t.me"]):
        if not any(link in text for link in allowed_links):
            try:
                await update.message.delete()
            except:
                pass
            return

# -------- AI CHAT HANDLER --------
async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    try:
        response = ai_client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": user_message}],
            max_tokens=300
        )
        answer = response.choices[0].message.content
        await update.message.reply_text(answer)
    except Exception as e:
        await update.message.reply_text(f"⚠️ AI error: {e}")

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("links", links))
    app.add_handler(CommandHandler("invite", invite))
    app.add_handler(CommandHandler("ecosystem", ecosystem))

    # Welcome new members
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # Anti-spam
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # AI chat
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat))

    print("🚀 OWPC Bot running with GIF + logo + inline buttons + AI...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())