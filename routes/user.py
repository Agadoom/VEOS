# 1. CETTE ROUTE DOIT ÊTRE EN PREMIER
@router.get("/leaderboard")
async def get_leaderboard():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # On additionne les 3 colonnes de ta table users
        c.execute("""
            SELECT name, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) as total_score 
            FROM users 
            WHERE name IS NOT NULL AND (p_genesis > 0 OR p_unity > 0 OR p_veo > 0)
            ORDER BY total_score DESC 
            LIMIT 10
        """)
        res = c.fetchall()
        leaders = []
        for i, r in enumerate(res):
            leaders.append({
                "rank": i + 1,
                "name": r[0] if r[0] else "Unknown",
                "score": round(r[1], 2)
            })
        return leaders
    except Exception as e:
        print(f"Leaderboard DB Error: {e}")
        return []
    finally:
        c.close(); conn.close()

# 2. CETTE ROUTE EN DEUXIÈME
@router.get("/{uid}")
async def get_user_data(uid: int):
    r = database.get_user_full(uid)
    if not r: return JSONResponse(status_code=404, content={"error": "User not found"})
    
    # ... (ton code de calcul d'énergie et score ici) ...
    score = (r[0] or 0) + (r[1] or 0) + (r[2] or 0)
    
    conn = database.get_db_conn(); c = conn.cursor()
    try:
        # Calcul du RANG en pointant sur la table users
        c.execute("""
            SELECT pos FROM (
                SELECT user_id, RANK() OVER (ORDER BY (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) DESC) as pos 
                FROM users
            ) as sub WHERE user_id = %s
        """, (uid,))
        rank_res = c.fetchone()
        user_rank = rank_res[0] if rank_res else "---"
        
        # ... (le reste de tes fetchs: assets, referrals) ...
        
        return {
            "uid": uid, "name": r[4], "g": r[0], "u": r[1], "v": r[2],
            "score": round(score, 2), "rank": user_rank, "energy": int(current_e),
            "max_energy": config.MAX_ENERGY, "badge": badge, "streak": r[7] or 0
        }
    finally:
        c.close(); conn.close()
