from fastapi import APIRouter, Request, JSONResponse
from telegram import LabeledPrice
import database, uuid, random

router = APIRouter(prefix="/api/launcher", tags=["Launcher"])

# We will import bot_instance from main later via a clever trick or global
from __main__ import bot_instance 

@router.get("/list")
async def get_tokens():
    return database.get_community_tokens()

@router.post("/buy-request")
async def buy_token_request(request: Request):
    data = await request.json()
    uid, tid = data.get("user_id"), data.get("token_id")
    qty, cost_wpt = 100, 50 # Settings: 100 tokens cost 50 WPT
    
    user_data = database.get_user_full(uid)
    if (user_data[0] or 0) < cost_wpt:
        return JSONResponse(status_code=400, content={"error": "Insufficient WPT (Genesis) balance"})

    # Prepare Stars Invoice for the Service Fee
    payload = f"buy|{uid}|{tid}|{qty}|{cost_wpt}"
    link = await bot_instance.bot.create_invoice_link(
        title="Transaction Fee",
        description=f"Purchase of {qty} community tokens",
        payload=payload, provider_token="", currency="XTR",
        prices=[LabeledPrice("Service Fee", 10)] # 10 Stars Fee
    )
    return {"ok": True, "link": link}

@router.post("/sell")
async def sell_token(request: Request):
    data = await request.json()
    uid, tid, qty = data.get("user_id"), data.get("token_id"), float(data.get("amount", 0))
    
    conn = database.get_db_conn()
    c = conn.cursor()
    c.execute("SELECT amount FROM user_community_assets WHERE user_id=%s AND token_id=%s", (uid, tid))
    res = c.fetchone()
    
    if not res or res[0] < qty:
        return JSONResponse(status_code=400, content={"error": "Insufficient token balance"})
    
    c.execute("SELECT price FROM community_tokens WHERE id=%s", (tid,))
    price = c.fetchone()[0]
    gain = qty * price
    
    c.execute("UPDATE user_community_assets SET amount = amount - %s WHERE user_id=%s AND token_id=%s", (qty, uid, tid))
    c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id=%s", (gain, uid))
    conn.commit()
    c.close()
    conn.close()
    return {"ok": True, "gain": gain}

@router.get("/chart/{tid}")
async def get_chart(tid: int):
    points = [random.uniform(0.0001, 0.001) for _ in range(15)]
    points.sort() 
    return {"points": points}
