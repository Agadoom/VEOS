from fastapi import APIRouter
import database
import random
import time
from datetime import datetime

router = APIRouter(prefix="/api/lottery", tags=["lottery"])

# --- 1. ACHETER DES TICKETS ---
@router.post("/buy-ticket")
async def buy_lottery_ticket(user_id: int, quantity: int, request: Request): # Ajoute request: Request
    price_per_ticket = 1000 
    total_cost = price_per_ticket * quantity
    
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérification solde
        c.execute("SELECT p_genesis, name FROM users WHERE user_id = %s", (user_id,))
        res = c.fetchone()
        balance = res[0] if res else 0
        user_name = res[1] if res else "A Whale"

        if balance < total_cost:
            return {"ok": False, "error": "Not enough WPT balance"}

        # 2. Update DB
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (total_cost, user_id))
        c.execute("""
            INSERT INTO lottery_tickets (user_id, tickets_count, week_number) 
            VALUES (%s, %s, EXTRACT(WEEK FROM CURRENT_DATE))
            ON CONFLICT (user_id, week_number) 
            DO UPDATE SET tickets_count = lottery_tickets.tickets_count + %s
        """, (user_id, quantity, quantity))
        
        # 3. Calcul du nouveau Jackpot pour l'annonce
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        new_jackpot = (c.fetchone()[0] or 0) * 1000
        
        conn.commit()

        # --- 🚀 NOTIFICATION TELEGRAM ---
        try:
            bot = request.app.state.bot
            import config
            # Message stylé pour le groupe
            text = (
                f"🎟️ <b>New Tickets Purchased!</b>\n\n"
                f"👤 <b>User:</b> {user_name}\n"
                f"🎫 <b>Amount:</b> {quantity} tickets\n"
                f"💰 <b>Current Jackpot:</b> {new_jackpot:,} WPT\n\n"
                f"🍀 <i>Try your luck in the App!</i>"
            )
            # On envoie au canal défini dans config.py
            await bot.send_message(chat_id=config.LOTTERY_CHANNEL_ID, text=text, parse_mode="HTML")
        except Exception as e:
            print(f"Notification Error: {e}")

        return {"ok": True, "msg": "Successfully purchased!"}
        
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
async def draw_lottery():
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
