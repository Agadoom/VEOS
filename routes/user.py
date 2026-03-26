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

# --- 3. DONNÉES UTILISATEUR ---
@router.get("/{uid}")
async def get_user_data(uid: int):
    r = database.get_user_full(uid)
    if not r: 
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    p_gen, p_uni, p_veo, name, energy, last_upd, streak, _, _ = r
    
    now = int(time.time())
    current_e = min(getattr(config, 'MAX_ENERGY', 100), (energy or 0) + ((now - (last_upd or now))/60 * getattr(config, 'REGEN_RATE', 1.0)))
    score_total = (p_gen or 0) + (p_uni or 0) + (p_veo or 0)
    
    try:
        badge, _, _ = missions.get_badge_info(score_total)
    except:
        badge = "Citizen"

    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Rang
        c.execute("SELECT pos FROM (SELECT user_id, RANK() OVER (ORDER BY (p_genesis+p_unity+p_veo) DESC) as pos FROM users) r WHERE user_id = %s", (uid,))
        res_rank = c.fetchone()
        
        # Assets
        c.execute("SELECT t.name, t.symbol, a.amount FROM user_community_assets a JOIN community_tokens t ON a.token_id = t.id WHERE a.user_id = %s", (uid,))
        assets = [{"n": x[0], "s": x[1], "a": float(x[2])} for x in c.fetchall()]

        # Referrals
        c.execute("SELECT COUNT(*) FROM users WHERE referrer_id = %s", (uid,))
        ref_count = c.fetchone()[0] or 0

        return {
            "uid": uid, "name": name or "Citizen", 
            "g": round(p_gen or 0, 2), "u": round(p_uni or 0, 2), "v": round(p_veo or 0, 2), 
            "energy": int(current_e), "score": round(score_total, 2), 
            "badge": badge, "rank": res_rank[0] if res_rank else "---",
            "streak": streak or 0, "assets": assets, "ref_count": ref_count
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

