import random
import database
import time
from fastapi import APIRouter, Request
from datetime import datetime

router = APIRouter(prefix="/api/lottery", tags=["Lottery"])

# --- 1. ACHAT DE TICKETS (CORRIGÉ) ---
@router.post("/buy-ticket") 
async def buy_lottery_ticket(request: Request):
    conn = None
    try:
        data = await request.json()
        uid = int(data.get("user_id")) 
        qty = int(data.get("quantity", 1))
        cost = float(qty * 1000)

        conn = database.get_db_conn()
        c = conn.cursor()

        # A. Vérification du solde total (Genesis + Unity + Veo)
        c.execute("""
            SELECT 
                COALESCE(p_genesis, 0), 
                COALESCE(p_unity, 0), 
                COALESCE(p_veo, 0), 
                name 
            FROM users WHERE user_id = %s
        """, (uid,))
        res = c.fetchone()
        
        if not res:
            return {"ok": False, "error": "Utilisateur introuvable."}
        
        current_balance = float(res[0]) + float(res[1]) + float(res[2])
        user_name = res[3] or "A Whale"

        if current_balance < cost:
            return {"ok": False, "error": f"Solde insuffisant (Total: {int(current_balance)} WPT)"}

        # B. DÉBIT DE L'ARGENT (On pioche dans p_genesis)
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (cost, uid))

        # C. ENREGISTREMENT DES TICKETS (Le fix était ici !)
        c.execute("""
            INSERT INTO lottery_tickets (user_id, tickets_count, week_number) 
            VALUES (%s, %s, EXTRACT(WEEK FROM CURRENT_DATE))
            ON CONFLICT (user_id, week_number) 
            DO UPDATE SET tickets_count = lottery_tickets.tickets_count + %s
        """, (uid, qty, qty))

        # D. MISE À JOUR DU JACKPOT GLOBAL (Stats)
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        total_tickets = c.fetchone()[0] or 0
        new_jackpot = total_tickets * 1000

        c.execute("UPDATE lottery_stats SET current_jackpot = %s WHERE id = 1", (new_jackpot,))
        
        conn.commit()

        # E. NOTIFICATION TELEGRAM
        try:
            bot = request.app.state.bot
            text = (
                f"🎟️ <b>New Tickets Purchased!</b>\n\n"
                f"👤 <b>User:</b> {user_name}\n"
                f"🎫 <b>Amount:</b> {qty} tickets\n"
                f"💰 <b>Current Jackpot:</b> {new_jackpot:,} WPT"
            )
            import config
            await bot.send_message(chat_id=config.LOTTERY_CHANNEL_ID, text=text, parse_mode="HTML")
        except: pass 

        return {"ok": True}

    except Exception as e:
        if conn: conn.rollback()
        print(f"❌ Erreur Achat Ticket: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        if conn: c.close(); conn.close()

# --- 2. LE MOTEUR DE TIRAGE ---
async def draw_lottery():
    print("🎲 Tirage de la Loterie en cours...")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Récupérer tous les tickets de la semaine
        c.execute("SELECT user_id, tickets_count FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        rows = c.fetchall()
        
        if not rows:
            print("🎰 Tirage annulé : Aucun ticket vendu cette semaine.")
            return

        # Création de l'urne (un ID répété selon son nombre de tickets)
        participants = []
        for uid, count in rows:
            participants.extend([uid] * count)

        # Désigner le gagnant
        winner_id = random.choice(participants)
        total_pool = len(participants) * 1000

        # Payer le gagnant
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (total_pool, winner_id))
        
        # Récupérer son nom
        c.execute("SELECT name FROM users WHERE user_id = %s", (winner_id,))
        winner_name = c.fetchone()[0] or "A Lucky Citizen"

        # Mettre à jour les stats historiques
        c.execute("""
            UPDATE lottery_stats 
            SET current_jackpot = 0, 
                last_winner = %s, 
                last_prize = %s 
            WHERE id = 1
        """, (winner_name, total_pool))
        
        # Supprimer les tickets pour la semaine prochaine
        c.execute("DELETE FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        
        conn.commit()
        print(f"🏆 GAGNANT : {winner_name} ({winner_id}) a remporté {total_pool} WPT")
    except Exception as e:
        print(f"❌ Erreur Tirage: {e}")
    finally:
        c.close(); conn.close()

# --- 3. STATUS GLOBAL ---
@router.get("/status")
async def get_lottery_status():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT current_jackpot, last_winner, last_prize FROM lottery_stats WHERE id = 1")
        res = c.fetchone()
        if res:
            return {
                "jackpot": float(res[0]),
                "last_winner": res[1] or "@NoOne",
                "last_prize": float(res[2] or 0)
            }
        return {"jackpot": 0.0, "last_winner": "@Ghost", "last_prize": 0}
    finally:
        c.close(); conn.close()

# --- 4. TICKETS DE L'UTILISATEUR ---
@router.get("/user-tickets/{uid}")
async def get_user_tickets(uid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT tickets_count FROM lottery_tickets 
            WHERE user_id = %s AND week_number = EXTRACT(WEEK FROM CURRENT_DATE)
        """, (uid,))
        res = c.fetchone()
        return {"count": res[0] if res else 0}
    finally:
        c.close(); conn.close()
