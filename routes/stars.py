from fastapi import APIRouter, Request
from telegram import LabeledPrice

# On définit le router ici
router = APIRouter()

@router.get("/create-invoice/{uid}")
async def create_stars_invoice(uid: int, amount: int):
    # On définit le titre selon le prix
    title = f"{amount} Stars Pack"
    description = f"Purchase {amount} Stars for WPT Hub"
    payload = f"stars_{amount}_{uid}" # On met le montant dans le payload
    
    if amount == 1000:
        title = "💎 LEGEND PACK"
        description = "300,000 WPT + Exclusive Badge"
        payload = f"pack_legend_{uid}"
    elif amount == 99:
        title = "⚡ TURBO BOOST"
        description = "3x Energy Speed for 24h"
        payload = f"turbo_boost_{uid}"

    # Appel à BotFather/Telegram pour créer le lien
    invoice_link = await bot.create_invoice_link(
        title=title,
        description=description,
        payload=payload,
        provider_token="", # Vide pour les Stars
        currency="XTR",
        prices=[{"label": "Stars", "amount": amount}]
    )
    return {"invoice_url": invoice_link}
