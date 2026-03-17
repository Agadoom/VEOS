import os import re import asyncio import nest_asyncio from collections import defaultdict from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

nest_asyncio.apply()

-------- ENV --------

TOKEN = os.getenv("TOKEN") OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") GROUP_ID = os.getenv("GROUP_ID")

if not TOKEN or not OPENAI_API_KEY: print("❌ TOKEN ou OPENAI_API_KEY manquant") exit()

-------- DATA --------

user_messages = defaultdict(list)

CA_BASE = "0x4db4c0a8399d0a1e00110656a38f6dc5a94c4191" CA_BLUM = "EQAN2MV2quj5n9CluKtoXI4tSCql_D_wzhw5c5RvngI_O4Hx" allowed_links = ["deeptrade.bio.link", "base.app", "t.me/blum"] GIF_FILE = "lv_0_20260310200554.gif"

-------- AI --------

import openai openai.api_key = OPENAI_API_KEY

async def ask_ai(prompt): try: response = openai.ChatCompletion.create( model="gpt-3.5-turbo", messages=[ {"role": "system", "content": "You are a helpful crypto community assistant."}, {"role": "user", "content": prompt} ], max_tokens=100, temperature=0.7 ) return response["choices"][0]["message"]["content"] except Exception as e: print("AI error:", e) return "🤖 AI temporarily unavailable."

-------- COMMANDS --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): keyboard = [ [InlineKeyboardButton("Links 🔗", callback_data="links")], [InlineKeyboardButton("Invite 📢", callback_data="invite")], [InlineKeyboardButton("Tokens 💎", callback_data="tokens")], [InlineKeyboardButton("Leaderboard 🏆", callback_data="leaderboard")] ] reply_markup = InlineKeyboardMarkup(keyboard)

await update.message.reply_text(
    "👋 Welcome to VEO & UNITY\n🌍 One World Peace Coins ecosystem",
    reply_markup=reply_markup
)

async def links(update: Update, context: ContextTypes.DEFAULT_TYPE): text = ( f"💠 Base CA:\n{CA_BASE}\n\n" f"💎 Blum CA:\n{CA_BLUM}\n\n" "🌐 Website:\nhttps://deeptrade.bio.link" ) await update.message.reply_text(text)

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("📢 Invite friends and grow the VEO & UNITY community 🚀")

-------- WELCOME --------

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE): for member in update.message.new_chat_members: await update.message.reply_animation(animation=open(GIF_FILE, 'rb'), caption=f"👋 Welcome {member.full_name}!")

-------- CALLBACK HANDLER --------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE): query = update.callback_query await query.answer() data = query.data

if data == "links":
    await links(update, context)
elif data == "invite":
    await invite(update, context)
elif data == "tokens":
    await query.message.reply_text(f"Base: {CA_BASE}\nBlum: {CA_BLUM}")
elif data == "leaderboard":
    # dummy leaderboard
    leaderboard_text = "🏆 Top Active Members:\n1. Alice - 5 pts\n2. Bob - 3 pts\n3. Charlie - 2 pts"
    await query.message.reply_text(leaderboard_text)

-------- MESSAGE HANDLER --------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE): if update.message.from_user.is_bot: return text = (update.message.text or "").lower() user_id = update.message.from_user.id

# quick crypto answers
if "ca" in text or "contract" in text:
    await update.message.reply_text(f"💠 Contract Address\nBase: {CA_BASE}\nBlum: {CA_BLUM}")
    return

if "buy" in text:
    await update.message.reply_text("🚀 Buy VEO / UNITY\nhttps://base.app\nor use Blum Mini App")
    return

# anti-spam
user_messages[user_id].append(update.message.date)
if len(user_messages[user_id]) > 6:
    try: await update.message.delete()
    except: pass
    user_messages[user_id].clear()
    return

# anti-scam
if re.search(r"http|t\.me|\.com|\.xyz", text) and not any(link in text for link in allowed_links):
    try: await update.message.delete()
    except: pass
    return

reply = await ask_ai(text)
await update.message.reply_text(f"🤖 {reply}")

-------- AUTO HYPE (OPTIONAL) --------

async def auto_hype(context: ContextTypes.DEFAULT_TYPE): if GROUP_ID: await context.bot.send_message(chat_id=GROUP_ID, text="🚀 OWPC HYPE MESSAGE 🔥")

-------- MAIN --------

async def main(): app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("links", links))
app.add_handler(CommandHandler("invite", invite))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/leaderboard$"), handle_message))
app.add_handler(app.callback_query_handler(button_handler))

# optional JobQueue
if hasattr(app, 'job_queue') and GROUP_ID:
    app.job_queue.run_repeating(auto_hype, interval=60*60*4, first=10)

print("🚀 Bot démarré")
await app.run_polling(drop_pending_updates=True)

if name == "main": asyncio.run(main())