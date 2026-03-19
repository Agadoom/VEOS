import os
import sqlite3
import asyncio
import uvicorn
from fastapi import FastAPI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = "https://veos-production.up.railway.app"

app = FastAPI()

# --- WEB PART ---
@app.get("/")
async def home():
    return {"status": "Terminal Active", "protocol": "OWPC"}

# --- BOT PART ---
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 LAUNCH TERMINAL", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Invest Hub", callback_data="invest"), InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("🆔 Passport", callback_data="passport")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🕊️ **OWPC PROTOCOL**\n\nCommander: {update.effective_user.first_name}\nStatus: `OPERATIONAL` ✅",
        reply_markup=main_menu(), parse_mode="Markdown"
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "stats":
        await query.message.edit_text("📊 **Stats:** 0 OWPC", reply_markup=main_menu())

# --- RUNNER ---
if __name__ == "__main__":
    # Si on lance le fichier normalement, on lance le BOT
    # Le WEB est géré par la commande 'uvicorn' dans le Procfile
    if not TOKEN:
        print("❌ TOKEN MISSING")
    else:
        print("🤖 STARTING BOT WORKER...")
        bot_app = ApplicationBuilder().token(TOKEN).build()
        bot_app.add_handler(CommandHandler("start", start))
        bot_app.add_handler(CallbackQueryHandler(handle_callback))
        bot_app.run_polling(drop_pending_updates=True)
