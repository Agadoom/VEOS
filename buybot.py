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

TOKEN_CONTRACT = Web3.to_checksum_address(os.getenv("TOKEN_CONTRACT"))

DEX_ROUTER = Web3.to_checksum_address(os.getenv("DEX_ROUTER"))

SLEEP_TIME = 5

# ==============================
# CONNECT WEB3
# ==============================

w3 = Web3(Web3.HTTPProvider(RPC_URL))

if not w3.is_connected():
    raise Exception("Web3 connection failed")

print("Connected to blockchain")

# ==============================
# TELEGRAM MESSAGE
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
# BUY MESSAGE
# ==============================

def format_buy(tx_hash, buyer, value_eth):

    message = f"""
🟢 <b>UNITY BUY</b>

👤 Wallet: {short_wallet(buyer)}

💰 Value: {value_eth:.4f} ETH

🔗 Tx:
https://etherscan.io/tx/{tx_hash}

🚀 <b>Powering the OWPC ecosystem</b>
"""

    return message


# ==============================
# CHECK TRANSACTIONS
# ==============================

def monitor_buys():

    last_block = w3.eth.block_number

    print("Starting block:", last_block)

    while True:

        try:

            current_block = w3.eth.block_number

            if current_block > last_block:

                for block_num in range(last_block + 1, current_block + 1):

                    block = w3.eth.get_block(block_num, full_transactions=True)

                    for tx in block.transactions:

                        if tx.to is None:
                            continue

                        to_address = tx.to.lower()

                        if to_address == TOKEN_CONTRACT.lower():

                            buyer = tx["from"]

                            value = w3.from_wei(tx["value"], "ether")

                            message = format_buy(tx.hash.hex(), buyer, value)

                            send_telegram(message)

                            print("BUY detected")

                last_block = current_block

        except Exception as e:

            print("Error:", e)

        time.sleep(SLEEP_TIME)


# ==============================
# MAIN
# ==============================

if __name__ == "__main__":

    print("OWPC UNITY BUY BOT STARTED")

    monitor_buys()