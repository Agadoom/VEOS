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
        # Vérification du solde
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        res = c.fetchone()
        user_wpt = float(res[0]) if res else 0.0
        
        if user_wpt < req.amount_wpt:
            return {"ok": False, "error": f"Solde insuffisant ({user_wpt} WPT)"}

        # Infos du token
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (req.token_id,))
        t_res = c.fetchone()
        if not t_res:
            return {"ok": False, "error": "Token introuvable"}
        
        current_price = float(t_res[0])
        if current_price <= 0: current_price = 0.000001
        
        amount_to_receive = req.amount_wpt / current_price

        # DÉBUT DE LA TRANSACTION
        # 1. Déduire WPT
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount_wpt, req.user_id))
        
        # 2. Ajouter Asset
        c.execute("""
            INSERT INTO user_community_assets (user_id, token_id, amount) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, token_id) 
            DO UPDATE SET amount = user_community_assets.amount + EXCLUDED.amount
        """, (req.user_id, req.token_id, amount_to_receive))

        # 3. Monter le prix
        new_price = current_price * 1.01 # +1% par achat pour tester
        c.execute("UPDATE community_tokens SET price = %s WHERE id = %s", (new_price, req.token_id))

        conn.commit()
        return {"ok": True, "received": amount_to_receive}

    except Exception as e:
        conn.rollback()
        print(f"DEBUG BUY ERROR: {e}")
        return {"ok": False, "error": str(e)} # On renvoie l'erreur réelle
    finally:
        c.close(); conn.close()


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
