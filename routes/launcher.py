from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import database
from pydantic import BaseModel
import time

# On définit le préfixe une seule fois ici
router = APIRouter(prefix="/api/launcher", tags=["Launcher"])

# Modèle de données unique pour les transactions
class TradeRequest(BaseModel):
    user_id: int
    token_id: int
    amount: float  # 'amount' sera utilisé pour le montant WPT (achat) ou QUANTITÉ (vente)

@router.get("/list")
async def list_tokens():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT id, name, symbol, logo, banner, price FROM community_tokens ORDER BY id DESC")
        res = c.fetchall()
        return [{"id": r[0], "name": r[1], "symbol": r[2], "logo": r[3], "banner": r[4], "price": float(r[5])} for r in res]
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()

@router.post("/buy")
async def buy_token(req: TradeRequest):
    print(f"📥 Buy Attempt: User {req.user_id} -> Token {req.token_id} with {req.amount} WPT")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérification du solde Genesis (WPT) de l'utilisateur
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        u = c.fetchone()
        if not u or float(u[0]) < req.amount:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Insufficient WPT Balance"})

        # 2. Vérification du prix du Token
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (req.token_id,))
        t = c.fetchone()
        if not t:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Token not found"})
            
        current_price = float(t[0])
        qty_to_receive = req.amount / current_price

        # 3. Exécution : Retirer WPT -> Ajouter Asset -> Augmenter prix (Pump)
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount, req.user_id))
        
        c.execute("""
            INSERT INTO user_community_assets (user_id, token_id, amount) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, token_id) 
            DO UPDATE SET amount = user_community_assets.amount + %s
        """, (req.user_id, req.token_id, qty_to_receive, qty_to_receive))
        
        # Le prix monte de 1% par achat
        new_price = current_price * 1.01
        c.execute("UPDATE community_tokens SET price = %s WHERE id = %s", (new_price, req.token_id))

        # Historique pour le graphique
        c.execute("INSERT INTO token_price_history (token_id, price, timestamp) VALUES (%s, %s, %s)", 
                  (req.token_id, new_price, int(time.time())))
        
        conn.commit()
        return {"ok": True, "received": qty_to_receive}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()

@router.post("/sell")
async def sell_token(req: TradeRequest):
    print(f"📉 Sell Attempt: User {req.user_id} -> Token {req.token_id} Amount: {req.amount}")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérifier si l'utilisateur possède bien ces tokens (req.amount est ici la quantité de tokens)
        c.execute("SELECT amount FROM user_community_assets WHERE user_id = %s AND token_id = %s", (req.user_id, req.token_id))
        res = c.fetchone()
        
        if not res or float(res[0]) < req.amount:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Not enough tokens to sell"})

        # 2. Récupérer le prix actuel
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (req.token_id,))
        t = c.fetchone()
        current_price = float(t[0])
        total_wpt_earned = req.amount * current_price

        # 3. Exécution : Retirer tokens -> Ajouter WPT -> Baisser le prix (Dump)
        c.execute("UPDATE user_community_assets SET amount = amount - %s WHERE user_id = %s AND token_id = %s", 
                  (req.amount, req.user_id, req.token_id))
        
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (total_wpt_earned, req.user_id))
        
        # Le prix baisse de 1% par vente
        new_price = current_price * 0.99
        c.execute("UPDATE community_tokens SET price = %s WHERE id = %s", (new_price, req.token_id))

        # Historique
        c.execute("INSERT INTO token_price_history (token_id, price, timestamp) VALUES (%s, %s, %s)", 
                  (req.token_id, new_price, int(time.time())))

        conn.commit()
        return {"ok": True, "received": total_wpt_earned} # 'received' ici est le WPT gagné
    except Exception as e:
        conn.rollback()
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

@router.get("/stats/{tid}")
async def get_token_stats(tid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT SUM(amount), COUNT(DISTINCT user_id) FROM user_community_assets WHERE token_id = %s", (tid,))
        res = c.fetchone()
        supply = float(res[0]) if res and res[0] else 0
        holders = res[1] if res and res[1] else 0
        
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (tid,))
        p_res = c.fetchone()
        price = float(p_res[0]) if p_res else 0
        
        return {
            "mcap": round(supply * price, 2),
            "holders": holders
        }
    finally:
        c.close(); conn.close()
