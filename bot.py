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

# 🔹 Commande /veos
async def veos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    thread_id = getattr(update.message, "message_thread_id", None)
    await update.message.reply_text(
        "VEO is a community-driven meme crypto.\n"
        "Part of the One World Peace Coins ecosystem.",
        message_thread_id=thread_id
    )

# 🔹 Commande /links
async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    thread_id = getattr(update.message, "message_thread_id", None)
    await update.message.reply_text(
        "Official links:\nhttps://deeptrade.bio.link",
        message_thread_id=thread_id
    )

# 🔹 Commande /invite
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    thread_id = getattr(update.message, "message_thread_id", None)
    await update.message.reply_text(
        "Invite friends and grow the VEO community 🚀",
        message_thread_id=thread_id
    )

# 🔹 Message de bienvenue automatique
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    thread_id = getattr(update.message, "message_thread_id", None)
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"Welcome {member.first_name}! 🚀\n"
            "You joined the VEO community.\n"
            "Part of One World Peace Coins 🌍\n"
            "Start here 👉 https://deeptrade.bio.link",
            message_thread_id=thread_id
        )

# 🔹 Création de l'application
app = ApplicationBuilder().token(TOKEN).build()

# 🔹 Ajout des handlers
app.add_handler(CommandHandler("veos", veos))
app.add_handler(CommandHandler("links", links))
app.add_handler(CommandHandler("invite", invite))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

# 🔹 Debug message
print("⚡ Bot is starting... polling for updates.")

# 🔹 Lancer le bot avec polling
app.run_polling()