from fastapi import APIRouter
from fastapi.responses import JSONResponse
import database, config, missions, time
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
    # 1. Récupération des données (inclut streak et last_login_date)
    r = database.get_user_full(uid)
    if not r: 
        return JSONResponse(status_code=404, content={"error": "User not found"})
    
    # Ordre: genesis(0), unity(1), veo(2), name(3), energy(4), last_upd(5), streak(6), ref(7), last_login(8)
    p_gen, p_uni, p_veo, name, energy, last_upd, streak, _, last_login_str = r
    
    # --- 🚀 LOGIQUE DU DAILY STREAK ---
    now_dt = datetime.now()
    today_str = now_dt.strftime("%Y-%m-%d")
    current_streak = streak or 0
    
    if last_login_str != today_str:
        conn = database.get_db_conn()
        c = conn.cursor()
        try:
            if last_login_str:
                last_login_dt = datetime.strptime(last_login_str, "%Y-%m-%d").date()
                yesterday = now_dt.date() - timedelta(days=1)
                
                if last_login_dt == yesterday:
                    current_streak += 1 # Continue le streak
                elif last_login_dt < yesterday:
                    current_streak = 1 # A raté un jour, reset à 1
            else:
                current_streak = 1 # Première connexion
            
            # Update BDD
            c.execute("UPDATE users SET streak = %s, last_login_date = %s WHERE user_id = %s", 
                      (current_streak, today_str, uid))
            conn.commit()
        except Exception as e:
            print(f"Streak Update Error: {e}")
        finally:
            c.close(); conn.close()

    # Calcul du boost de minage (ex: +5% par jour de streak, max +50%)
    mining_boost = 1 + (min(current_streak, 10) * 0.05)

    # --- RESTE DES CALCULS (Score, Prix, Rang) ---
    score_total = (p_gen or 0) + (p_uni or 0) + (p_veo or 0)
    
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT SUM(COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users")
        total_supply = c.fetchone()[0] or 0
        current_price = get_wpt_price(total_supply)
        usd_value = score_total * current_price

        c.execute("""
            SELECT pos FROM (
                SELECT user_id, RANK() OVER (ORDER BY (p_genesis + p_unity + p_veo) DESC) as pos 
                FROM users
            ) r WHERE user_id = %s
        """, (uid,))
        res_rank = c.fetchone()
        rank_display = res_rank[0] if res_rank else "---"

        # Énergie régénérée
        now_ts = int(time.time())
        max_e = getattr(config, 'MAX_ENERGY', 100)
        regen_rate = getattr(config, 'REGEN_RATE', 1.0)
        minutes_passed = (now_ts - (last_upd or now_ts)) / 60
        current_e = min(max_e, (energy or 0) + (minutes_passed * regen_rate))

        return {
            "uid": uid, 
            "name": name or "Citizen", 
            "g": round(p_gen or 0, 2),
            "u": round(p_uni or 0, 2),
            "v": round(p_veo or 0, 2),
            "score": round(score_total, 2), 
            "usd_value": round(usd_value, 2),
            "energy": int(current_e),
            "max_energy": max_e,
            "rank": rank_display,
            "streak": current_streak,
            "mining_boost": round(mining_boost, 2) # On envoie le boost au JS
        }
    except Exception as e:
        print(f"Erreur API User: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
    finally:
        c.close(); conn.close()


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
