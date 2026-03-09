from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "TON_TOKEN_ICI"

# Message de bienvenue
WELCOME_TEXT = """
👋 Bienvenue sur le bot !

Ici tu trouveras tous nos liens importants.

Clique sur les boutons ci-dessous ⬇️
"""

# Commande /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    keyboard = [
        [InlineKeyboardButton("🌐 Nos liens", callback_data="links")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=reply_markup
    )

# Commande /links
async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
📌 Voici nos liens :

🌍 Site web
https://monsite.com

📢 Canal Telegram
https://t.me/moncanal

💬 Groupe Telegram
https://t.me/mongroupe

📷 Instagram
https://instagram.com/moncompte

▶️ YouTube
https://youtube.com/@monchaine
"""

    await update.message.reply_text(text)

# Lancer le bot
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("links", links))

    print("Bot lancé...")

    app.run_polling()

if __name__ == "__main__":
    main()