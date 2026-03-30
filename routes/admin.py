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
