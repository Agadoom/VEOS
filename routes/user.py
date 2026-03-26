from fastapi import APIRouter
from fastapi.responses import JSONResponse
import database, config, missions, time

router = APIRouter(prefix="/api/user", tags=["User"])

@router.get("/leaderboard")
async def get_leaderboard():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT name, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) as total_score 
            FROM users 
            WHERE name IS NOT NULL AND (p_genesis > 0 OR p_unity > 0 OR p_veo > 0)
            ORDER BY total_score DESC LIMIT 10
        """)
        res = c.fetchall()
        return [{"rank": i+1, "name": r[0] or "Anon", "score": round(r[1], 2)} for i, r in enumerate(res)]
    except Exception as e:
        print(f"L-Board Error: {e}")
        return []
    finally:
        c.close(); conn.close()

@router.get("/{uid}")
async def get_user_data(uid: int):
    try:
        r = database.get_user_full(uid)
        if not r: 
            return JSONResponse(status_code=404, content={"error": "User not found"})
        
        now = int(time.time())
        last_update = r[6] if r[6] is not None else now
        current_e = min(config.MAX_ENERGY, (r[5] or 0) + ((now - last_update) / 60) * config.REGEN_RATE)
        score_total = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
        badge, _, _ = missions.get_badge_info(score_total)
        
        conn = database.get_db_conn(); c = conn.cursor()
        
        # Rang
        c.execute("""SELECT pos FROM (SELECT user_id, RANK() OVER (ORDER BY (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) DESC) as pos FROM users) as r WHERE user_id = %s""", (uid,))
        res_rank = c.fetchone()
        
        # Assets
        c.execute("""SELECT t.name, t.symbol, a.amount FROM user_community_assets a JOIN community_tokens t ON a.token_id = t.id WHERE a.user_id = %s AND a.amount > 0""", (uid,))
        assets = [{"n": x[0], "s": x[1], "a": float(x[2])} for x in c.fetchall()]

        # Referrals
        c.execute("SELECT COUNT(*) FROM users WHERE referrer_id = %s", (uid,))
        ref_count = c.fetchone()[0] or 0
        
        c.close(); conn.close()

        return {
            "uid": uid, "name": r[4] or "User", "g": r[0] or 0, "u": r[1] or 0, "v": r[2] or 0,
            "energy": int(current_e), "max_energy": config.MAX_ENERGY, "score": round(score_total, 2),
            "badge": badge, "rank": res_rank[0] if res_rank else "---", "streak": r[7] or 0,
            "assets": assets, "ref_count": ref_count
        }
    except Exception as e:
        print(f"Crit Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/claim-daily")
async def claim_daily(data: dict):
    uid = data.get("user_id")
    reward, new_streak = missions.process_daily_login(uid)
    return {"ok": reward > 0, "reward": reward, "streak": new_streak}
