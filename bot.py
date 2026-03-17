import os
import asyncio
import nest_asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
import openai

nest_asyncio.apply()

# -------- ENV --------
TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROUP_ID = os.getenv("GROUP_ID")  # chat_id du groupe Telegram

if not TOKEN or not OPENAI_API_KEY or not GROUP_ID:
    print("❌ TOKEN, OPENAI_API_KEY ou GROUP_ID manquant")
    exit()

openai.api_key = OPENAI_API_KEY

# -------- DATA --------
user_activity = defaultdict(int)
CA_GENESIS = "EQADd56FsTcaOntj-F-he1DUnkPVnsHx7WolQpWUuW6tl1eS"
CA_UNITY = "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx"
CA_VEO = "EQC80jMdQW-bS6ePB99HJIGN-krRBzPSJ8KIZ_dfwBhDV-wt"
allowed_links = ["deeptrade.bio.link", "t.me/blum", "youtube.com/@deeptradex", "base.app"]

# -------- HELPERS --------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("GENESIS", url=f"https://t.me/blum/app?startapp=memepadjetton_GENESIS_2xKA1-ref_6VRKyJ9MZA")],
        [InlineKeyboardButton("UNITY", url=f"https://t.me/blum/app?startapp=memepadjetton_UNITY_psbzR-ref_6VRKyJ9MZA")],
        [InlineKeyboardButton("VEO", url=f"https://t.me/blum/app?startapp=memepadjetton_VEO_UnqBK-ref_6VRKyJ9MZA")],
        [
            InlineKeyboardButton("Leaderboard", callback_data="leaderboard"),
            InlineKeyboardButton("Links", callback_data="links"),
            InlineKeyboardButton("Invite", callback_data="invite")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def ask_ai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful crypto community assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        print("AI error:", e)
        return "🤖 AI temporarily unavailable."

# -------- COMMANDS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to OWPC Ultimate Hub\n🚀 Community driven crypto\n🌍 One World Peace Coins ecosystem",
        reply_markup=main_menu()
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📊 OWPC Stats:\n"
        f"GENESIS: {len(user_activity)} holders approx\n"
        f"UNITY: {len(user_activity)} holders approx\n"
        f"VEO: {len(user_activity)} holders approx\n"
    )
    await update.message.reply_text(text, reply_markup=main_menu())

# -------- CALLBACKS --------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "links":
        await query.edit_message_text(
            text=f"🌐 Official Links\n\n💠 GENESIS: {CA_GENESIS}\n💎 UNITY: {CA_UNITY}\n⚡ VEO: {CA_VEO}\n\nWebsite: https://deeptrade.bio.link\nYouTube: https://youtube.com/@deeptradex",
            reply_markup=main_menu()
        )
    elif query.data == "invite":
        await query.edit_message_text(
            text="📢 Invite friends and grow the OWPC community 🚀\nJoin our Telegram: https://t.me/+SQhKj-gWWmcyODY0",
            reply_markup=main_menu()
        )
    elif query.data == "leaderboard":
        leaderboard = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:10]
        text = "🏆 Top Active Members:\n"
        for i, (user_id, score) in enumerate(leaderboard, start=1):
            try:
                user = await context.bot.get_chat(user_id)
                name = user.first_name
            except:
                name = str(user_id)
            text += f"{i}. {name} - {score} pts\n"
        try:
            await query.message.reply_animation(
                animation=open("lv_0_20260310200554.gif", "rb"),
                caption=text,
                reply_markup=main_menu()
            )
        except:
            await query.edit_message_text(text=text, reply_markup=main_menu())

# -------- MESSAGE HANDLER --------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return
    user_id = update.message.from_user.id
    user_activity[user_id] += 1

    text = (update.message.text or "").lower()
    # Quick answers
    if "ca" in text or "contract" in text:
        await update.message.reply_text(
            f"💠 Contract Address\nGENESIS: {CA_GENESIS}\nUNITY: {CA_UNITY}\nVEO: {CA_VEO}"
        )
        return
    if "buy" in text:
        await update.message.reply_text(
            "🚀 Buy GENESIS / UNITY / VEO here:\nhttps://base.app or Blum Mini App"
        )
        return
    # AI fallback
    reply = await ask_ai(text)
    await update.message.reply_text(f"🤖 {reply}")

# -------- AUTO-HYPE TASK --------
async def auto_hype(context):
    try:
        await context.bot.send_photo(
            chat_id=int(GROUP_ID),
            photo=open("owpc_logo.png", "rb"),
            caption="🌍 OWPC Phase 2 is live! Hold, engage, and join the movement! 🚀💎",
            reply_markup=main_menu()
        )
    except Exception as e:
        print("Auto-hype error:", e)

# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Auto-hype every 4 hours
    job_queue = app.job_queue
    job_queue.run_repeating(auto_hype, interval=60*60*4, first=10)

    print("🚀 OWPC Ultimate Hub Bot démarré")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())