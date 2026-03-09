import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ ERROR: Telegram TOKEN not found in environment variables.")
    exit(1)

# Commandes
async def veos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "VEO is a community-driven meme crypto.\n"
        "Part of the One World Peace Coins ecosystem."
    )

async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Official links:\nhttps://deeptrade.bio.link"
    )

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Invite friends and grow the VEO community 🚀"
    )

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
app.add_handler(CommandHandler("veos", veos))
app.add_handler(CommandHandler("links", links))
app.add_handler(CommandHandler("invite", invite))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

print("⚡ Bot is starting... polling for updates.")

# 🔹 Fonction main adaptée à un loop déjà existant
async def main():
    await app.initialize()
    await app.start()
    print("✅ Bot started successfully")
    await app.updater.start_polling()
    # Le bot continue de tourner
    await asyncio.Event().wait()

# Lancer le bot dans le loop actuel
asyncio.run(main())