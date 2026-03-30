from fastapi import APIRouter, HTTPException, Request
import database
import config
import asyncio
import time # <--- CRUCIAL : Ne pas oublier cet import !

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/stats/{admin_id}")
async def get_admin_stats(admin_id: int):
    # 1. Sécurité
    if admin_id != config.ADMIN_ID:
        raise HTTPException(status_code=403, detail="Access Denied")

    conn = database.get_db_conn()
    c = conn.cursor()
    
    try:
        # --- MISE À JOUR DE TON STATUT ONLINE ---
        # On utilise %s pour éviter les injections et on passe le timestamp actuel
        now_ts = int(time.time())
        c.execute("UPDATE users SET last_energy_update = %s WHERE user_id = %s", (now_ts, admin_id))
        
        # 2. Total Users
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]

        # 3. Online Users (Actifs depuis 5 min)
        five_mins_ago = now_ts - 300
        c.execute("SELECT COUNT(*) FROM users WHERE last_energy_update > %s", (five_mins_ago,))
        online_users = c.fetchone()[0]

        # 4. Économie
        c.execute("SELECT SUM(p_genesis + p_unity + p_veo) FROM users")
        total_supply = c.fetchone()[0] or 0
        
        c.execute("SELECT total_burned FROM global_stats WHERE id = 1")
        res_burn = c.fetchone()
        total_burned = res_burn[0] if res_burn else 0

        # 5. Loterie
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        weekly_tickets = c.fetchone()[0] or 0

        # 6. Activité Récente
        c.execute("""
            SELECT u.name, t.tickets_count 
            FROM lottery_tickets t 
            JOIN users u ON t.user_id = u.user_id 
            ORDER BY t.id DESC LIMIT 5
        """)
        activity = [{"name": r[0], "qty": r[1]} for r in c.fetchall()]

        conn.commit() # On valide l'UPDATE du statut online

        return {
            "users": total_users,
            "online": online_users,
            "supply": round(total_supply, 2),
            "burned": round(total_burned, 2),
            "jackpot": weekly_tickets * 1000,
            "tickets": weekly_tickets,
            "activity": activity,
            "wpt_price": 0.0001 + (float(total_burned) * 0.00000001)
        }
        
    except Exception as e:
        print(f"❌ Admin API Error: {e}")
        return {"error": str(e), "users": 0, "online": 0, "supply": 0, "burned": 0, "jackpot": 0, "tickets": 0, "activity": []}
    finally:
        c.close()
        conn.close()

# --- Garde ta route @router.post("/broadcast") ici en dessous ---


# --- 📢 GLOBAL BROADCAST ---
@router.post("/broadcast/{admin_id}")
async def send_broadcast(admin_id: int, request: Request):
    # 1. Sécurité Admin
    if admin_id != config.ADMIN_ID:
        return {"ok": False, "error": "Unauthorized access"}
    
    # 2. Récupérer le message
    try:
        data = await request.json()
        message_text = data.get("message")
    except:
        return {"ok": False, "error": "Invalid JSON data"}
    
    if not message_text:
        return {"ok": False, "error": "Message is empty"}

    bot = request.app.state.bot
    conn = database.get_db_conn()
    c = conn.cursor()
    
    try:
        # On récupère tous les IDs des utilisateurs enregistrés
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        
        sent_count = 0
        failed_count = 0

        for (uid,) in users:
            try:
                # On envoie le message formaté
                text = f"📢 <b>GLOBAL ANNOUNCEMENT</b>\n\n{message_text}"
                await bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
                sent_count += 1
                
                # Anti-Spam Telegram : On fait une mini pause tous les 30 messages
                if sent_count % 30 == 0:
                    await asyncio.sleep(1)
            except Exception:
                failed_count += 1
                continue # L'utilisateur a peut-être bloqué le bot
                
        return {"ok": True, "sent": sent_count, "failed": failed_count}
        
    except Exception as e:
        print(f"Broadcast error: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        c.close()
        conn.close()

