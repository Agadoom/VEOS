import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 🔹 Récupère le token depuis les variables d'environnement Railway
TOKEN = os.getenv("TOKEN")

# Vérifie que le token est bien chargé
if not TOKEN:
    print("❌ ERROR: Telegram TOKEN not found in environment variables.")
    exit(1)
else:
    print("✅ TOKEN loaded successfully")

# 🔹 Commande /veo
async def veo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "VEO is a community-driven meme crypto.\n"
        "Part of the One World Peace Coins ecosystem."
    )

# 🔹 Commande /links
async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Official links:\nhttps://deeptrade.bio.link"
    )

# 🔹 Commande /invite
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Invite friends and grow the VEO community 🚀"
    )

# 🔹 Message de bienvenue automatique
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"Welcome {member.first_name}! 🚀\n"
            "You joined the VEO community.\n"
            "Part of One World Peace Coins 🌍\n"
            "Start here 👉 https://deeptrade.bio.link"
        )

# 🔹 Création de l'application
app = ApplicationBuilder().token(TOKEN).build()

# 🔹 Ajout des handlers
app.add_handler(CommandHandler("veo", veo))
app.add_handler(CommandHandler("links", links))
app.add_handler(CommandHandler("invite", invite))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

# 🔹 Message de debug pour savoir que le bot démarre
print("⚡ Bot is starting... polling for updates.")

# 🔹 Lancer le bot avec polling (une seule instance !)
app.run_polling()