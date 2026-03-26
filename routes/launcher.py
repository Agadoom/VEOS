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
