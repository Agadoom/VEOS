import os
import asyncio
import nest_asyncio
from datetime import datetime
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import openai

nest_asyncio.apply()

# -------- CONFIGURATION RAILWAY --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY
BOT_USERNAME = "OWPCinfobot" # L'ID de parrainage en dépend

# -------- STOCKAGE EN MÉMOIRE --------
user_scores = defaultdict(int) 
user_names = {}
last_daily = {} 
referred_users = set() 

# -------- LIENS & ASSETS --------
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LOGO_PATH = "media/owpc_logo.png"
ROADMAP_PATH = "media/roadmap.png"

# -------- SYSTÈME DE GRADES --------
def get_title(score):
    if score >= 1000: return "👑 Alpha Legend"
    if score >= 500:  return "💎 Unity Guardian"
    if score >= 100:  return "🛠️ Builder"
    return "🐣 Seeker"

# -------- CLAVIER INTERACTIF --------
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("GENESIS 🧬", url=LINK_GENESIS),
         InlineKeyboardButton("UNITY 💎", url=LINK_UNITY),
         InlineKeyboardButton("VEO ⚡", url=LINK_VEO)],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_leaderboard"),
         InlineKeyboardButton("📅 Daily Points", callback_data="daily_claim")],
        [InlineKeyboardButton("🔗 YOUR INVITE LINK", callback_data="get_invite")],
        [InlineKeyboardButton("🌐 Official Links", callback_data="show_links")]
    ])

# -------- COMMANDES --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_names[user.id] = user.first_name
    
    # Gestion du parrainage via lien profond
    if context.args and context.args[0].startswith("ref_"):
        try:
            referrer_id = int(context.args[0].replace("ref_", ""))
            if user.id != referrer_id and user.id not in referred_users:
                user_scores[referrer_id] += 50 
                referred_users.add(user.id)
                await context.bot.send_message(
                    chat_id=referrer_id, 
                    text=f"🔥 **+50 PTS!** {user.first_name} a rejoint la ruche via ton lien !"
                )
        except: pass

    # Message de bienvenue (différent si Groupe ou Privé)
    if update.effective_chat.type == "private":
        await update.message.reply_photo(
            photo=open(LOGO_PATH, "rb"),
            caption=f"🕊️ **OWPC Core v2.5**\n\nBienvenue {user.first_name}!\nTon Grade : {get_title(user_scores[user.id])}\n\nUtilise le menu pour propulser l'écosystème.",
            reply_markup=get_main_keyboard()
        )

async def roadmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(ROADMAP_PATH):
        await update.message.reply_photo(photo=open(ROADMAP_PATH, "rb"), caption="📍 **OWPC ROADMAP**")

# -------- GESTION DES BOUTONS --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "view_leaderboard":
        sorted_users = sorted(user_scores.items(), key=lambda item: item[1], reverse=True)[:10]
        text = "🏆 **TOP 10 OWPC ACTIVITY**\n\n"
        for i, (uid, score) in enumerate(sorted_users, 1):
            name = user_names.get(uid, f"User_{uid}")
            text += f"{i}. {name} — {score} pts ({get_title(score)})\n"
        await query.message.reply_text(text)

    elif query.data == "get_invite":
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        await query.message.reply_text(f"🔗 **TON LIEN DE PARRAINAGE**\n\n`{ref_link}`\n\nGagne 50 pts par ami invité ! 🚀", parse_mode="Markdown")

    elif query.data == "daily_claim":
        today = datetime.now().date()
        if last_daily.get(user_id) == today:
            await query.message.reply_text("⏳ Déjà réclamé. Reviens demain !")
        else:
            user_scores[user_id] += 10
            last_daily[user_id] = today
            await query.message.reply_text(f"✅ +10 pts ! Grade actuel : {get_title(user_scores[user_id])}")

    elif query.data == "show_links":
        text = "🌐 **LIENS OFFICIELS**\n\n🔹 [Website](https://deeptrade.bio.link)\n🔹 [Twitter](https://x.com/DeepTradeX)\n🔹 [YouTube](https://youtube.com/@deeptradex)"
        await query.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

# -------- LOGIQUE DE GROUPE & IA --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    user = update.effective_user
    chat = update.effective_chat
    user_id = user.id
    user_names[user_id] = user.first_name
    
    # 1. Mise à jour du score (Activité)
    old_score = user_scores[user_id]
    user_scores[user_id] += 1
    new_score = user_scores[user_id]

    # 2. Annonce de Level Up dans le groupe
    if get_title(old_score) != get_title(new_score):
        await update.message.reply_text(f"🎊 **FÉLICITATIONS {user.first_name}!**\nTu viens de passer au grade : **{get_title(new_score)}** 🏆")

    # 3. Réponse IA (Seulement si mentionné ou en privé)
    is_private = chat.type == "private"
    is_mentioned = f"@{context.bot.username}" in update.message.text
    is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if is_private or is_mentioned or is_reply:
        try:
            clean_text = update.message.text.replace(f"@{context.bot.username}", "").strip()
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"Tu es l'IA Alpha d'OWPC. L'utilisateur est un {get_title(new_score)}. Sois visionnaire et pro."},
                    {"role": "user", "content": clean_text}
                ],
                max_tokens=150
            )
            await update.message.reply_text(response.choices[0].message.content)
        except: pass

# -------- LANCEMENT --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("roadmap", roadmap))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 OWPC Bot v2.5 Online & Group Optimized")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
