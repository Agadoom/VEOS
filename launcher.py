from fastapi import APIRouter
from fastapi.responses import JSONResponse
import database
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
    c.execute("SELECT id, name, symbol, logo, banner, price FROM community_tokens ORDER BY id DESC")
    res = c.fetchall()
    c.close(); conn.close()
    return [{"id": r[0], "name": r[1], "symbol": r[2], "logo": r[3], "banner": r[4], "price": float(r[5])} for r in res]

@router.post("/buy") # <-- SURTOUT NE PAS METTRE /api/launcher ICI
async def buy_token(req: TradeRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Vérification solde
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        row = c.fetchone()
        if not row or float(row[0]) < req.amount_wpt:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Pas assez de WPT"})

        # Infos Token
        c.execute("SELECT price FROM community_tokens WHERE id = %s", (req.token_id,))
        t_row = c.fetchone()
        qty = req.amount_wpt / float(t_row[0])

        # Transaction
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount_wpt, req.user_id))
        c.execute("""
            INSERT INTO user_community_assets (user_id, token_id, amount) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, token_id) DO UPDATE SET amount = user_community_assets.amount + %s
        """, (req.user_id, req.token_id, qty, qty))
        
        c.execute("UPDATE community_tokens SET price = price * 1.01 WHERE id = %s", (req.token_id,))
        conn.commit()
        return {"ok": True, "received": qty}
    except Exception as e:
        conn.rollback()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        c.close(); conn.close()
