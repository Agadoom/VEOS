from fastapi import APIRouter
from fastapi.responses import JSONResponse
import database, config, time
from pydantic import BaseModel

# On définit le préfixe UNE SEULE FOIS ici
router = APIRouter(prefix="/api/launcher", tags=["Launcher"])

class TradeRequest(BaseModel):
    user_id: int
    token_id: int
    amount_wpt: float

# URL réelle : /api/launcher/list
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

# URL réelle : /api/launcher/buy (C'est celle qui te donnait le 404)
@router.post("/buy")
async def buy_token(req: TradeRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérifier solde WPT (p_genesis)
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        row = c.fetchone()
        user_balance = float(row[0]) if row else 0
        
        if user_balance < req.amount_wpt:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Insufficient WPT"})

        # 2. Infos Token
        c.execute("SELECT price, symbol FROM community_tokens WHERE id = %s", (req.token_id,))
        t_row = c.fetchone()
        if not t_row:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Token not found"})
        
        price = float(t_row[0])
        qty = req.amount_wpt / price

        # 3. Exécution
        # Déduire WPT
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount_wpt, req.user_id))
        
        # Ajouter le Token (ON CONFLICT nécessite la contrainte unique sur la DB !)
        c.execute("""
            INSERT INTO user_community_assets (user_id, token_id, amount) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, token_id) 
            DO UPDATE SET amount = user_community_assets.amount + %s
        """, (req.user_id, req.token_id, qty, qty))

        # Monter le prix de 1%
        c.execute("UPDATE community_tokens SET price = price * 1.01 WHERE id = %s", (req.token_id,))

        conn.commit()
        return {"ok": True, "received": qty}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()
