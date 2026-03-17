import os
import asyncio
import nest_asyncio
from datetime import datetime
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import openai

nest_asyncio.apply()

# -------- CONFIGURATION --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY
BOT_USERNAME = "OWPCinfo_bot" 

# -------- DATA STOCKAGE --------
user_scores = defaultdict(int) 
user_names = {}
last_daily = {} 
referred_users = set() 

# ---- Liens & Assets ----
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LOGO_PATH = "media/owpc_logo.png"
ROADMAP_PATH = "media/roadmap.png"

# -------- HELPERS : GRADES --------
def get_title(score):
    if score >= 1000: return "👑 Alpha Legend"
    if score >= 500:  return "💎 Unity Guardian"
    if score >= 100:  return "🛠️ Builder"
    return "🐣 Seeker"

# -------- COMMANDS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_names[user.id] = user.first_name
    
    if context.args and context.args[0].startswith("ref_"):
        referrer_id = int(context.args[0].replace("ref_", ""))
        if user.id != referrer_id and user.id not in referred_users:
            user_scores[referrer_id] += 50 
            referred_users.add(user.id)
            try: await context.bot.send_message(chat_id=referrer_id, text=f"🎉 New referral! +50 pts via {user.first_name}!")
            except: pass

    await update.message.reply_photo(
        photo=open(LOGO_PATH, "rb"),
        caption=f"🕊️ **OWPC Core v2.3**\n\nWelcome {user.first_name}!\nYour Rank: {get_title(user_scores[user.id])}\n\nUse the menu to explore the 3 pillars! 🚀",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def pillars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🏛️ **THE 3 PILLARS OF OWPC**\n\n"
        "💎 **UNITY**: Our collective strength. Building a global network of believers.\n"
        "⚡ **VEO**: Our engine of innovation. Researching the future of Web3.\n"
        "🧬 **GENESIS**: Our eternal foundation. Providing stability for the ecosystem.\n\n"
        "Which one are you building today? 🔥"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# -------- CALLBACK HANDLER --------
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("GENESIS 🧬", url=LINK_GENESIS),
         InlineKeyboardButton("UNITY 💎", url=LINK_UNITY),
         InlineKeyboardButton("VEO ⚡", url=LINK_VEO)],
        [InlineKeyboardButton("🌐 Links", callback_data="show_links"),
         InlineKeyboardButton("🏆 Leaderboard", callback_data="view_leaderboard")],
        [InlineKeyboardButton("📅 Daily Points", callback_data="daily_claim"),
         InlineKeyboardButton("🔗 Invite & Earn", callback_data="get_invite")]
    ])

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "view_leaderboard":
        sorted_users = sorted(user_scores.items(), key=lambda item: item[1], reverse=True)[:10]
        text = "🏆 **OWPC ACTIVITY LEADERBOARD**\n\n"
        for i, (uid, score) in enumerate(sorted_users, 1):
            name = user_names.get(uid, f"User_{uid}")
            rank = get_title(score)
            text += f"{i}. {name} ({rank}) — {score} pts\n"
        await query.message.reply_text(text, parse_mode="Markdown")

    elif query.data == "daily_claim":
        today = datetime.now().date()
        if last_daily.get(user_id) == today:
            await query.message.reply_text("⏳ Already claimed! Come back tomorrow.")
        else:
            user_scores[user_id] += 10
            last_daily[user_id] = today
            await query.message.reply_text(f"✅ +10 pts! Current Rank: {get_title(user_scores[user_id])}")

    elif query.data == "get_invite":
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        await query.message.reply_text(f"🔗 **YOUR INVITE LINK**\n\n`{ref_link}`\n\nEarn 50 pts per referral! 🚀", parse_mode="Markdown")

    elif query.data == "show_links":
        text = "🌐 **LINKS**\n🔹 [Website](https://deeptrade.bio.link)\n🔹 [Twitter](https://x.com/DeepTradeX)\n🔹 [YouTube](https://youtube.com/@deeptradex)"
        await query.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

# -------- IA & ACTIVITY --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text: return
    user_id = update.effective_user.id
    user_names[user_id] = update.effective_user.first_name
    user_scores[user_id] += 1 

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are the OWPC Alpha Bot. The user is currently a {get_title(user_scores[user_id])}. Be visionary."},
                {"role": "user", "content": update.message.text}
            ],
            max_tokens=150
        )
        await update.message.reply_text(response.choices[0].message.content)
    except: pass

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pillars", pillars))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 OWPC Bot v2.3 (Social Titles) running")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
