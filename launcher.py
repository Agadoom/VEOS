from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import database, config
from pydantic import BaseModel

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
        # On récupère tous les tokens actifs
        c.execute("SELECT id, name, symbol, logo, banner, price, supply FROM community_tokens ORDER BY id DESC")
        tokens = []
        for r in c.fetchall():
            tokens.append({
                "id": r[0], "name": r[1], "symbol": r[2],
                "logo": r[3], "banner": r[4], "price": float(r[5]), "supply": float(r[6])
            })
        return tokens
    finally:
        c.close(); conn.close()

@router.post("/buy")
async def buy_token(req: TradeRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérifier le solde WPT de l'utilisateur (p_genesis)
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        user_wpt = c.fetchone()
        if not user_wpt or user_wpt[0] < req.amount_wpt:
            return {"ok": False, "error": "Insufficient WPT balance"}

        # 2. Infos du token
        c.execute("SELECT price, supply, symbol FROM community_tokens WHERE id = %s", (req.token_id,))
        token = c.fetchone()
        if not token:
            return {"ok": False, "error": "Token not found"}
        
        current_price = float(token[0])
        amount_to_receive = req.amount_wpt / current_price

        # 3. TRANSACTION ATOMIQUE
        # Déduire WPT
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount_wpt, req.user_id))
        
        # Ajouter le token au wallet de l'utilisateur (ou update si déjà possédé)
        c.execute("""
            INSERT INTO user_community_assets (user_id, token_id, amount) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, token_id) 
            DO UPDATE SET amount = user_community_assets.amount + %s
        """, (req.user_id, req.token_id, amount_to_receive, amount_to_receive))

        # Faire monter le prix (Bonding Curve simple : +0.1% par achat)
        new_price = current_price * 1.001 
        c.execute("UPDATE community_tokens SET price = %s, supply = supply + %s WHERE id = %s", 
                  (new_price, amount_to_receive, req.token_id))

        conn.commit()
        return {"ok": True, "received": round(amount_to_receive, 2)}

    except Exception as e:
        conn.rollback()
        print(f"Trade Error: {e}")
        return {"ok": False, "error": "Internal Server Error"}
    finally:
        c.close(); conn.close()
