from fastapi import APIRouter, Request, HTTPException
from telegram import LabeledPrice
import config

router = APIRouter(prefix="/api/stars", tags=["Stars"])

import os
from pydantic import BaseModel

class InvoiceRequest(BaseModel):
    user_id: int
    stars: int

@router.get("/create-invoice")
async def create_invoice(req: InvoiceRequest):
    # Remplace par ton TOKEN BOT Telegram (celui de BotFather)
    BOT_TOKEN = os.getenv("BOT_TOKEN") 
    
    # Configuration de la facture (Prix en Stars)
    title = f"{req.stars} Stars Pack"
    description = f"Get {req.stars} Stars and bonus WPT for your OWPC account!"
    payload = f"stars_pack_{req.user_id}_{req.stars}"
    currency = "XTR" # "XTR" est le code pour les Telegram Stars
    prices = [{"label": "Stars", "amount": req.stars}] 

    # Note: Tu dois appeler l'API Telegram 'createInvoiceLink' ici
    # Pour simplifier, assure-toi d'utiliser une librairie comme 'python-telegram-bot' 
    # ou de faire un requests.post vers https://api.telegram.org/bot{token}/createInvoiceLink
    
    # Exemple rapide avec requests :
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink"
    res = requests.post(url, json={
        "title": title,
        "description": description,
        "payload": payload,
        "currency": currency,
        "prices": prices
    })
    
    data = res.json()
    if data.get("ok"):
        return {"invoice_link": data["result"]}
    return {"error": "Failed to create invoice"}
