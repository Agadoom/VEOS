from fastapi import APIRouter, Request, HTTPException
from telegram import LabeledPrice
import config

router = APIRouter(prefix="/api/stars", tags=["Stars"])

import os
from pydantic import BaseModel

# 1. Le modèle pour recevoir les données du JS
class InvoiceRequest(BaseModel):
    user_id: int
    stars: int

# 2. La route en POST
@router.post("/create-invoice")
async def create_invoice(req: InvoiceRequest):
    token = os.getenv("BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/createInvoiceLink"
    
    payload = {
        "title": f"Buy {req.stars} Stars",
        "description": f"Boost your OWPC account with {req.stars} Telegram Stars!",
        "payload": f"user_id_{req.user_id}_stars_{req.stars}",
        "provider_token": "", # DOIT rester vide pour les Stars (XTR)
        "currency": "XTR",
        "prices": [{"label": "Stars", "amount": int(req.stars)}]
    }
    
    r = requests.post(url, json=payload)
    res = r.json()
    
    if not res.get("ok"):
        print(f"❌ Telegram Error: {res.get('description')}") # Regarde tes logs Railway !
        return JSONResponse(status_code=400, content={"error": res.get("description")})
        
    return {"invoice_link": res["result"]}
": str(e)})