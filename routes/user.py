from fastapi import APIRouter
from fastapi.responses import JSONResponse
import database, config, missions, time
from pydantic import BaseModel

router = APIRouter(prefix="/api/user", tags=["User"])

# --- 1. LEADERBOARD (Toujours en premier) ---
@router.get("/leaderboard")
async def get_leaderboard():
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # On additionne les 3 colonnes pour le score réel
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
    except Exception as e:
        print(f"Leaderboard Error: {e}")
        return []
    finally:
        c.close()
        conn.close()

# --- 2. DONNÉES UTILISATEUR ---
@router.get("/{uid}")
async def get_user_data(uid: int):
    # 1. Récupération via database.py
    # On s'attend à recevoir : (p_gen, p_uni, p_veo, name, energy, last_upd, streak, ref_id, last_login)
    r = database.get_user_full(uid)
    
    if not r or len(r) < 6: 
        return JSONResponse(status_code=404, content={"error": "User data incomplete"})
    
    # Extraction propre des données du tuple
    p_gen, p_uni, p_veo, name, energy, last_upd, streak, _, _ = r
    
    # 2. Calcul Énergie
    now = int(time.time())
    # Sécurité : si last_upd est None ou 0, on initialise à 'now'
    last_update_ts = last_upd if (last_upd and last_upd > 0) else now
    
    # Formule : Énergie actuelle + (temps écoulé en min * taux de regen)
    diff_minutes = (now - last_update_ts) / 60
    regen = diff_minutes * getattr(config, 'REGEN_RATE', 1.0)
    current_e = min(getattr(config, 'MAX_ENERGY', 100), (energy or 0) + regen)
    
    # 3. Score Global
    score_total = (p_gen or 0) + (p_uni or 0) + (p_veo or 0)
    
    # Gestion du badge (evite le crash si missions.py bug)
    try:
        badge, _, _ = missions.get_badge_info(score_total)
    except:
        badge = "Citizen"

    conn = database.get_db_conn()
    c = conn.cursor()

    try:
        # 4. Calcul du rang (Ranking)
        c.execute("""
            SELECT pos FROM (
                SELECT user_id, RANK() OVER (ORDER BY (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) DESC) as pos 
                FROM users
            ) as ranking WHERE user_id = %s
        """, (uid,))
        res_rank = c.fetchone()
        user_rank = res_rank[0] if res_rank else "---"

        # 5. Fetch Assets (Tokens communautaires) - Correction JOIN
        c.execute("""
            SELECT t.name, t.symbol, a.amount 
            FROM user_community_assets a 
            INNER JOIN community_tokens t ON a.token_id = t.id 
            WHERE a.user_id = %s AND a.amount > 0
        """, (uid,))
        assets = [{"n": x[0], "s": x[1], "a": float(x[2])} for x in c.fetchall()]

        # 6. Compteur Referrals
        c.execute("SELECT COUNT(*) FROM users WHERE referrer_id = %s", (uid,))
        ref_count = c.fetchone()[0] or 0

        return {
            "uid": uid, 
            "name": name or "Citizen", 
            "g": round(p_gen or 0, 2), 
            "u": round(p_uni or 0, 2), 
            "v": round(p_veo or 0, 2), 
            "energy": int(current_e), 
            "max_energy": getattr(config, 'MAX_ENERGY', 100), 
            "score": round(score_total, 2), 
            "badge": badge, 
            "rank": user_rank,
            "streak": streak or 0,
            "assets": assets,
            "ref_count": ref_count,
             user_id: int,
             address: str,
             amount: float
        }
    except Exception as e:
        print(f"❌ Error in user route for UID {uid}: {e}")
        return JSONResponse(status_code=500, content={"error": f"Database detail error: {str(e)}"})
    finally:
        c.close()
        conn.close()



# Dans ton fichier routes/user.py ou launcher.py
@router.post("/api/user/withdraw")
async def request_withdraw(req: WithdrawRequest):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # Vérifier si l'utilisateur a assez de solde
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (req.user_id,))
        balance = c.fetchone()[0]
        
        if balance < req.amount:
            return {"ok": False, "error": "Insufficient balance"}

        # Déduire le solde et enregistrer la demande
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (req.amount, req.user_id))
        c.execute("INSERT INTO withdrawals (user_id, address, amount, status) VALUES (%s, %s, %s, 'pending')", 
                  (req.user_id, req.address, req.amount))
        
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}



@router.post("/withdraw") # ou /api/user/withdraw selon ton prefixe
async def request_withdraw(req: WithdrawRequest):
    # Ton code actuel de retrait...
    # Tu accèdes aux données avec req.user_id, req.address, etc.
    print(f"Demande de retrait de {req.amount} pour {req.address}")
    return {"ok": True}


