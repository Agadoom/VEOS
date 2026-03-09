import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Récupère le token depuis les variables d'environnement Railway
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", "8443"))  # Railway fournit souvent un port via variable d'environnement
RAILWAY_URL = os.getenv("RAILWAY_STATIC_URL")  # URL de ton projet Railway (ou ton custom domain)

# Commande /veo
async def veo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "VEO is a community-driven meme crypto.\n"
        "Part of the One World Peace Coins ecosystem."
    )

# Commande /links
async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Official links:\nhttps://deeptrade.bio.link"
    )

# Commande /invite
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Invite friends and grow the VEO community 🚀"
    )

# Message de bienvenue automatique
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"Welcome {member.first_name}! 🚀\n"
            "You joined the VEO community.\n"
            "Part of One World Peace Coins 🌍\n"
            "Start here 👉 https://deeptrade.bio.link"
        )

# Création de l'application
app = ApplicationBuilder().token(TOKEN).build()

# Ajout des handlers
app.add_handler(CommandHandler("veo", veo))
app.add_handler(CommandHandler("links", links))
app.add_handler(CommandHandler("invite", invite))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

# ------------------------------
# 🔹 Lancer le bot en webhook
# ------------------------------
app.run_webhook(
    listen="0.0.0.0",
    port=PORT,
    url_path=TOKEN,
    webhook_url=f"{RAILWAY_URL}/{TOKEN}"
)