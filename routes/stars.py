from fastapi import APIRouter, Request
from telegram import LabeledPrice

# On définit le router ici
router = APIRouter()

@router.get("/api/stars/create-invoice/{uid}")
async def create_invoice(request: Request, uid: int, amount: int = 50):
    try:
        # On récupère le bot depuis l'état de l'application
        bot = request.app.state.bot 
        
        prices = [LabeledPrice(label="Stars", amount=amount)]
        
        invoice_link = await bot.create_invoice_link(
            title=f"Pack {amount} Stars",
            description="Purchase WPT Credits",
            payload=f"buy_stars_{amount}_{uid}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
        return {"invoice_link": invoice_link}
    except Exception as e:
        print(f"Erreur Invoice: {e}")
        return {"error": str(e)}
