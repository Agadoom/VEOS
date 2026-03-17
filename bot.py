import os
import re
import asyncio
import nest_asyncio
import openai
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

nest_asyncio.apply()

# -------- CONFIG / ENV --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

if not TOKEN or not OPENAI_API_KEY:
    print("❌ TOKEN ou OPENAI_API_KEY manquant")
    exit()

# -------- DATA --------
user_messages = defaultdict(list)

CA = {
    "GENESIS": "EQADd56FsTcaOntj-F-he1DUnkPVnsHx7WolQpWUuW6tl1eS",
    "UNITY": "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx",
    "VEO": "EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt"
}

BUY_LINKS = {
    "GENESIS": "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA",
    "UNITY": "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA",
    "VEO": "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
}

ALLOWED_LINKS = [
    "deeptrade.bio.link",
    "base.app",
    "t.me/blum"
]

OFFICIAL_LINKS = {
    "Website": "https://deeptrade.bio.link",
    "YouTube": "https://youtube.com/@deeptradex",
    "Telegram": "https://t.me/+SQhKj-gWWmcyODY0"
}

# -------- AI FUNCTION --------
async def ask_ai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional crypto community assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        print("AI error:", e)
        return "🤖 AI temporarily unavailable."

# -------- COMMANDS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("GENESIS", callback_data="buy_GENESIS"),
         InlineKeyboardButton("UNITY", callback_data="buy_UNITY"),
         InlineKeyboardButton("VEO", callback_data="buy_VEO")],
        [InlineKeyboardButton("Official Links", callback_data="links"),
         InlineKeyboardButton("Invite", callback_data="invite")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🌍 Welcome to OWPC Ecosystem\n\n🚀 Phase 2 is LIVE!\nUse the buttons below to navigate."
    await update.message.reply_text(text, reply_markup=reply_markup)

async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🔗 Official Links:\n"
    for name, url in OFFICIAL_LINKS.items():
        text += f"{name}: {url}\n"
    await update.message.reply_text(text)

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📢 Invite your friends to OWPC Ecosystem 🚀\n\n" \
           "https://t.me/+SQhKj-gWWmcyODY0"
    await update.message.reply_text(text)

# -------- INLINE BUTTON CALLBACK --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("buy_"):
        token = data.split("_")[1]
        link = BUY_LINKS.get(token)
        if link:
            await query.edit_message_text(f"💰 Buy {token} here:\n{link}")
    elif data == "links":
        await links(update, context)
    elif data == "invite":
        await invite(update, context)

# -------- MESSAGE HANDLER --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return

    text = (update.message.text or "").lower()
    user_id = update.message.from_user.id

    # Anti spam
    user_messages[user_id].append(update.message.date)
    if len(user_messages[user_id]) > 6:
        try:
            await update.message.delete()
        except:
            pass
        user_messages[user_id].clear()
        return

    # Anti scam
    if re.search(r"http|t\.me|\.com|\.xyz", text):
        if not any(link in text for link in ALLOWED_LINKS):
            try:
                await update.message.delete()
            except:
                pass
            return

    # Quick commands
    if "buy" in text:
        text_links = "\n".join([f"{k}: {v}" for k, v in BUY_LINKS.items()])
        await update.message.reply_text(f"💰 Buy OWPC Tokens:\n{text_links}")
        return

    if "links" in text:
        await links(update, context)
        return

    # AI response
    reply = await ask_ai(text)
    await update.message.reply_text(f"🤖 {reply}")

# -------- WELCOME --------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(f"👋 Welcome {member.first_name}!\nUse /start to explore OWPC Ecosystem.")

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("links", links))
    app.add_handler(CommandHandler("invite", invite))

    # Inline buttons
    app.add_handler(CallbackQueryHandler(button_handler))

    # Welcome new members
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 OWPC Pro Bot started")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())