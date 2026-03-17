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

# -------- GRADES & BADGES --------
def get_title(score):
    if score >= 1000: return "👑 Alpha Legend"
    if score >= 500:  return "💎 Unity Guardian"
    if score >= 100:  return "🛠️ Builder"
    return "🐣 Seeker"

# -------- COMMANDES --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_names[user.id] = user.first_name
    
    # Système de Parrainage
    if context.args and context.args[0].startswith("ref_"):
        referrer_id = int(context.args[0].replace("ref_", ""))
        if user.id != referrer_id and user.id not in referred_users:
            user_scores[referrer_id] += 50 
            referred_users.add(user.id)
            try:
                await context.bot.send_message(
                    chat_id=referrer_id, 
                    text=f"🔥 **+50 POINTS!** Your friend {user.first_name} joined the hive via your link!"
                )
            except: pass

    # Si c'est en privé, on montre le menu complet
    if update.effective_chat.type == "private":
        await update.message.reply_photo(
            photo=open(LOGO_PATH, "rb"),
            caption=f"🕊️ **OWPC Core v2.4**\n\nWelcome {user.first_name}!\nRank: {get_title(user_scores[user.id])}\n\nUse the buttons to grow the ecosystem.",
            reply_markup=get_main_keyboard()
        )

# -------- CLAVIER --------
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("GENESIS 🧬", url=LINK_GENESIS),
         InlineKeyboardButton("UNITY 💎", url=LINK_UNITY),
         InlineKeyboardButton("VEO ⚡", url=LINK_VEO)],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_leaderboard"),
         InlineKeyboardButton("📅 Daily Points", callback_data="daily_claim")],
        [InlineKeyboardButton("🔗 YOUR INVITE LINK", callback_data="get_invite")]
    ])

# -------- BOUTONS --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "view_leaderboard":
        sorted_users = sorted(user_scores.items(), key=lambda item: item[1], reverse=True)[:10]
        text = "🏆 **OWPC TOP HOLDERS**\n\n"
        for i, (uid, score) in enumerate(sorted_users, 1):
            name = user_names.get(uid, f"User_{uid}")
            text += f"{i}. {name} — {score} pts ({get_title(score)})\n"
        await query.message.reply_text(text)

    elif query.data == "get_invite":
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        text = f"🔗 **YOUR INVITE LINK**\n\n`{ref_link}`\n\nEarn 50 pts per referral! 🚀"
        await query.message.reply_text(text, parse_mode="Markdown")

    elif query.data == "daily_claim":
        today = datetime.now().date()
        if last_daily.get(user_id) == today:
            await query.message.reply_text("⏳ Already claimed. Come back tomorrow!")
        else:
            user_scores[user_id] += 10
            last_daily[user_id] = today
            await query.message.reply_text(f"✅ +10 pts! Current Rank: {get_title(user_scores[user_id])}")

# -------- CHAT HANDLER (GROUP + AI) --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    user = update.effective_user
    user_id = user.id
    user_names[user_id] = user.first_name
    
    # 1 message = 1 point dans le groupe
    old_score = user_scores[user_id]
    user_scores[user_id] += 1
    new_score = user_scores[user_id]

    # Alerte de changement de Grade (Badge)
    if get_title(old_score) != get_title(new_score):
        await update.message.reply_text(
            f"🎊 **CONGRATULATIONS {user.first_name}!**\nYou just leveled up to: **{get_title(new_score)}** 🏆"
        )

    # Réponse IA (seulement si le bot est cité ou en privé)
    if context.bot.username in update.message.text or update.effective_chat.type == "private":
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"Tu es l'IA Alpha d'OWPC. L'utilisateur est un {get_title(new_score)}."},
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
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 OWPC Bot v2.4 (Group & Badges) running")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
