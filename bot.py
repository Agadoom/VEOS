import os
import asyncio
import nest_asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import openai

nest_asyncio.apply()

# -------- CONFIGURATION DES ENVIRONNEMENTS --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# -------- STOCKAGE DES DONNÉES (Activité & Noms) --------
user_scores = defaultdict(int) 
user_names = {}

# -------- LIENS OFFICIELS & ASSETS --------
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"
LINK_WEBSITE = "https://deeptrade.bio.link"
LINK_TWITTER = "https://x.com/DeepTradeX"
LINK_YOUTUBE = "https://youtube.com/@deeptradex"

LOGO_PATH = "media/owpc_logo.png"
ROADMAP_PATH = "media/roadmap.png"

# -------- CLAVIER PRINCIPAL --------
def get_main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("GENESIS 🧬", url=LINK_GENESIS),
            InlineKeyboardButton("UNITY 💎", url=LINK_UNITY),
            InlineKeyboardButton("VEO ⚡", url=LINK_VEO)
        ],
        [
            InlineKeyboardButton("🌐 Official Links", callback_data="show_links"),
            InlineKeyboardButton("🏆 Leaderboard", callback_data="view_leaderboard")
        ],
        [
            InlineKeyboardButton("📢 Invite Friends", url="https://t.me/share/url?url=https://t.me/OWPCinfo_bot")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# -------- COMMANDES PRINCIPALES --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lance le menu principal avec le logo OWPC."""
    try:
        await update.message.reply_photo(
            photo=open(LOGO_PATH, "rb"),
            caption="🕊️ **OWPC Ecosystem Core Active**\n\nWelcome to Phase 2. Use the buttons below to explore our 3-pillar ecosystem and access the apps.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await update.message.reply_text("🕊️ **OWPC Ecosystem Core Active**\n(Logo missing in /media)", reply_markup=get_main_keyboard())

async def roadmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envoie l'image de la Roadmap de la Phase 2."""
    if os.path.exists(ROADMAP_PATH):
        await update.message.reply_photo(
            photo=open(ROADMAP_PATH, "rb"),
            caption="📍 **OWPC OFFICIAL ROADMAP**\n\nOur journey is set. From infrastructure to global integration. Trust the vision. 🕊️",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("📍 **Roadmap status:** Image updating. Stay tuned to the channel!")

# -------- GESTION DES BOUTONS (CALLBACK) --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "view_leaderboard":
        if not user_scores:
            await query.message.reply_text("🏆 **Leaderboard is currently empty.**\nStart chatting in the group to climb the ranks!")
            return

        # Tri des 10 meilleurs utilisateurs par score
        sorted_users = sorted(user_scores.items(), key=lambda item: item[1], reverse=True)[:10]
        leaderboard_text = "🏆 **OWPC ACTIVITY LEADERBOARD**\n\n"
        for i, (uid, score) in enumerate(sorted_users, 1):
            name = user_names.get(uid, f"User_{uid}")
            leaderboard_text += f"{i}. {name} — {score} pts\n"
        
        await query.message.reply_text(leaderboard_text, parse_mode="Markdown")

    elif query.data == "show_links":
        links_text = (
            "🌐 **OWPC OFFICIAL ECOSYSTEM LINKS**\n\n"
            f"🔹 **Website:** [deeptrade.bio.link]({LINK_WEBSITE})\n"
            f"🔹 **Twitter (X):** [DeepTradeX]({LINK_TWITTER})\n"
            f"🔹 **YouTube:** [@deeptradex]({LINK_YOUTUBE})\n\n"
            "⚠️ Always verify you are using official links to stay safe."
        )
        await query.message.reply_text(links_text, parse_mode="Markdown", disable_web_page_preview=True)

# -------- IA & TRACKING D'ACTIVITÉ --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    user_id = user.id
    user_names[user_id] = user.first_name
    
    # Enregistrement de l'activité pour le Leaderboard
    user_scores[user_id] += 1

    # Réponse de l'IA personnalisée OWPC
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are the OWPC Alpha Bot. You are professional, visionary, and focused on the 3 pillars: UNITY, VEO, and GENESIS. Keep the community motivated and answer their questions about the ecosystem with authority."},
                {"role": "user", "content": update.message.text}
            ],
            max_tokens=200
        )
        await update.message.reply_text(response.choices[0].message.content)
    except Exception as e:
        print(f"Erreur IA: {e}")

# -------- LANCEMENT DU BOT --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("roadmap", roadmap))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 OWPC Bot v2.1 running with Leaderboard, Links & AI")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
