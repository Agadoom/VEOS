from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import database
from pydantic import BaseModel
import time

router = APIRouter(prefix="/api/launcher", tags=["Launcher"])

class TradeRequest(BaseModel):
    user_id: int
    token_id: int
    amount_wpt: float

@router.get("/list")
async def list_tokens():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT id, name, symbol, logo, banner, price FROM community_tokens ORDER BY id DESC")
        res = c.fetchall()
        return [{"id": r[0], "name": r[1], "symbol": r[2], "logo": r[3], "banner": r[4], "price": float(r[5])} for r in res]
    finally:
        c.close(); conn.close()

@router.post("/buy")
async def buy_token(req: TradeRequest):
    print(f"📥 Trade Attempt: User {req.user_id} -> Token {req.token_id}")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Balance check
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        u = c.fetchone()
        if not u or float(u[0]) < req.amount_wpt:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Insufficient Balance"})

        # 2. Token check
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (req.token_id,))
        t = c.fetchone()
        if not t:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Token not found"})
            
        qty = req.amount_wpt / float(t[0])

        # 3. Execution
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount_wpt, req.user_id))
        
        c.execute("""
            INSERT INTO user_community_assets (user_id, token_id, amount) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, token_id) 
            DO UPDATE SET amount = user_community_assets.amount + %s
        """, (req.user_id, req.token_id, qty, qty))
        
        c.execute("UPDATE community_tokens SET price = price * 1.01 WHERE id = %s", (req.token_id,))

        # Update Chart History
        c.execute("""
            INSERT INTO token_price_history (token_id, price, timestamp) 
            VALUES (%s, (SELECT price FROM community_tokens WHERE id = %s), %s)
        """, (req.token_id, req.token_id, int(time.time())))
        
        conn.commit()
        print(f"✅ Trade Success: {qty} tokens for UID {req.user_id}")
        return {"ok": True, "received": qty}
    except Exception as e:
        conn.rollback()
        print(f"❌ Trade Error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()

@router.get("/history/{tid}")
async def get_token_history(tid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT price FROM token_price_history WHERE token_id = %s ORDER BY timestamp ASC LIMIT 50", (tid,))
        prices = [float(r[0]) for r in c.fetchall()]
        return prices if prices else [0.0001]
    finally:
        c.close(); conn.close()


@router.post("/sell")
async def sell_token(req: TradeRequest):
    print(f"📉 Sell Attempt: User {req.user_id} -> Token {req.token_id}")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérifier si l'utilisateur possède bien ces tokens
        c.execute("SELECT amount FROM user_community_assets WHERE user_id = %s AND token_id = %s", (req.user_id, req.token_id))
        res = c.fetchone()
        
        # Ici req.amount_wpt représentera la QUANTITÉ de tokens à vendre
        if not res or float(res[0]) < req.amount_wpt:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Not enough tokens to sell"})

        # 2. Récupérer le prix actuel
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (req.token_id,))
        t = c.fetchone()
        current_price = float(t[0])
        
        # Valeur de la vente en WPT
        total_wpt = req.amount_wpt * current_price

        # 3. Exécution : Retirer tokens -> Ajouter WPT -> Baisser le prix
        c.execute("UPDATE user_community_assets SET amount = amount - %s WHERE user_id = %s AND token_id = %s", 
                  (req.amount_wpt, req.user_id, req.token_id))
        
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (total_wpt, req.user_id))
        
        # Le prix baisse de 1% par vente
        c.execute("UPDATE community_tokens SET price = price * 0.99 WHERE id = %s", (req.token_id,))

        # Mise à jour de l'historique (pour la courbe qui descend !)
        c.execute("""
            INSERT INTO token_price_history (token_id, price, timestamp) 
            VALUES (%s, (SELECT price FROM community_tokens WHERE id = %s), %s)
        """, (req.token_id, req.token_id, int(time.time())))

        conn.commit()
        print(f"✅ Sell Success: {total_wpt} WPT earned by UID {req.user_id}")
        return {"ok": True, "earned": total_wpt}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()



@router.get("/stats/{tid}")
async def get_token_stats(tid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Calcul du Supply Total et nombre de Holders
        c.execute("SELECT SUM(amount), COUNT(DISTINCT user_id) FROM user_community_assets WHERE token_id = %s", (tid,))
        res = c.fetchone()
        supply = float(res[0]) if res[0] else 0
        holders = res[1] if res[1] else 0
        
        # 2. Récupérer le prix
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (tid,))
        price = float(c.fetchone()[0])
        
        mcap = supply * price
        
        return {
            "mcap": round(mcap, 2),
            "holders": holders,
            "supply": round(supply, 2)
        }
    finally:
        c.close(); conn.close()


