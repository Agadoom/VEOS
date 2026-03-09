import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
print("TOKEN loaded:", TOKEN)

async def veos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Command /veos received")  # <-- debug log
    await update.message.reply_text("VEO is alive!")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("veos", veos))

app.run_polling()