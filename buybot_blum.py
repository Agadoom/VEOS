import os
from telegram import Bot
from telegram.ext import CommandHandler, Updater

# Variables d'environnement (tu peux les mettre dans ton fichier .env ou directement ici)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8628687876:AAGb596ry7ZaYgsM9j-Y6dU2aNhXfS7AsBg")
CHAT_ID = os.getenv("CHAT_ID", "-1003564334773")

# Initialisation du bot
bot = Bot(token=BOT_TOKEN)
updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Commande /start
def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Salut ! Le bot fonctionne sans blockchain pour l'instant 🚀")

# Commande /buy simulée
def buy(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="💰 Achat simulé ! Ici, tu pourrais intégrer la blockchain plus tard.")

# Ajout des commandes
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("buy", buy))

# Lancement du bot
if __name__ == "__main__":
    print("Bot lancé ! Envoie /start dans Telegram pour tester.")
    updater.start_polling()
    updater.idle()