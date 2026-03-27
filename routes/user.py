from fastapi import APIRouter
from fastapi.responses import JSONResponse
import database, config, missions, time
from pydantic import BaseModel

router = APIRouter(prefix="/api/user", tags=["User"])

# --- 1. MODÈLES DE DONNÉES (Pydantic) ---
# Toujours définir les classes au début, en dehors des fonctions !
class WithdrawRequest(BaseModel):
    user_id: int
    address: str
    amount: float

# --- 2. LEADERBOARD ---
@router.get("/leaderboard")
async def get_leaderboard():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT name, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) as total_score 
            FROM users 
            WHERE name IS NOT NULL AND (p_genesis > 0 OR p_unity > 0 OR p_veo > 0)
            ORDER BY total_score DESC 
            LIMIT 10
        """)
        leaders = []
        for i, r in enumerate(c.fetchall()):
            leaders.append({
                "rank": i + 1,
                "name": r[0] or "Unknown",
                "score": round(r[1], 2)
            })
        return leaders
    finally:
        c.close(); conn.close()

# --- FONCTION ÉCONOMIQUE ---
def get_wpt_price(total_supply):
    """Calcule le prix du WPT basé sur la masse monétaire totale."""
    base_price = 0.0001  # Prix de départ
    # On augmente le prix de 0.00001$ par million de tokens
    growth = (total_supply / 1000000) * 0.00001
    return round(base_price + growth, 6)

# --- 3. DONNÉES UTILISATEUR MODIFIÉES ---
@router.get("/{uid}")
async def get_user_data(uid: int):
    r = database.get_user_full(uid)
    if not r: 
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    p_gen, p_uni, p_veo, name, energy, last_upd, streak, _, _ = r
    score_total = (p_gen or 0) + (p_uni or 0) + (p_veo or 0)
    
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Calcul de la Supply Totale pour le prix
        c.execute("SELECT SUM(COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users")
        total_supply = c.fetchone()[0] or 0
        current_price = get_wpt_price(total_supply)
        usd_value = score_total * current_price

        # 2. Reste des requêtes (Rang, Assets, Referrals)
        c.execute("SELECT pos FROM (SELECT user_id, RANK() OVER (ORDER BY (p_genesis+p_unity+p_veo) DESC) as pos FROM users) r WHERE user_id = %s", (uid,))
        res_rank = c.fetchone()
        
        c.execute("SELECT t.name, t.symbol, a.amount FROM user_community_assets a JOIN community_tokens t ON a.token_id = t.id WHERE a.user_id = %s", (uid,))
        assets = [{"n": x[0], "s": x[1], "a": float(x[2])} for x in c.fetchall()]

        c.execute("SELECT COUNT(*) FROM users WHERE referrer_id = %s", (uid,))
        ref_count = c.fetchone()[0] or 0

        # On calcule l'énergie régénérée
        now = int(time.time())
        current_e = min(getattr(config, 'MAX_ENERGY', 100), (energy or 0) + ((now - (last_upd or now))/60 * getattr(config, 'REGEN_RATE', 1.0)))

        return {
            "uid": uid, "name": name or "Citizen", 
            "score": round(score_total, 2), 
            "usd_value": round(usd_value, 2), # <-- Valeur en $
            "wpt_price": current_price,       # <-- Prix actuel
            "energy": int(current_e), 
            "rank": res_rank[0] if res_rank else "---",
            "assets": assets, 
            "ref_count": ref_count
        }
    finally:
        c.close(); conn.close()


# --- 4. RETRAIT (Withdraw) ---
@router.post("/withdraw")
async def request_withdraw(req: WithdrawRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérifier le solde
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        res = c.fetchone()
        if not res or res[0] < req.amount:
            return {"ok": False, "error": "Insufficient balance"}

        # 2. Déduire le solde
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount, req.user_id))
        
        # 3. Enregistrer la demande (assure-toi que la table 'withdrawals' existe)
        c.execute("""
            INSERT INTO withdrawals (user_id, address, amount, status, created_at) 
            VALUES (%s, %s, %s, 'pending', %s)
        """, (req.user_id, req.address, req.amount, int(time.time())))
        
        conn.commit()
        print(f"💰 Withdrawal request: {req.amount} WPT to {req.address}")
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()




# Assure-toi que cette classe est définie en haut ou juste avant la route
class WalletUpdate(BaseModel):
    user_id: int
    wallet_address: str

# Utilise @router.post et non @app.post
@router.post("/update-wallet")
async def update_wallet(req: WalletUpdate):
    print(f"🔐 Linking Wallet: {req.wallet_address} to UID {req.user_id}")
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # On met à jour la colonne wallet pour l'utilisateur
        c.execute("UPDATE users SET wallet = %s WHERE user_id = %s", (req.wallet_address, req.user_id))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        print(f"❌ Wallet Update Error: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()

