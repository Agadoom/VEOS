import random
import database
from fastapi import APIRouter, Request

router = APIRouter()

# --- 1. ACHAT DE TICKETS ---
# DANS routes/lottery.py

@router.post("/api/lottery/buy-ticket")
async def buy_lottery_ticket(request: Request):
    try:
        data = await request.json()
        uid = data.get("user_id")
        qty = int(data.get("quantity", 1))
        cost = qty * 1000

        conn = database.get_db_conn()
        c = conn.cursor()

        # 1. Check balance & Name
        c.execute("SELECT p_genesis, name FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res or res[0] < cost:
            return {"ok": False, "error": "Insufficient balance"}
        
        user_name = res[1] or "A Whale"

        # 2. Update DB
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (cost, uid))
        c.execute("""
            INSERT INTO lottery_tickets (user_id, tickets_count, week_number) 
            VALUES (%s, %s, EXTRACT(WEEK FROM CURRENT_DATE))
            ON CONFLICT (user_id, week_number) 
            DO UPDATE SET tickets_count = lottery_tickets.tickets_count + %s
        """, (uid, qty, qty))

        # 3. Calcul du nouveau Jackpot pour le message
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        new_jackpot = (c.fetchone()[0] or 0) * 1000
        
        conn.commit()

        # --- 🚀 NOTIFICATION TELEGRAM ---
        try:
            # On récupère l'instance du bot stockée dans app.state
            bot = request.app.state.bot
            text = (
                f"🎟️ <b>New Tickets Purchased!</b>\n\n"
                f"👤 <b>User:</b> {user_name}\n"
                f"🎫 <b>Amount:</b> {qty} tickets\n"
                f"💰 <b>Current Jackpot:</b> {new_jackpot:,} WPT\n\n"
                f"🍀 <i>Check the App to try your luck!</i>"
            )
            # Utilise l'ID de ton groupe/canal défini dans config.py
            import config
            await bot.send_message(chat_id=config.LOTTERY_CHANNEL_ID, text=text, parse_mode="HTML")
        except Exception as e:
            print(f"⚠️ Telegram Notify Error: {e}")

        return {"ok": True}

    except Exception as e:
        print(f"❌ Error: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()








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


