from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from telegram import LabeledPrice
import database, uuid, random

router = APIRouter(prefix="/api/launcher", tags=["Launcher"])

# Storage for pending tokens (moved here to avoid circular import)
pending_tokens = {}

@router.get("/list")
async def get_tokens():
    tokens = database.get_community_tokens()
    # On s'assure que tout est compatible JSON (float, string, etc.)
    clean_tokens = []
    for t in tokens:
        clean_tokens.append({
            "id": t["id"],
            "name": str(t["name"]),
            "sym": str(t["sym"]),
            "price": float(t["price"]),
            "mcap": float(t["mcap"]),
            "logo": t["logo"] or "",
            "banner": t["banner"] or ""
        })
    return clean_tokens


@router.post("/save-pending")
async def save_pending(request: Request):
    data = await request.json()
    temp_id = str(uuid.uuid4())[:8]
    pending_tokens[temp_id] = data
    return {"ok": True, "temp_id": temp_id}

@router.post("/create-invoice")
async def api_create_invoice(request: Request):
    data = await request.json()
    temp_id = data.get("temp_id")
    token = pending_tokens.get(temp_id)
    
    # Access bot via app state
    bot = request.app.state.bot
    link = await bot.create_invoice_link(
        title=f"Launch {token['symbol']}", 
        description="Token creation service fee", 
        payload=temp_id, provider_token="", currency="XTR", 
        prices=[LabeledPrice("Creation Fee", 500)]
    )
    return {"ok": True, "link": link}

@router.post("/buy-request")
async def buy_token_request(request: Request):
    data = await request.json()
    uid, tid = data.get("user_id"), data.get("token_id")
    qty, cost_wpt = 100, 50 
    
    user_data = database.get_user_full(uid)
    if (user_data[0] or 0) < cost_wpt:
        return JSONResponse(status_code=400, content={"error": "Insufficient WPT balance"})

    payload = f"buy|{uid}|{tid}|{qty}|{cost_wpt}"
    
    # Access bot via app state
    bot = request.app.state.bot
    link = await bot.create_invoice_link(
        title="Transaction Fee",
        description=f"Purchase of {qty} tokens",
        payload=payload, provider_token="", currency="XTR",
        prices=[LabeledPrice("Service Fee", 10)]
    )
    return {"ok": True, "link": link}

# ... rest of your sell and chart code ...


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
