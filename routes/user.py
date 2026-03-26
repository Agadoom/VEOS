from fastapi import APIRouter
from fastapi.responses import JSONResponse
import database, config, missions, time

router = APIRouter(prefix="/api/user", tags=["User"])

@router.get("/{uid}")
async def get_user_data(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={"error": "User not found"})
    
    # Energy & Score Calculation
    now = int(time.time())
    last_update = r[6] if r[6] is not None else now
    current_e = min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_update) / 60) * config.REGEN_RATE)
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    badge, _, _ = missions.get_badge_info(score)
    
    conn = database.get_db_conn()
    c = conn.cursor()

    try:
        # 1. Calcul du RANG
         # Calcul du rang basé sur le score total
        c.execute("""
            SELECT rank FROM (
                SELECT user_id, RANK() OVER (ORDER BY (p_genesis + p_unity + p_veo) DESC) as rank 
                FROM users
            ) as ranking WHERE user_id = %s
        """, (uid,))
        res_rank = c.fetchone()
        rank = res_rank[0] if res_rank else "---"

        # 2. FETCH ALL ASSETS
        c.execute("""
            SELECT t.name, t.symbol, a.amount 
            FROM user_community_assets a 
            JOIN community_tokens t ON a.token_id = t.id 
            WHERE a.user_id = %s AND a.amount > 0
        """, (uid,))
        assets = [{"n": x[0], "s": x[1], "a": float(x[2])} for x in c.fetchall()]

        # 3. COUNT REFERRALS
        c.execute("SELECT COUNT(*) FROM users WHERE referrer_id = %s", (uid,))
        ref_count = c.fetchone()[0] or 0

        return {
            "uid": uid, 
            "name": r[4], 
            "g": round(r[0] or 0, 2), 
            "u": round(r[1] or 0, 2), 
            "v": round(r[2] or 0, 2), 
            "energy": int(current_e), 
            "max_energy": config.MAX_ENERGY, 
            "score": round(score, 2), 
            "badge": badge, 
            "rank": rank, # <-- AJOUTÉ
            "streak": r[7] or 0, # <-- AJOUTÉ
            "assets": assets,
            "ref_count": ref_count
        }
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
    finally:
        c.close()
        conn.close()

@router.get("/leaderboard")
async def get_leaderboard():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT name, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) as total_score 
            FROM users 
            WHERE name IS NOT NULL 
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
        c.close()
        conn.close()

@router.post("/claim-daily")
async def claim_daily(data: dict):
    uid = data.get("user_id")
    if not uid: return JSONResponse(status_code=400, content={"error": "Missing user_id"})
    reward, new_streak = missions.process_daily_login(uid)
    return {
        "ok": reward > 0,
        "reward": reward,
        "streak": new_streak
    }