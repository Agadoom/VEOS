import os

TOKEN = os.getenv("TOKEN")
BOT_TOKEN = TOKEN  # On crée cet alias pour éviter l'AttributeError
PORT = int(os.getenv("PORT", 8080))
RAW_URL = os.getenv("WEBAPP_URL", "")
WEBAPP_URL = RAW_URL if RAW_URL.startswith("http") else f"https://{RAW_URL}"

# Équilibrage du jeu
MAX_ENERGY = 100
REGEN_RATE = 1  # 1% par minute
STAKE_MIN = 100
BOOST_PRICE = 250
GIFT_COOLDOWN = 12 * 3600 # 12 heures en secondes
# Dans ton fichier config.py
ADMIN_WALLET = "UQAvZ1e88yhxpRcfNtJyUNEHD31cDfvF8q_J-PIAukHsNTYi"
DEPLOY_FEE_TON = 0.5  # Exemple : 0.5 TON pour lancer un token
# config.py
DEPLOY_FEE_STARS = 10  # Environ 5$ (ajuste selon tes besoins)
# Tu peux aussi ajouter des frais pour "Boost" un token
BOOST_FEE_STARS = 100
LOTTERY_CHANNEL_ID = 8657676090

