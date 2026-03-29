from fastapi import APIRouter
from fastapi.responses import JSONResponse
import database, config, missions, time
from datetime import datetime, timedelta
from pydantic import BaseModel

router = APIRouter(prefix="/api/user", tags=["User"])

# --- FONCTION ÉCONOMIQUE ---
def get_wpt_price(total_supply):
    base_price = 0.0001
    # On peut imaginer que plus il y a de WPT en circulation (émis par les Stars), 
    # plus la rareté augmente via un multiplicateur
    growth = (total_supply / 1000000) * 0.00002 # On a doublé le facteur de croissance
    return round(base_price + growth, 6)
# --- 1. MODÈLES DE DONNÉES ---
class WithdrawRequest(BaseModel):
    user_id: int
    address: str
    amount: float

class WalletUpdate(BaseModel):
    user_id: int
    wallet_address: str

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
    # 1. Récupération des données de base
    r = database.get_user_full(uid)
    if not r: 
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    # Extraction des données (Assure-toi que l'ordre correspond à ta BDD)
    p_gen, p_uni, p_veo, name, energy, last_upd, streak, _, last_login_str = r[:9]
    
    # --- INITIALISATION DES VARIABLES ---
    turbo_active = False
    recharge_rate = 1.0
    rank_display = "---"
    now_dt = datetime.now()
    now_ts = int(time.time())

    try:
        conn = database.get_db_conn()
        c = conn.cursor()

        # --- 🚀 LOGIQUE TURBO ---
        c.execute("SELECT turbo_until FROM users WHERE user_id = %s", (uid,))
        t_res = c.fetchone()
        if t_res and t_res[0] and t_res[0] > now_dt:
            turbo_active = True
            recharge_rate = 3.0

        # --- 🚀 LOGIQUE DAILY STREAK ---
        today_str = now_dt.strftime("%Y-%m-%d")
        current_streak = streak or 0
        if last_login_str != today_str:
            if last_login_str:
                last_login_dt = datetime.strptime(last_login_str, "%Y-%m-%d").date()
                yesterday = now_dt.date() - timedelta(days=1)
                if last_login_dt == yesterday:
                    current_streak += 1
                elif last_login_dt < yesterday:
                    current_streak = 1
            else:
                current_streak = 1
            c.execute("UPDATE users SET streak = %s, last_login_date = %s WHERE user_id = %s", 
                      (current_streak, today_str, uid))
            conn.commit()

        # --- 🚀 CALCULS FINANCIERS (PRIX & SUPPLY) ---
        c.execute("SELECT SUM(COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users")
        total_supply = c.fetchone()[0] or 0
        
        c.execute("SELECT total_burned FROM global_stats LIMIT 1")
        b_res = c.fetchone()
        burned = b_res[0] if b_res else 0
        
        # Calcul du prix et score
        score_total = (float(p_gen or 0) + float(p_uni or 0) + float(p_veo or 0))
        current_price = 0.0001 + (float(burned) * 0.00000001) 
        usd_value = score_total * current_price

        # --- 🚀 LE FIX DU RANK ✨ ---
        c.execute("""
            SELECT position FROM (
                SELECT user_id, 
                       RANK() OVER (ORDER BY (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) DESC) as position 
                FROM users
            ) AS ranking 
            WHERE user_id = %s
        """, (uid,))
        res_rank = c.fetchone()
        if res_rank:
            rank_display = res_rank[0]

        c.close(); conn.close()
    except Exception as e:
        print(f"❌ Erreur Data Init: {e}")
        score_total = (float(p_gen or 0) + float(p_uni or 0) + float(p_veo or 0))
        usd_value = score_total * 0.0001
        current_streak = streak or 0

    # --- 🚀 ÉNERGIE DYNAMIQUE ---
    try:
        max_e = 100
        l_upd = int(last_upd) if last_upd else now_ts
        minutes_passed = (now_ts - l_upd) / 60
        current_e = min(max_e, (float(energy or 0)) + (minutes_passed * recharge_rate))
    except:
        current_e = 100

    mining_boost = 1 + (min(current_streak, 10) * 0.05)

    return {
        "uid": uid, 
        "name": name or "Citizen", 
        "g": round(float(p_gen or 0), 2),
        "u": round(float(p_uni or 0), 2),
        "v": round(float(p_veo or 0), 2),
        "score": round(score_total, 2), 
        "usd_value": round(usd_value, 2),
        "energy": int(current_e),
        "max_energy": 100,
        "rank": rank_display,
        "streak": current_streak,
        "turbo_active": turbo_active,
        "mining_boost": round(mining_boost, 2)
    }




# --- 4. RETRAIT & WALLET ---
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
        c.execute("INSERT INTO withdrawals (user_id, address, amount, status, created_at) VALUES (%s, %s, %s, 'pending', %s)", (req.user_id, req.address, req.amount, int(time.time())))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()

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
