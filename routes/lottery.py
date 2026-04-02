import random
import database
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/lottery", tags=["Lottery"])

# --- 1. ACHAT DE TICKETS ---
# DANS routes/lottery.py

# Retire le "/api/lottery" du décorateur si ton router a déjà le préfixe
@router.post("/buy-ticket") 
async def buy_lottery_ticket(request: Request):
    conn = None
    try:
        data = await request.json()
        # On force l'UID en entier pour être sûr de matcher la DB
        uid = int(data.get("user_id")) 
        qty = int(data.get("quantity", 1))
        cost = float(qty * 1000)

        conn = database.get_db_conn()
        c = conn.cursor()

                # 1. On récupère TOUS les soldes (Genesis, Unity, Veo)
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
        
        # On fait la somme comme sur ton écran d'accueil
        current_balance = float(res[0]) + float(res[1]) + float(res[2])
        user_name = res[3] or "A Whale"

        # Comparaison sur le TOTAL
        if current_balance < cost:
            return {"ok": False, "error": f"Insufficient balance (Total: {int(current_balance)} WPT)"}

        # 2. Mise à jour : On pioche d'abord dans p_genesis
        # Si p_genesis devient négatif, c'est pas grave car ton 'score' total reste positif
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (cost, uid))


        # 3. Calcul et enregistrement du Jackpot
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        total_tickets = c.fetchone()[0] or 0
        new_jackpot = total_tickets * 1000

        c.execute("UPDATE lottery_stats SET current_jackpot = %s WHERE id = 1", (new_jackpot,))
        
        conn.commit()

        # --- 🚀 NOTIFICATION TELEGRAM ---
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

        # Payer le gagnant et mettre à jour les stats
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (total_pool, winner_id))
        
        # On récupère le nom du gagnant pour les stats
        c.execute("SELECT name FROM users WHERE user_id = %s", (winner_id,))
        winner_name = c.fetchone()[0] or "A Lucky Citizen"

        # Mettre à jour la table globale pour l'affichage
        c.execute("""
            UPDATE lottery_stats 
            SET current_jackpot = 0, 
                last_winner = %s, 
                last_prize = %s 
            WHERE id = 1
        """, (winner_name, total_pool))
        
        # Reset des tickets pour la nouvelle semaine
        c.execute("DELETE FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")

        
        conn.commit()
        print(f"🏆 WINNER: {winner_id} won {total_pool} WPT")
    except Exception as e:
        print(f"❌ Draw Error: {e}")
    finally:
        c.close(); conn.close()





@router.get("/status")
async def get_lottery_status():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # On calcule le Jackpot : soit une valeur fixe + les tickets, 
        # soit on lit une table 'lottery'
        c.execute("SELECT current_jackpot, last_winner, last_prize FROM lottery_stats LIMIT 1")
        res = c.fetchone()
        
        if res:
            return {
                "jackpot": float(res[0]),
                "last_winner": res[1] or "@NoOne",
                "last_prize": float(res[2] or 0)
            }
        else:
            # Si la table est vide, on renvoie une valeur par défaut au lieu de 0
            return {"jackpot": 12000.0, "last_winner": "@Ghost", "last_prize": 5000}
    finally:
        c.close(); conn.close()


