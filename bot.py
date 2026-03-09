from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

TOKEN = os.getenv("TOKEN")

async def veos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /veos command received")
    await update.message.reply_text("VEO is alive!")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("veos", veos))
app.run_polling()