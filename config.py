import os

TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8080))
RAW_URL = os.getenv("WEBAPP_URL", "")
WEBAPP_URL = RAW_URL if RAW_URL.startswith("http") else f"https://{RAW_URL}"

MAX_ENERGY = 100
REGEN_RATE = 1
LOCK_TIME_DAILY = 12 * 3600 # 12 heures en secondes
