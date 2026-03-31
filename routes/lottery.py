from fastapi import APIRouter, Request # <--- FIX: Ajout de Request
import database
import random
from datetime import datetime
import config # <--- Import de tes IDs de canaux

router = APIRouter(prefix="/api/lottery", tags=["lottery"])

# --- 1. BUY TICKETS ---
# --- 1. BUY TICKET CORRIGÉ ---
@router.post("/lottery/buy-ticket") # Vérifie bien le chemin ici
async def buy_lottery_ticket(request: Request):
    # On récupère les données du JSON envoyé par le JS
    data = await request.json()
    user_id = data.get("user_id")
    quantity = int(data.get("quantity", 1))
    
    price_per_ticket = 1000 
    total_cost = price_per_ticket * quantity
    
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Check balance and Name
        c.execute("SELECT p_genesis, name FROM users WHERE user_id = %s", (user_id,))
        res = c.fetchone()
        
        if not res:
            return {"ok": False, "error": "User not found"}
            
        balance = res[0]
        user_name = res[1] or "A Whale"

        if balance < total_cost:
            # C'est ici que ça bloquait car balance était 0 (user_id non reçu)
            return {"ok": False, "error": f"Insufficient balance ({balance} WPT)"}

        # Deduct WPT and update Tickets
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (total_cost, user_id))
        
        # Ton code de mise à jour des tickets ici...
        # ... (Garde ton code INSERT INTO lottery_tickets)
        
        conn.commit()
        return {"ok": True, "msg": "Successfully purchased!"}
    except Exception as e:
        print(f"Erreur : {e}")
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()

# --- 2. GET INFO RÉEL (Pas simulé) ---
@router.get("/api/lottery/info")
async def get_lottery_info(user_id: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Récupérer le vrai Jackpot (Somme des tickets * 1000)
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        total_tickets = c.fetchone()[0] or 0
        jackpot = total_tickets * 1000
        
        # Tes tickets à toi
        c.execute("SELECT tickets_count FROM lottery_tickets WHERE user_id = %s AND week_number = EXTRACT(WEEK FROM CURRENT_DATE)", (user_id,))
        user_res = c.fetchone()
        user_tickets = user_res[0] if user_res else 0

        return {
            "ok": True,
            "jackpot": jackpot,
            "last_winner": "NEEV", # Tu pourras automatiser ça plus tard
            "user_tickets": user_tickets,
            "total_tickets": total_tickets
        }
    finally:
        c.close(); conn.close()


# --- 2. GET INFO ---
@router.get("/api/lottery/info")
async def get_lottery_info(user_id: int):
    # Ici, on simule des données, mais tu pourras les lier à ta DB plus tard
    return {
        "ok": True,
        "jackpot": 125000, # Montant total à gagner
        "last_winner": "NEEV", # Nom du dernier gagnant
        "user_tickets": 0, # À récupérer en DB selon l'user_id
        "total_tickets": 150 # Total des tickets en jeu
    }



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
