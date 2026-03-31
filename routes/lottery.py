from fastapi import APIRouter, Request # <--- FIX: Ajout de Request
import database
import random
from datetime import datetime
import config # <--- Import de tes IDs de canaux

router = APIRouter(prefix="/api/lottery", tags=["lottery"])

# --- 1. BUY TICKETS ---
@router.post("/buy-ticket")
async def buy_lottery_ticket(user_id: int, quantity: int, request: Request):
    price_per_ticket = 1000 
    total_cost = price_per_ticket * quantity
    
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Check balance and Name
        c.execute("SELECT p_genesis, name FROM users WHERE user_id = %s", (user_id,))
        res = c.fetchone()
        balance = res[0] if res else 0
        user_name = res[1] if res else "A Whale"

        if balance < total_cost:
            return {"ok": False, "error": "Not enough WPT balance"}

        # Deduct WPT and update Tickets
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (total_cost, user_id))
        c.execute("""
            INSERT INTO lottery_tickets (user_id, tickets_count, week_number) 
            VALUES (%s, %s, EXTRACT(WEEK FROM CURRENT_DATE))
            ON CONFLICT (user_id, week_number) 
            DO UPDATE SET tickets_count = lottery_tickets.tickets_count + %s
        """, (user_id, quantity, quantity))
        
        # Calculate new Jackpot for the broadcast
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        new_jackpot = (c.fetchone()[0] or 0) * 1000
        
        conn.commit()

        # --- 🚀 TELEGRAM NOTIFICATION ---
        try:
            bot = request.app.state.bot
            text = (
                f"🎟️ <b>New Tickets Purchased!</b>\n\n"
                f"👤 <b>User:</b> {user_name}\n"
                f"🎫 <b>Amount:</b> {quantity} tickets\n"
                f"💰 <b>Current Jackpot:</b> {new_jackpot:,} WPT\n\n"
                f"🍀 <i>Check the App to try your luck!</i>"
            )
            await bot.send_message(chat_id=config.LOTTERY_CHANNEL_ID, text=text, parse_mode="HTML")
        except Exception as e:
            print(f"Broadcast Error: {e}")

        return {"ok": True, "msg": "Successfully purchased!"}
    finally:
        c.close(); conn.close()

# --- 2. GET INFO ---
@router.get("/lottery/info")
async def get_lottery_info(user_id: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Somme totale du Jackpot (ex: 1% de chaque mine ou tickets achetés)
        c.execute("SELECT pool_amount, last_winner_name FROM lottery_stats WHERE id = 1")
        lottery = c.fetchone()
        
        # 2. Nombre de tickets de l'utilisateur
        c.execute("SELECT tickets FROM users WHERE user_id = %s", (user_id,))
        user_data = c.fetchone()
        
        # 3. Total des tickets vendus pour le calcul des chances
        c.execute("SELECT SUM(tickets) FROM users")
        total_tickets = c.fetchone()[0] or 0

        return {
            "ok": True,
            "jackpot": lottery[0] if lottery else 0,
            "last_winner": lottery[1] if lottery else None,
            "user_tickets": user_data[0] if user_data else 0,
            "total_tickets": total_tickets
        }
    finally:
        c.close(); conn.close()


# --- 3. THE DRAW (Cron Job) ---
async def draw_lottery(bot): # <--- FIX: Reçoit le bot en argument
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT user_id, tickets_count FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        participants = c.fetchall()
        
        if not participants: 
            print("Draw: No participants.")
            return

        pool = []
        for uid, count in participants:
            pool.extend([uid] * count)

        winner_id = random.choice(pool)
        
        # Math: 80% to winner, 20% burned
        total_tickets = len(pool)
        total_pot = total_tickets * 1000
        jackpot_winner = total_pot * 0.8
        burned_amount = total_pot * 0.2
        
        # 1. Update Winner Balance
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (jackpot_winner, winner_id))
        
        # 2. Get Winner Name for Announcement
        c.execute("SELECT name FROM users WHERE user_id = %s", (winner_id,))
        winner_name = c.fetchone()[0] or "Lucky Citizen"

        # 3. Log winner & Burn
        c.execute("INSERT INTO lottery_winners (user_id, amount_won) VALUES (%s, %s)", (winner_id, jackpot_winner))
        c.execute("UPDATE global_stats SET total_burned = total_burned + %s", (burned_amount,))
        
        conn.commit()

        # --- 🚀 PUBLIC ANNOUNCEMENT ---
        announcement = (
            f"🎊 <b>WEEKLY DRAW COMPLETED!</b> 🎊\n\n"
            f"🏆 <b>Winner:</b> {winner_name}\n"
            f"💰 <b>Prize:</b> {jackpot_winner:,} WPT\n\n"
            f"🔥 <b>Burned:</b> {burned_amount:,} WPT deleted forever!\n\n"
            f"✨ Next round has already started. Good luck!"
        )
        await bot.send_message(chat_id=config.LOTTERY_CHANNEL_ID, text=announcement, parse_mode="HTML")

    except Exception as e:
        print(f"Critical Draw Error: {e}")
    finally:
        c.close(); conn.close()
