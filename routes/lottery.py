from fastapi import APIRouter, Request
import database # Ton module de connexion DB

router = APIRouter()

@router.post("/api/lottery/buy-ticket")
async def buy_lottery_ticket(request: Request):
    try:
        data = await request.json()
        uid = data.get("user_id")
        qty = int(data.get("quantity", 1))
        cost = qty * 1000  # 1,000 WPT par ticket

        conn = database.get_db_conn()
        c = conn.cursor()

        # 1. Vérification du solde Genesis (p_genesis)
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res or res[0] < cost:
            return {"ok": False, "error": "Insufficient WPT balance"}

        # 2. Déduction des WPT
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (cost, uid))

        # 3. Ajout des tickets (Semaine actuelle)
        c.execute("""
            INSERT INTO lottery_tickets (user_id, tickets_count, week_number) 
            VALUES (%s, %s, EXTRACT(WEEK FROM CURRENT_DATE))
            ON CONFLICT (user_id, week_number) 
            DO UPDATE SET tickets_count = lottery_tickets.tickets_count + %s
        """, (uid, qty, qty))

        conn.commit()
        return {"ok": True}
    except Exception as e:
        print(f"Error Lottery Buy: {e}")
        return {"ok": False, "error": "Server error"}
    finally:
        c.close(); conn.close()

@router.get("/api/lottery/info")
async def get_lottery_info(user_id: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Jackpot Total (Somme des tickets * 1000)
        c.execute("SELECT SUM(tickets_count) FROM lottery_tickets WHERE week_number = EXTRACT(WEEK FROM CURRENT_DATE)")
        total_tickets = c.fetchone()[0] or 0
        jackpot = total_tickets * 1000

        # Tickets de l'utilisateur
        c.execute("SELECT tickets_count FROM lottery_tickets WHERE user_id = %s AND week_number = EXTRACT(WEEK FROM CURRENT_DATE)", (user_id,))
        u_res = c.fetchone()
        user_tickets = u_res[0] if u_res else 0

        return {
            "ok": True,
            "jackpot": jackpot if jackpot > 0 else 8500, # Base de départ
            "user_tickets": user_tickets,
            "total_tickets": total_tickets,
            "last_winner": "None yet"
        }
    finally:
        c.close(); conn.close()
