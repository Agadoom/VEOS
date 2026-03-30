
from fastapi import APIRouter
import database
import random
from datetime import datetime

# C'est cette ligne qui manquait ! ⚡
router = APIRouter(prefix="/api/lottery", tags=["lottery"])



@router.post("/buy-ticket")
async def buy_lottery_ticket(user_id: int, quantity: int):
    price_per_ticket = 1000 # 1000 WPT le ticket
    total_cost = price_per_ticket * quantity
    
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérifier le solde
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (user_id,))
        balance = c.fetchone()[0]
        if balance < total_cost:
            return {"ok": False, "error": "Pas assez de WPT"}

        # 2. Déduire les WPT et ajouter les tickets
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (total_cost, user_id))
        
        # On insère ou on met à jour le nombre de tickets
        c.execute("""
            INSERT INTO lottery_tickets (user_id, tickets_count, week_number) 
            VALUES (%s, %s, EXTRACT(WEEK FROM CURRENT_DATE))
            ON CONFLICT (user_id, week_number) DO UPDATE SET tickets_count = lottery_tickets.tickets_count + %s
        """, (user_id, quantity, quantity))
        
        conn.commit()
        return {"ok": True, "msg": f"{quantity} tickets achetés !"}
    finally:
        c.close(); conn.close()





async def draw_lottery():
    conn = database.get_db_conn()
    c = conn.cursor()
    
    # 1. Récupérer tous les participants (un user avec 10 tickets a 10 chances)
    c.execute("SELECT user_id, tickets_count FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
    participants = c.fetchall()
    
    if not participants: return

    pool = []
    for uid, count in participants:
        pool.extend([uid] * count)

    import random
    winner_id = random.choice(pool)
    
    # 2. Calculer le Jackpot (ex: 80% des tickets vendus, 20% sont Burn 🔥)
    total_tickets = len(pool)
    jackpot = total_tickets * 1000 * 0.8
    
    # 3. Payer le gagnant
    c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (jackpot, winner_id))
    
    # 4. Enregistrer le gagnant
    c.execute("INSERT INTO lottery_winners (user_id, amount_won) VALUES (%s, %s)", (winner_id, jackpot))
    
    conn.commit()
    # Envoyer un message Telegram au gagnant ici via le bot



@router.get("/info")
async def get_lottery_info(user_id: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Jackpot total (Tickets vendus cette semaine * 1000)
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        total_tickets = c.fetchone()[0] or 0
        jackpot = total_tickets * 1000
        
        # Tickets de l'utilisateur
        c.execute("SELECT tickets_count FROM lottery_tickets WHERE user_id = %s AND week_number = EXTRACT(WEEK FROM CURRENT_DATE)", (user_id,))
        user_res = c.fetchone()
        user_tickets = user_res[0] if user_res else 0
        
        return {"jackpot": jackpot, "user_tickets": user_tickets}
    finally:
        c.close(); conn.close()


