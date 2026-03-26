from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import database
from pydantic import BaseModel

# Le préfixe est défini ICI une seule fois
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

# IMPORTANT : Juste "/buy", pas "/api/launcher/buy"
@router.post("/buy")
async def buy_token(req: TradeRequest):
    print(f"📥 Tentative d'achat : User {req.user_id} -> Token {req.token_id}")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Check solde
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        u = c.fetchone()
        if not u or float(u[0]) < req.amount_wpt:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Solde insuffisant"})

        # 2. Check token
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (req.token_id,))
        t = c.fetchone()
        if not t:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Token introuvable"})
            
        qty = req.amount_wpt / float(t[0])

        # 3. Exécution de la transaction
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount_wpt, req.user_id))
        
        c.execute("""
            INSERT INTO user_community_assets (user_id, token_id, amount) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, token_id) 
            DO UPDATE SET amount = user_community_assets.amount + %s
        """, (req.user_id, req.token_id, qty, qty))
        
        c.execute("UPDATE community_tokens SET price = price * 1.01 WHERE id = %s", (req.token_id,))
        
        conn.commit()
        print(f"✅ Achat réussi : {qty} tokens pour l'user {req.user_id}")
        return {"ok": True, "received": qty}
    except Exception as e:
        conn.rollback()
        print(f"❌ Erreur achat : {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()


class DeployRequest(BaseModel):
    user_id: int
    name: str
    symbol: str
    description: str = ""
    logo: str = ""
    banner: str = ""

@router.post("/deploy")
async def deploy_token(req: DeployRequest):
    print(f"🚀 Nouveau déploiement : {req.name} par {req.user_id}")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérifier si l'utilisateur a assez de fonds pour les frais (ex: 10 WPT)
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        res = c.fetchone()
        if not res or float(res[0]) < 10:
            return {"ok": False, "error": "Frais de déploiement insuffisants (10 WPT requis)"}

        # 2. Prélever les frais
        c.execute("UPDATE users SET p_genesis = p_genesis - 10 WHERE user_id = %s", (req.user_id,))

        # 3. Créer le token
        # On initialise le prix à 0.0001 et la supply à 0
        query = """
            INSERT INTO community_tokens (name, symbol, description, logo, banner, price, supply, creator_id)
            VALUES (%s, %s, %s, %s, %s, 0.0001, 0, %s)
            RETURNING id
        """
        c.execute(query, (req.name, req.symbol, req.description, req.logo, req.banner, req.user_id))
        new_id = c.fetchone()[0]

        conn.commit()
        return {"ok": True, "token_id": new_id}

    except Exception as e:
        conn.rollback()
        print(f"❌ Erreur Deploy: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()


@router.get("/history/{tid}")
async def get_token_history(tid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    c.execute("SELECT price FROM token_price_history WHERE token_id = %s ORDER BY timestamp ASC LIMIT 50", (tid,))
    prices = [float(r[0]) for r in c.fetchall()]
    c.close(); conn.close()
    return prices


