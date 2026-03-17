# -------- NOUVELLES FONCTIONS --------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid, name = query.from_user.id, query.from_user.first_name
    await query.answer()

    if query.data == "my_card":
        score = update_user(uid, name)[0]
        rank, next_val, msg = get_rank_info(score)
        bar = generate_progress_bar(score, next_val)
        
        # Ajout d'un bouton "Share" spécifique
        kb = [[InlineKeyboardButton("📣 Share my Status", switch_inline_query=f"Check my Rank: {rank}!")]]
        
        card = (
            f"💳 **OWPC DIGITAL PASSPORT**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Holder:** {name}\n"
            f"🏅 **Rank:** {rank}\n"
            f"⭐ **Points:** {score} pts\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📈 `{bar}`\n\n"
            f"Build the hive. Share your status! 🐝"
        )
        await query.message.reply_text(card, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data == "view_stats":
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT COUNT(*), SUM(score) FROM users")
        total_users, total_points = c.fetchone()
        conn.close()
        
        stats = (
            f"📊 **OWPC GLOBAL STATS**\n\n"
            f"👥 **Total Citizens:** {total_users}\n"
            f"💰 **Total Points Issued:** {total_points} pts\n"
            f"⚡ **Ecosystem Status:** Viral 🚀\n\n"
            f"We are growing together! 🕊️"
        )
        await query.message.reply_text(stats, parse_mode="Markdown")
