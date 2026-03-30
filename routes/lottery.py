from fastapi import APIRouter
import database
import random
import time
from datetime import datetime

router = APIRouter(prefix="/api/lottery", tags=["lottery"])

# --- 1. ACHETER DES TICKETS ---
@router.post("/buy-ticket")
async def buy_lottery_ticket(user_id: int, quantity: int):
    price_per_ticket = 1000 
    total_cost = price_per_ticket * quantity
    
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Check balance
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (user_id,))
        res = c.fetchone()
        balance = res[0] if res else 0

        if balance < total_cost:
            return {"ok": False, "error": "Not enough WPT balance"}

        # Deduct WPT and Add tickets
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (total_cost, user_id))
        
        # INSERT or UPDATE tickets for current week
        c.execute("""
            INSERT INTO lottery_tickets (user_id, tickets_count, week_number) 
            VALUES (%s, %s, EXTRACT(WEEK FROM CURRENT_DATE))
            ON CONFLICT (user_id, week_number) 
            DO UPDATE SET tickets_count = lottery_tickets.tickets_count + %s
        """, (user_id, quantity, quantity))
        
        conn.commit()
        return {"ok": True, "msg": f"Successfully purchased {quantity} tickets!"}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()

# --- 2. INFOS JACKPOT & USER TICKETS ---
@router.get("/info")
async def get_lottery_info(user_id: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Get global Jackpot (All tickets sold this week)
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        total_tickets = c.fetchone()[0] or 0
        jackpot = total_tickets * 1000
        
        # Get specific User tickets
        c.execute("SELECT tickets_count FROM lottery_tickets WHERE user_id = %s AND week_number = EXTRACT(WEEK FROM CURRENT_DATE)", (user_id,))
        user_res = c.fetchone()
        user_tickets = user_res[0] if user_res else 0
        
        return {"jackpot": jackpot, "user_tickets": user_tickets}
    except Exception as e:
        return {"jackpot": 0, "user_tickets": 0, "error": str(e)}
    finally:
        c.close(); conn.close()

# --- 3. LE TIRAGE (Draw) ---
# async def draw_lottery():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT user_id, tickets_count FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        participants = c.fetchall()
        
        if not participants: 
            print("No participants for this draw.")
            return

        pool = []
        for uid, count in participants:
            pool.extend([uid] * count)

        winner_id = random.choice(pool)
        
        # Jackpot: 80% to winner, 20% burned 🔥
        total_tickets = len(pool)
        total_pot = total_tickets * 1000
        jackpot = total_pot * 0.8
        burned_amount = total_pot * 0.2
        
        # Pay the winner
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (jackpot, winner_id))
        
        # Log the winner
        c.execute("INSERT INTO lottery_winners (user_id, amount_won) VALUES (%s, %s)", (winner_id, jackpot))
        
        # Update Burn Stats
        c.execute("UPDATE global_stats SET total_burned = total_burned + %s", (burned_amount,))
        
        conn.commit()
        print(f"🎉 Winner picked: {winner_id} won {jackpot} WPT!")
    except Exception as e:
        print(f"Error during draw: {e}")
    finally:
        c.close(); conn.close()
