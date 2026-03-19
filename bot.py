import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIGURATION ---
# Assure-toi que cette variable est bien le TOKEN de @OwpcInfobot sur Railway
TOKEN = os.getenv("TOKEN")

# Liens officiels (récupérés de l'écosystème)
LINK_MINING_BOT = "https://t.me/OWPCsbot"
LINK_CHANNEL = "https://t.me/owpc_co"  # Remplace par ton canal si différent
LINK_GENESIS = "https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1"
LINK_UNITY = "https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR"
LINK_VEO = "https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK"

# --- LOGIQUE DU BOT ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu principal du bot d'information"""
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 START MINING (Terminal)", url=LINK_MINING_BOT)],
        [InlineKeyboardButton("📢 Official Channel", url=LINK_CHANNEL)],
        [InlineKeyboardButton("💰 Buy/Invest (Blum)", callback_data="buy_menu")],
        [InlineKeyboardButton("📖 Protocol Info", callback_data="info_menu")]
    ])
    
    msg = (
        "🕊️ **WELCOME TO OWPC INFO HUB**\n\n"
        "You have reached the official information terminal for the One World Peace Coins ecosystem.\n\n"
        "**Status:** `ACTIVE ✅`\n"
        "**Network:** `TON / BLUM`"
    )
    
    if update.message:
        await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.callback_query.message.edit_text(msg, reply_markup=kb, parse_mode="Markdown")

async def handle_menus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestion des menus secondaires et du bouton retour"""
    query = update.callback_query
    await query.answer()

    if query.data == "back_main":
        await start(update, context)

    elif query.data == "buy_menu":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧬 GENESIS", url=LINK_GENESIS)],
            [InlineKeyboardButton("🌍 UNITY", url=LINK_UNITY)],
            [InlineKeyboardButton("🤖 VEO AI", url=LINK_VEO)],
            [InlineKeyboardButton("⬅️ BACK", callback_data="back_main")]
        ])
        await query.message.edit_text(
            "💎 **INVESTMENT SECTORS**\n\nClick a token to open it in Blum Memepad:",
            reply_markup=kb, parse_mode="Markdown"
        )

    elif query.data == "info_menu":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back_main")]])
        info_txt = (
            "📖 **OWPC PROTOCOL INFO**\n\n"
            "**Genesis:** The foundational core of OWPC.\n"
            "**Unity:** The community and governance layer.\n"
            "**Veo AI:** The intelligent extraction algorithm.\n\n"
            "Use the Mining Bot to earn points and stay active in the ecosystem."
        )
        await query.message.edit_text(info_txt, reply_markup=kb, parse_mode="Markdown")

# --- EXECUTION ---

if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: No TOKEN found in environment variables!")
    else:
        print("✅ OwpcInfobot is starting...")
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(handle_menus))
        
        app.run_polling(drop_pending_updates=True)
