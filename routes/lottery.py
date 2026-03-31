import random
import database
from fastapi import APIRouter, Request

router = APIRouter()

# --- 1. ACHAT DE TICKETS ---
@router.post("/api/lottery/buy-ticket")
async def buy_lottery_ticket(request: Request):
    try:
        data = await request.json()
        uid = data.get("user_id")
        qty = int(data.get("quantity", 1))
        cost = qty * 1000

        conn = database.get_db_conn()
        c = conn.cursor()

        # Vérifier solde
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res or res[0] < cost:
            return {"ok": False, "error": "Insufficient WPT"}

        # Retirer WPT
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (cost, uid))

        # Ajouter tickets
        c.execute("""
            INSERT INTO lottery_tickets (user_id, tickets_count, week_number) 
            VALUES (%s, %s, EXTRACT(WEEK FROM CURRENT_DATE))
            ON CONFLICT (user_id, week_number) 
            DO UPDATE SET tickets_count = lottery_tickets.tickets_count + %s
        """, (uid, qty, qty))

        conn.commit()
        return {"ok": True}
    except Exception as e:
        print(f"❌ Error Buy: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        if 'c' in locals(): c.close()
        if 'conn' in locals(): conn.close()

# --- 2. INFOS LOTERIE ---
@router.get("/api/lottery/info")
async def get_lottery_info(user_id: int):
    try:
        conn = database.get_db_conn()
        c = conn.cursor()
        
        # Jackpot
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        total_tickets = c.fetchone()[0] or 0
        jackpot = total_tickets * 1000

        # Tickets utilisateur
        c.execute("SELECT tickets_count FROM lottery_tickets WHERE user_id = %s AND week_number = EXTRACT(WEEK FROM CURRENT_DATE)", (user_id,))
        u_res = c.fetchone()
        user_tickets = u_res[0] if u_res else 0

        return {
            "ok": True,
            "jackpot": jackpot if jackpot > 0 else 8500,
            "user_tickets": user_tickets,
            "total_tickets": total_tickets,
            "last_winner": "None yet"
        }
    except Exception as e:
        print(f"❌ Error Info: {e}")
        return {"ok": False}
    finally:
        if 'c' in locals(): c.close()
        if 'conn' in locals(): conn.close()

# --- 3. LE MOTEUR DE TIRAGE (Pour APScheduler) ---
async def draw_lottery():
    print("🎲 Lottery Draw started...")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Récupérer participants
        c.execute("SELECT user_id, tickets_count FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        rows = c.fetchall()
        
        if not rows:
            print("🎰 Draw: No tickets this week.")
            return

        participants = []
        for uid, count in rows:
            participants.extend([uid] * count)

        # Tirage
        winner_id = random.choice(participants)
        total_pool = len(participants) * 1000

        # Payer le gagnant
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (total_pool, winner_id))
        
        # Reset
        c.execute("DELETE FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        
        conn.commit()
        print(f"🏆 WINNER: {winner_id} won {total_pool} WPT")
    except Exception as e:
        print(f"❌ Draw Error: {e}")
    finally:
        c.close(); conn.close()
