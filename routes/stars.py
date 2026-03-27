from fastapi import APIRouter
from telegram import LabeledPrice

router = APIRouter() # <--- Cette ligne est obligatoire

# À placer là où sont tes autres routes API
@app.get("/api/stars/create-invoice/{uid}")
async def create_invoice(uid: int, amount: int = 50): # <--- BIEN VÉRIFIER LE 'amount' ICI
    try:
        # On définit le prix dynamiquement selon ce que l'App envoie
        prices = [LabeledPrice(label="Stars", amount=amount)] 
        
        # On génère le lien avec le montant correct
        invoice_link = await app.state.bot.create_invoice_link(
            title=f"Pack {amount} Stars",
            description="Recharge de crédits WPT",
            payload=f"buy_stars_{amount}_{uid}", # On passe l'amount dans le payload
            provider_token="", 
            currency="XTR",
            prices=prices
        )
        return {"invoice_link": invoice_link}
    except Exception as e:
        print(f"Erreur: {e}")
        return {"error": str(e)}
