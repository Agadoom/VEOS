import os
import asyncio
import nest_asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import openai

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# -------- DATA (Persistance simple en mémoire) --------
# Dans un vrai projet, utilise une base de données (SQLite/PostgreSQL)
user_scores = defaultdict(int) 
user_names = {}

# ---- Links / Assets ----
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA"

LOGO_PATH = "media/owpc_logo.png"
# GIF_PATH = "media/gif.gif"
ROADMAP_PATH = "media/roadmap.png" # Assure-toi d'avoir cette image

# -------- HELPERS --------
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("GENESIS 🧬", url=LINK_GENESIS),
         InlineKeyboardButton("UNITY 💎", url=LINK_UNITY),
         InlineKeyboardButton("VEO ⚡", url=LINK_VEO)],
        [InlineKeyboardButton("🌐 Links", callback_data="show_links"), # Tu peux ajouter des callback plus tard
         InlineKeyboardButton("📢 Invite", url="https://t.me/share/url?url=https://t.me/votre_bot")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="view_leaderboard")]
    ])

# -------- COMMANDS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_photo(
        photo=open(LOGO_PATH, "rb"),
        caption="🕊️ **Welcome to OWPC Ecosystem**\nThe core is active. Use the buttons below to explore and buy tokens 🚀",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    await update.message.reply_animation(animation=open(GIF_PATH, "rb"))

async def roadmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(ROADMAP_PATH):
        await update.message.reply_photo(
            photo=open(ROADMAP_PATH, "rb"),
            caption="📍 **OWPC ROADMAP - PHASE 2**\nWe are building the foundation of a global empire. Trust the vision. 🕊️",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("📍 Roadmap image missing in /media folder.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_scores:
        await update.message.reply_text("🏆 The leaderboard is empty. Start chatting to climb the ranks!")
        return

    # Trier les 10 meilleurs
    sorted_users = sorted(user_scores.items(), key=lambda item: item[1], reverse=True)[:10]
    text = "🏆 **OWPC TOP HOLDERS (Activity)**\n\n"
    for i, (user_id, score) in enumerate(sorted_users, 1):
        name = user_names.get(user_id, f"User_{user_id}")
        text += f"{i}. {name} — {score} pts\n"
    
    text += "\n🔥 Keep active to support the UNITY!"
    await update.message.reply_text(text, parse_mode="Markdown")

# -------- AI & ACTIVITY HANDLER --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_names[user_id] = user.first_name
    
    # Incrémenter le score d'activité
    user_scores[user_id] += 1

    # Réponse IA (seulement si le bot est mentionné ou en MP)
    if update.message.text:
        try:
            # IA avec "System Prompt" pour la personnalité OWPC
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo", # Utilise 3.5-turbo (plus stable que gpt-5-mini qui n'existe pas)
                messages=[
                    {"role": "system", "content": "You are the OWPC Alpha Bot. You are professional and visionary. You support the 3 pillars: UNITY, VEO, and GENESIS. Keep the community motivated without promising financial gains."},
                    {"role": "user", "content": update.message.text}
                ],
                max_tokens=200
            )
            answer = response.choices[0].message.content
            await update.message.reply_text(answer)
        except Exception as e:
            print(f"AI Error: {e}")

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("roadmap", roadmap))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 OWPC Bot v2.0 running on Railway")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
