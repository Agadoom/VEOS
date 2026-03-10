import os
from web3 import Web3
import requests

# Variables d'environnement
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
RPC_URL = os.environ.get("RPC_URL")
TOKEN_CONTRACT = os.environ.get("TOKEN_CONTRACT")

# Vérification des variables
if not all([BOT_TOKEN, CHAT_ID, RPC_URL, TOKEN_CONTRACT]):
    raise Exception("Une ou plusieurs variables d'environnement manquantes !")

# Connexion Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise Exception("Web3 connection failed")

# ABI minimal pour lire la balance
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    }
]

# Création du contrat
token_contract = w3.eth.contract(address=TOKEN_CONTRACT, abi=ERC20_ABI)

# Ici on définit l'adresse à surveiller automatiquement
# => Pour un bot lecture seule, on peut utiliser une adresse publique "monitor"
# Exemple générique (peut être remplacée par ton adresse publique)
PUBLIC_ADDRESS = TOKEN_CONTRACT  

# Récupération balance
decimals = token_contract.functions.decimals().call()
balance_raw = token_contract.functions.balanceOf(PUBLIC_ADDRESS).call()
balance = balance_raw / (10 ** decimals)

# Envoi sur Telegram
message = f"Balance actuelle du token : {balance} BLUM"
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
requests.post(url, data={"chat_id": CHAT_ID, "text": message})

print(message)