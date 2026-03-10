import os
from web3 import Web3
import requests

# 🔹 Variables d'environnement
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RPC_URL = os.getenv("RPC_URL")
TOKEN_CONTRACT = os.getenv("TOKEN_CONTRACT")  # contrat BLUM
PUBLIC_ADDRESS = os.getenv("PUBLIC_ADDRESS")  # adresse à checker

# 🔹 Vérification des variables
if not all([BOT_TOKEN, CHAT_ID, RPC_URL, TOKEN_CONTRACT, PUBLIC_ADDRESS]):
    raise Exception("Une ou plusieurs variables d'environnement manquantes !")

# 🔹 Connexion Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise Exception(f"Impossible de se connecter au RPC : {RPC_URL}")

print(f"Connecté à Web3 : {w3.clientVersion}")

# 🔹 ABI minimal pour ERC20 (balanceOf et decimals)
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
    },
]

token = w3.eth.contract(address=TOKEN_CONTRACT, abi=ERC20_ABI)

# 🔹 Récupérer balance
balance_raw = token.functions.balanceOf(PUBLIC_ADDRESS).call()
decimals = token.functions.decimals().call()
balance = balance_raw / (10 ** decimals)

# 🔹 Envoyer message Telegram
msg = f"Balance de {PUBLIC_ADDRESS} : {balance} BLUM"

requests.get(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    params={"chat_id": CHAT_ID, "text": msg}
)

print("Message envoyé :", msg)