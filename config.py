TOKEN = os.getenv("TOKEN")
BOT_TOKEN = TOKEN  # On crée cet alias pour éviter l'AttributeError
PORT = int(os.getenv("PORT", 8080))
RAW_URL = os.getenv("WEBAPP_URL", "")
WEBAPP_URL = RAW_URL if RAW_URL.startswith("http") else f"https://{RAW_URL}"

# Équilibrage du jeu
MAX_ENERGY = 100
REGEN_RATE = 1  # 1% par minute
STAKE_MIN = 100
BOOST_PRICE = 50
GIFT_COOLDOWN = 12 * 3600 # 12 heures en secondes