from fastapi import APIRouter, HTTPException
import database
import config

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/stats/{admin_id}")
async def get_admin_stats(admin_id: int):
    # --- SÉCURITÉ : Seul TOI peux voir ça ---
    if admin_id != config.ADMIN_ID: # Ajoute ADMIN_ID dans ton config.py
        raise HTTPException(status_code=403, detail="Access Denied")

    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Stats Utilisateurs
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]

        # 2. Économie WPT (Supply & Burn)
        c.execute("SELECT SUM(p_genesis + p_unity + p_veo) FROM users")
        total_supply = c.fetchone()[0] or 0
        
        c.execute("SELECT total_burned FROM global_stats WHERE id = 1")
        total_burned = c.fetchone()[0] or 0

        # 3. Stats Loterie de la semaine
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        weekly_tickets = c.fetchone()[0] or 0
        current_jackpot = weekly_tickets * 1000

        # 4. Top 5 Whales (Détails)
        c.execute("""
            SELECT name, (p_genesis + p_unity + p_veo) as total 
            FROM users ORDER BY total DESC LIMIT 5
        """)
        whales = [{"name": r[0], "balance": round(r[1], 2)} for r in c.fetchall()]

        return {
            "users": total_users,
            "supply": round(total_supply, 2),
            "burned": round(total_burned, 2),
            "jackpot": current_jackpot,
            "tickets": weekly_tickets,
            "whales": whales,
            "wpt_price": 0.0001 + (float(total_burned) * 0.00000001)
        }
    finally:
        c.close(); conn.close()
