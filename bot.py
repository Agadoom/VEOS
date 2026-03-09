import os
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 🔹 Récupère le token depuis les variables d'environnement Railway
TOKEN = os.getenv("TOKEN")

# Vérifie que le token est bien chargé
if not TOKEN:
    print("❌ ERROR: Telegram TOKEN not found in environment variables.")
    exit(1)
else:
    print("✅ TOKEN loaded successfully")

# 🔹 Commande /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    thread_id = getattr(update.message, "message_thread_id", None)
    await update.message.reply_text(
        "👋 Welcome to the VEO community!\n"
        "This bot helps you explore VEO and One World Peace Coins 🌍\n\n"
        "Use /help to see available commands.",
        message_thread_id=thread_id
    )

# 🔹 Commande /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    thread_id = getattr(update.message, "message_thread_id", None)
    await update.message.reply_text(
        "📜 Available commands:\n"
        "/start - Welcome message\n"
        "/help - List commands\n"
        "/veos - Info about VEO crypto\n"
        "/links - Official links\n"
        "/invite - Invite friends",
        message_thread_id=thread_id
    )

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
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("veos", veos))
app.add_handler(CommandHandler("links", links))
app.add_handler(CommandHandler("invite", invite))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

# 🔹 Définit les commandes visibles dans Telegram
async def set_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Welcome message"),
        BotCommand("help", "List all commands"),
        BotCommand("veos", "Info about VEO crypto"),
        BotCommand("links", "Official links"),
        BotCommand("invite", "Invite friends to the community")
    ])

# 🔹 Lancer le bot avec polling
async def main():
    await set_bot_commands(app)
    print("⚡ Bot is starting... polling for updates.")
    await app.run_polling()

import asyncio
asyncio.run(main())