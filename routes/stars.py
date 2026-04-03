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
    token = os.getenv("BOT_TOKEN") # Ton token BotFather
    
    url = f"https://api.telegram.org/bot{token}/createInvoiceLink"
    
    payload = {
        "title": f"Pack {req.stars} Stars",
        "description": f"Créditez votre compte OWPC avec {req.stars} Stars !",
        "payload": f"user_{req.user_id}_pack_{req.stars}",
        "provider_token": "", # Vide pour les Telegram Stars (XTR)
        "currency": "XTR",
        "prices": [{"label": "Stars", "amount": req.stars}]
    }
    
    try:
        r = requests.post(url, json=payload)
        res = r.json()
        
        if res.get("ok"):
            return {"invoice_link": res["result"]}
        else:
            return JSONResponse(status_code=400, content={"error": res.get("description")})
            
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})