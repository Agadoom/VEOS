from fastapi import APIRouter, Request, HTTPException
from telegram import LabeledPrice
import config

router = APIRouter(prefix="/api/stars", tags=["Stars"])

@router.get("/create-invoice/{uid}")
async def create_stars_invoice(uid: int, amount: int, request: Request):
    # 1. On récupère l'instance du bot stockée dans FastAPI (main.py)
    bot = request.app.state.bot
    
    # 2. Configuration dynamique selon le montant
    title = f"{amount} Stars Pack"
    description = f"Purchase {amount} Stars for WPT Hub"
    # IMPORTANT : Le payload doit correspondre à ce que ton successful_payment_callback attend !
    payload = f"stars_pack_{amount}_{uid}" 
    
    if amount == 1000:
        title = "💎 LEGEND PACK"
        description = "300,000 WPT + Exclusive Badge"
        payload = f"stars_pack_1000_{uid}"
    elif amount == 250:
        title = "🌟 MEDIUM PACK"
        description = "60,000 WPT + Bonus"
        payload = f"stars_pack_250_{uid}"
    elif amount == 99:
        title = "⚡ TURBO BOOST"
        description = "3x Energy Speed for 24h"
        payload = f"turbo_boost_99_{uid}"

    try:
        # 3. Création du lien avec LabeledPrice
        invoice_link = await bot.create_invoice_link(
            title=title,
            description=description,
            payload=payload,
            provider_token="", # Vide pour Telegram Stars (XTR)
            currency="XTR",
            prices=[LabeledPrice(label=title, amount=amount)]
        )
        
        # On retourne "invoice_link" pour que ton JS puisse faire window.Telegram.WebApp.openInvoice
        return {"invoice_link": invoice_link}
        
    except Exception as e:
        print(f"❌ Stars Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
