import os
import time
import requests
from web3 import Web3

# ==============================
# CONFIGURATION
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

RPC_URL = os.getenv("RPC_URL")
TOKEN_CONTRACT = os.getenv("TOKEN_CONTRACT")

SLEEP_TIME = 5  # secondes entre vérifications

# ==============================
# CONNECT TO BLUM RPC
# ==============================
w3 = Web3(Web3.HTTPProvider(RPC_URL))

if not w3.is_connected():
    raise Exception("Web3 connection failed")
print("Connected to Blum blockchain RPC")

# ==============================
# TELEGRAM FUNCTION
# ==============================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram error:", e)

# ==============================
# FORMAT WALLET
# ==============================
def short_wallet(addr):
    return addr[:6] + "..." + addr[-4:]

# ==============================
# FORMAT BUY MESSAGE
# ==============================
def format_buy(tx_hash, buyer, value):
    message = f"""
🟢 <b>UNITY BUY</b>

👤 Wallet: {short_wallet(buyer)}

💰 Value: {value} BLM

🔗 Tx: https://blumscan.io/tx/{tx_hash}

🚀 <b>Powering the OWPC ecosystem</b>
"""
    return message

# ==============================
# MONITOR TRANSACTIONS
# ==============================
def monitor_buys():
    last_block = w3.eth.block_number
    print("Starting at block:", last_block)

    while True:
        try:
            current_block = w3.eth.block_number
            if current_block > last_block:
                for block_num in range(last_block + 1, current_block + 1):
                    block = w3.eth.get_block(block_num, full_transactions=True)
                    for tx in block.transactions:
                        if tx.to is None:
                            continue
                        if tx.to.lower() == TOKEN_CONTRACT.lower():
                            buyer = tx['from']
                            value = w3.from_wei(tx['value'], 'ether')
                            message = format_buy(tx.hash.hex(), buyer, value)
                            send_telegram(message)
                            print("BUY detected:", tx.hash.hex())
                last_block = current_block
        except Exception as e:
            print("Error:", e)
        time.sleep(SLEEP_TIME)

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    print("OWPC UNITY Buy Bot for Blum STARTED")
    monitor_buys()
if __name__ == "__main__":
    test_message = format_buy("0xTEST123", "0xYourWallet", 0.01)
    send_telegram(test_message)
    monitor_buys()