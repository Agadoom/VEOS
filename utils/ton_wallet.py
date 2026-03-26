from tonsdk.contract.wallet import Wallets, WalletVersionEnum
from tonsdk.utils import bytes_to_b64str
import requests

# Configuration du Wallet du Bot
MNEMONIC = ["pink", "lounge", "forget", "tunnel", "upon", "suggest", "pull", "honey", "super", "review", "cargo", "oblige"] # TES 24 MOTS ICI
API_KEY = "3f1ff1ba6288e32f70660b1e8ccb3c948cf59d4d1d1949a58a421e9c598a9ecb" # À obtenir sur toncenter.com

def send_ton_to_user(recipient_address, amount_in_ton):
    # 1. Initialisation du wallet bot
    _mnemonics, _pub_k, _priv_k, wallet = Wallets.from_mnemonic(
        MNEMONIC, version=WalletVersionEnum.v4r2, workchain=0
    )

    # 2. Création du transfert
    query = wallet.create_transfer_message(
        to_addr=recipient_address,
        amount=int(amount_in_ton * 10**9), # Convertir en Nanotons
        seqno=get_current_seqno(wallet.address.to_string()) # Numéro de transaction actuel
    )
    
    # 3. Envoi à la blockchain via API
    b64_msg = bytes_to_b64str(query["message"].to_boc(False))
    r = requests.post(f"https://toncenter.com/api/v2/sendBoc", 
                      json={"boc": b64_msg}, 
                      headers={"X-API-Key": API_KEY})
    return r.json()

