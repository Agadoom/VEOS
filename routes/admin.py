from fastapi import APIRouter, HTTPException, Request
import database
import config
import asyncio # <--- Important pour ne pas se faire bannir par Telegram

# 1. INITIALISATION DU ROUTER (C'est ce qui manquait !) ⚡
router = APIRouter(prefix="/api/admin", tags=["Admin"])

# --- 🛰️ DASHBOARD STATS ---
@router.get("/stats/{admin_id}")
async def get_admin_stats(admin_id: int):
    if admin_id != config.ADMIN_ID:
        raise HTTPException(status_code=403, detail="Access Denied")

    conn = database.get_db_conn()
    c = conn.cursor()

 # --- AJOUTE CETTE LIGNE ICI ---
    # Ça met à jour ton propre statut dès que tu regardes le dashboard
    c.execute("UPDATE users SET last_energy_update = %s WHERE user_id = %s", (int(time.time()), admin_id))

    try:
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]

        c.execute("SELECT SUM(p_genesis + p_unity + p_veo) FROM users")
        total_supply = c.fetchone()[0] or 0
        
        c.execute("SELECT total_burned FROM global_stats WHERE id = 1")
        total_burned = c.fetchone()[0] or 0

        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        weekly_tickets = c.fetchone()[0] or 0
        
        c.execute("SELECT name, (p_genesis + p_unity + p_veo) as total FROM users ORDER BY total DESC LIMIT 5")
        whales = [{"name": r[0], "balance": round(r[1], 2)} for r in c.fetchall()]

        return {
            "users": total_users,
            "supply": round(total_supply, 2),
            "burned": round(total_burned, 2),
            "jackpot": weekly_tickets * 1000,
            "tickets": weekly_tickets,
            "whales": whales,
            "wpt_price": 0.0001 + (float(total_burned) * 0.00000001)
        }
    finally:
        c.close(); conn.close()

# --- 📢 GLOBAL BROADCAST ---
@router.post("/broadcast/{admin_id}")
async def send_broadcast(admin_id: int, request: Request):
    if admin_id != config.ADMIN_ID:
        return {"ok": False, "error": "Unauthorized access"}
    
    data = await request.json()
    message_text = data.get("message")
    
    if not message_text:
        return {"ok": False, "error": "No message provided"}

    bot = request.app.state.bot
    conn = database.get_db_conn()
    c = conn.cursor()
    
    try:
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        
        sent_count = 0
        for (uid,) in users:
            try:
                # Formatage du message broadcast
                text = f"📢 <b>SYSTEM ANNOUNCEMENT</b>\n\n{message_text}"
                await bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
                sent_count += 1
                # On évite de saturer l'API Telegram
                if sent_count % 25 == 0: await asyncio.sleep(1)
            except Exception as e:
                print(f"Skipping user {uid}: {e}")
                continue
                
        return {"ok": True, "sent": sent_count}
    finally:
        c.close(); conn.close()


from datetime import datetime, timedelta

@router.get("/stats/{admin_id}")
async def get_admin_stats(admin_id: int):
    if admin_id != config.ADMIN_ID:
        raise HTTPException(status_code=403, detail="Access Denied")

    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Utilisateurs Totaux
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]

        # 2. Utilisateurs ONLINE (Actifs les 5 dernières minutes)
        now_ts = int(time.time())
        five_mins_ago = now_ts - 300
        c.execute("SELECT COUNT(*) FROM users WHERE last_energy_update > %s", (five_mins_ago,))
        online_users = c.fetchone()[0]

        # 3. Économie WPT
        c.execute("SELECT SUM(p_genesis + p_unity + p_veo) FROM users")
        total_supply = c.fetchone()[0] or 0
        c.execute("SELECT total_burned FROM global_stats WHERE id = 1")
        total_burned = c.fetchone()[0] or 0

        # 4. Loterie
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        weekly_tickets = c.fetchone()[0] or 0

        # 5. DERNIÈRES ACTIVITÉS (Les 5 derniers achats de tickets)
        c.execute("""
            SELECT u.name, t.tickets_count, t.week_number 
            FROM lottery_tickets t 
            JOIN users u ON t.user_id = u.user_id 
            ORDER BY t.id DESC LIMIT 5
        """)
        recent_activity = [{"name": r[0], "qty": r[1]} for r in c.fetchall()]

        return {
            "users": total_users,
            "online": online_users,
            "supply": round(total_supply, 2),
            "burned": round(total_burned, 2),
            "jackpot": weekly_tickets * 1000,
            "tickets": weekly_tickets,
            "activity": recent_activity,
            "wpt_price": 0.0001 + (float(total_burned) * 0.00000001)
        }
    finally:
        c.close(); conn.close()

