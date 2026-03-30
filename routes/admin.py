from fastapi import Request

@router.post("/broadcast/{admin_id}")
async def send_broadcast(admin_id: int, request: Request):
    # 1. Vérification Admin
    if admin_id != config.ADMIN_ID:
        return {"ok": False, "error": "Unauthorized"}
    
    # 2. Récupérer le message depuis le corps de la requête
    data = await request.json()
    message_text = data.get("message")
    
    if not message_text:
        return {"ok": False, "error": "Empty message"}

    bot = request.app.state.bot
    conn = database.get_db_conn()
    c = conn.cursor()
    
    try:
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        
        count = 0
        for (uid,) in users:
            try:
                await bot.send_message(chat_id=uid, text=f"📢 <b>GLOBAL ANNOUNCEMENT</b>\n\n{message_text}", parse_mode="HTML")
                count += 1
                # Petit délai pour éviter le spam-ban de Telegram
                if count % 20 == 0: await asyncio.sleep(1) 
            except:
                continue # L'utilisateur a peut-être bloqué le bot
                
        return {"ok": True, "sent": count}
    finally:
        c.close(); conn.close()
