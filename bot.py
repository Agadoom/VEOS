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
BOT_USERNAME = "OWPCinfo_bot" # ⚠️ Remplace par le vrai username de ton bot sans le @

# -------- DATA STOCKAGE --------
user_scores = defaultdict(int) 
user_names = {}
last_daily = {} # Stocke la date du dernier claim
referred_users = set() # Pour éviter de compter deux fois le même parrainage

# -------- LIENS & ASSETS --------
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"

LOGO_PATH = "media/owpc_logo.png"
ROADMAP_PATH = "media/roadmap.png"

# -------- KEYBOARDS --------
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

# -------- COMMANDS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_names[user.id] = user.first_name
    
    # Logique de parrainage : si le user vient d'un lien ref
    if context.args and context.args[0].startswith("ref_"):
        referrer_id = int(context.args[0].replace("ref_", ""))
        if user.id != referrer_id and user.id not in referred_users:
            user_scores[referrer_id] += 50 # Bonus de 50 pts pour le parrain
            referred_users.add(user.id)
            try:
                await context.bot.send_message(chat_id=referrer_id, text=f"🎉 New referral! You earned 50 pts thanks to {user.first_name}!")
            except: pass

    await update.message.reply_photo(
        photo=open(LOGO_PATH, "rb"),
        caption="🕊️ **OWPC Ecosystem v2.2**\n\nInvite your friends and claim your daily points to climb the leaderboard! 🚀",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# -------- CALLBACK HANDLER --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "view_leaderboard":
        sorted_users = sorted(user_scores.items(), key=lambda item: item[1], reverse=True)[:10]
        text = "🏆 **OWPC ACTIVITY LEADERBOARD**\n\n"
        for i, (uid, score) in enumerate(sorted_users, 1):
            name = user_names.get(uid, f"User_{uid}")
            text += f"{i}. {name} — {score} pts\n"
        await query.message.reply_text(text, parse_mode="Markdown")

    elif query.data == "daily_claim":
        today = datetime.now().date()
        if last_daily.get(user_id) == today:
            await query.message.reply_text("⏳ You already claimed your points today! Come back tomorrow.")
        else:
            user_scores[user_id] += 10
            last_daily[user_id] = today
            await query.message.reply_text("✅ +10 points added! Your consistency supports the UNITY. 💎")

    elif query.data == "get_invite":
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        text = (
            "🔗 **YOUR PERSONAL REFERRAL LINK**\n\n"
            f"`{ref_link}`\n\n"
            "Share this link! You earn **50 points** for every new member who joins. 🚀"
        )
        await query.message.reply_text(text, parse_mode="Markdown")

    elif query.data == "show_links":
        text = "🌐 **OFFICIAL LINKS**\n\n🔹 [Website](https://deeptrade.bio.link)\n🔹 [Twitter](https://x.com/DeepTradeX)\n🔹 [YouTube](https://youtube.com/@deeptradex)"
        await query.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

# -------- IA HANDLER --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text: return
    user_id = update.effective_user.id
    user_names[user_id] = update.effective_user.first_name
    user_scores[user_id] += 1 # 1 pt par message

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are the OWPC Alpha Bot. Focus on UNITY, VEO, GENESIS. Be professional and visionary."},
                {"role": "user", "content": update.message.text}
            ],
            max_tokens=150
        )
        await update.message.reply_text(response.choices[0].message.content)
    except Exception as e: print(f"AI Error: {e}")

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 OWPC Bot v2.2 (Ref & Daily) running")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
