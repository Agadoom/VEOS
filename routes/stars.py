from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import os
import requests
from pydantic import BaseModel

router = APIRouter(prefix="/api/stars", tags=["Stars"])

# 1. Modèle de données pour la requête
class InvoiceRequest(BaseModel):
    user_id: int
    stars: int

# 2. Route POST pour créer le lien de paiement
@router.post("/create-invoice")
async def create_invoice(req: InvoiceRequest):
    token = os.getenv("BOT_TOKEN")
    if not token:
        return JSONResponse(status_code=500, content={"error": "BOT_TOKEN not configured on Railway"})

    url = f"https://api.telegram.org/bot{token}/createInvoiceLink"
    
    # Configuration de la facture pour les Telegram Stars
    payload = {
        "title": f"Buy {req.stars} Stars",
        "description": f"Boost your OWPC account with {req.stars} Telegram Stars!",
        "payload": f"user_id_{req.user_id}_stars_{req.stars}",
        "provider_token": "",  # Toujours vide pour les Stars (XTR)
        "currency": "XTR",
        "prices": [{"label": "Stars", "amount": int(req.stars)}]
    }
    
    try:
        r = requests.post(url, json=payload)
        res = r.json()
        
        if res.get("ok"):
            return {"invoice_link": res["result"]}
        else:
            print(f"❌ Telegram Error: {res.get('description')}")
            return JSONResponse(status_code=400, content={"error": res.get("description")})
            
    except Exception as e:
        print(f"❌ Crash API Stars: {str(e)}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})

# --- NETTOYAGE EFFECTUÉ : LES LIGNES MORTES ONT ÉTÉ SUPPRIMÉES ---
