from fastapi import APIRouter
from fastapi.responses import JSONResponse
import database, config, time
from datetime import datetime, timedelta
from pydantic import BaseModel

router = APIRouter(prefix="/api/user", tags=["User"])

# --- MODÈLES DE DONNÉES ---
class WithdrawRequest(BaseModel):
    user_id: int
    address: str
    amount: float

class WalletUpdate(BaseModel):
    user_id: int
    wallet_address: str

# --- 1. LEADERBOARD ---
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

# --- 2. DONNÉES UTILISATEUR (GET PROFILE & ASSETS) ---
@router.get("/{uid}")
async def get_user_data(uid: int):
    r = database.get_user_full(uid)
    if not r: 
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    # Mapping des données BDD
    p_gen, p_uni, p_veo, name, energy, last_upd, streak, _, last_login_str = r[:9]
    
    turbo_active = False
    recharge_rate = 1.0
    rank_display = "---"
    now_dt = datetime.now()
    now_ts = int(time.time())

    try:
        conn = database.get_db_conn()
        c = conn.cursor()

        # Turbo Logic
        c.execute("SELECT turbo_until FROM users WHERE user_id = %s", (uid,))
        t_res = c.fetchone()
        if t_res and t_res[0] and t_res[0] > now_dt:
            turbo_active = True
            recharge_rate = 3.0

        # Burn & Price Logic
        c.execute("SELECT total_burned FROM global_stats LIMIT 1")
        b_res = c.fetchone()
        burned = b_res[0] if b_res else 0
        
        # Calcul du prix dynamique
        current_price = 0.0001 + (float(burned) * 0.00000001) 
        score_total = (float(p_gen or 0) + float(p_uni or 0) + float(p_veo or 0))
        usd_value = score_total * current_price

        # Rank Logic
        # --- DANS user.py (get_user_data) ---
c.execute("""
    SELECT pos FROM (
        SELECT user_id, 
               RANK() OVER (ORDER BY (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) DESC) as pos
        FROM users
    ) as ranking
    WHERE user_id = %s
""", (uid,))
res_rank = c.fetchone()
rank_display = res_rank[0] if res_rank else "---"

        c.close(); conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")
        current_price = 0.0001
        score_total = (float(p_gen or 0) + float(p_uni or 0) + float(p_veo or 0))
        usd_value = score_total * current_price

    # Énergie Dynamique
    l_upd = int(last_upd) if last_upd else now_ts
    minutes_passed = (now_ts - l_upd) / 60
    current_e = min(100, (float(energy or 0)) + (minutes_passed * recharge_rate))
    
    mining_boost = 1 + (min(streak or 0, 10) * 0.05)

    # --- PRÉPARATION DES ASSETS (Pour le JS updateProfilUI) ---
    user_assets = [
        {
            "name": "Genesis (WPT)",
            "symbol": "WPT",
            "balance": round(float(p_gen or 0), 2),
            "current_price": current_price,
            "change_24h": 2.5,
            "icon": "https://veos-production-a2de.up.railway.app/media/owpc_logo.png"
        },
        {
            "name": "Unity",
            "symbol": "UNT",
            "balance": round(float(p_uni or 0), 2),
            "current_price": 0.000089, 
            "change_24h": -1.2,
            "icon": "https://veos-production-a2de.up.railway.app/media/owpc_logo.png"
        },
        {
            "name": "Veo AI",
            "symbol": "VEO",
            "balance": round(float(p_veo or 0), 2),
            "current_price": 0.000120,
            "change_24h": 5.4,
            "icon": "https://veos-production-a2de.up.railway.app/media/owpc_logo.png"
        }
    ]

    return {
        "uid": uid, 
        "name": name or "Citizen", 
        "g": round(float(p_gen or 0), 2),
        "u": round(float(p_uni or 0), 2),
        "v": round(float(p_veo or 0), 2),
        "score": round(score_total, 2), 
        "usd_value": round(usd_value, 2),
        "energy": int(current_e),
        "rank": rank_display,
        "streak": streak or 0,
        "turbo_active": turbo_active,
        "mining_boost": round(mining_boost, 2),
        "assets": user_assets # <-- Voilà ce qui manquait au JS !
    }

# --- 3. RETRAIT (WITHDRAW) ---
@router.post("/withdraw")
async def request_withdraw(req: WithdrawRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        res = c.fetchone()
        if not res or res[0] < req.amount:
            return {"ok": False, "error": "Insufficient balance"}

        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount, req.user_id))
        c.execute("""
            INSERT INTO withdrawals (user_id, address, amount, status, created_at) 
            VALUES (%s, %s, %s, 'pending', %s)
        """, (req.user_id, req.address, req.amount, int(time.time())))
        
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()

# --- 4. MISE À JOUR DU WALLET ---
@router.post("/update-wallet")
async def update_wallet(req: WalletUpdate):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("UPDATE users SET wallet = %s WHERE user_id = %s", (req.wallet_address, req.user_id))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()




@router.get("/vault-status/{uid}")
async def get_vault_status(uid: int):
    user = database.get_user(uid)
    # 1. On récupère son solde de jetons REEL sur la blockchain
    # (Il faut une petite fonction helper qui interroge l'API TonCenter)
    token_balance = await get_ton_balance(user['wallet_address'], "CONTRACT_GWPC")

    # 2. On définit les paliers du coffre-fort
    status = "Citizen"
    multiplier = 1.0
    
    if token_balance >= 1000000: # 1 Million de GWPC
        status = "LEGENDARY VAULT"
        multiplier = 10.0 # x10 sur le minage !
    elif token_balance >= 100000:
        status = "GOLDEN VAULT"
        multiplier = 3.0

    return {
        "status": status,
        "multiplier": multiplier,
        "balance": token_balance
    }

