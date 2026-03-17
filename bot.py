import os
import asyncio
import nest_asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import openai  # ← changement ici

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY  # ← configure la clé API

if not TOKEN:
    print("❌ TOKEN Telegram manquant")
    exit()
if not OPENAI_API_KEY:
    print("❌ OPENAI_API_KEY manquant")
    exit()

# -------- DATA --------
user_messages = defaultdict(list)

# ---- Links / Tokens ----
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"

LOGO = "owpc_logo.png"
GIF_LAUNCH = "gif.gif"

# -------- COMMANDS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("GENESIS 🧬", url=LINK_GENESIS)],
        [InlineKeyboardButton("UNITY 💎", url=LINK_UNITY)],
        [InlineKeyboardButton("VEO ⚡", url=LINK_VEO)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_photo(
        photo=open(LOGO, "rb"),
        caption="🕊️ **Welcome to OWPC Ecosystem**\nUse the buttons below to buy tokens 🚀",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    await update.message.reply_animation(animation=open(GIF_LAUNCH, "rb"))

# -------- AI Chat Handler --------
async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    try:
        response = openai.ChatCompletion.create(
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
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat))
    print("🚀 OWPC Bot running with AI + GIF + logo")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())