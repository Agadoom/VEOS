import os
import asyncio
import nest_asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import openai

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# -------- DATA --------
user_scores = defaultdict(int) 
user_names = {}

# ---- Links / Assets ----
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
        [InlineKeyboardButton("🌐 Official Links", callback_data="show_links"),
         InlineKeyboardButton("🏆 Leaderboard", callback_data="view_leaderboard")],
        [InlineKeyboardButton("📢 Invite Friends", url="https://t.me/share/url?url=https://t.me/votre_bot_username")]
    ])

# -------- COMMANDS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_photo(
        photo=open(LOGO_PATH, "rb"),
        caption="🕊️ **OWPC Ecosystem Core Active**\n\nBienvenue dans la Phase 2. Utilisez les boutons ci-dessous pour naviguer.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def roadmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(ROADMAP_PATH):
        await update.message.reply_photo(
            photo=open(ROADMAP_PATH, "rb"),
            caption="📍 **OWPC ROADMAP**\nTrust the vision. Unity is power. 🕊️",
            parse_mode="Markdown"
        )

# -------- CALLBACK HANDLER (Pour les boutons) --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "view_leaderboard":
        if not user_scores:
            await query.edit_message_caption(caption="🏆 Le leaderboard est vide. Commencez à discuter !")
            return

        sorted_users = sorted(user_scores.items(), key=lambda item: item[1], reverse=True)[:10]
        text = "🏆 **OWPC TOP HOLDERS (Activity)**\n\n"
        for i, (user_id, score) in enumerate(sorted_users, 1):
            name = user_names.get(user_id, f"User_{user_id}")
            text += f"{i}. {name} — {score} pts\n"
        
        await query.message.reply_text(text, parse_mode="Markdown")

    elif query.data == "show_links":
        links_text = (
            "🌐 **OWPC OFFICIAL LINKS**\n\n"
            "🔹 Website: [owpc.io](https://owpc.io)\n"
            "🔹 YouTube: [@deeptradex](https://youtube.com/@deeptradex)\n"
            "🔹 X (Twitter): [OWPC_Official](https://x.com/OWPC_Official)"
        )
        await query.message.reply_text(links_text, parse_mode="Markdown", disable_web_page_preview=True)

# -------- AI & ACTIVITY --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    user = update.effective_user
    user_id = user.id
    user_names[user_id] = user.first_name
    user_scores[user_id] += 1 # On compte l'activité

    # Réponse IA simplifiée
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Tu es l'IA du bot OWPC. Pro, visionnaire, focus sur UNITY, VEO, GENESIS."},
                {"role": "user", "content": update.message.text}
            ],
            max_tokens=150
        )
        await update.message.reply_text(response.choices[0].message.content)
    except Exception as e:
        print(f"AI Error: {e}")

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("roadmap", roadmap))
    app.add_handler(CallbackQueryHandler(button_handler)) # Gère les clics sur boutons
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 OWPC Bot v2.1 (No GIF + Fix Leaderboard) running")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
