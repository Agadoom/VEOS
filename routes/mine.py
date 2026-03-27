from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import database, config, time

router = APIRouter(prefix="/api/mine", tags=["Mining"])

@router.post("")
async def mine_action(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    token_type = data.get("token")
    
    if not uid or not token_type:
        return JSONResponse(status_code=400, content={"error": "Missing data"})

    conn = database.get_db_conn()
    c = conn.cursor()
    
    try:
        # 1. On récupère les infos
        c.execute("SELECT energy, last_energy_update, last_click_time FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        
        if not res:
            return JSONResponse(status_code=400, content={"error": "User not found"})

        energy, last_upd, last_click = res
        now_ms = int(time.time() * 1000)
        now_s = now_ms // 1000
        
        # 2. Calcul de la régénération d'énergie forcée
        # Si last_upd est vide, on prend maintenant
        last_upd = last_upd if last_upd else now_s
        diff_minutes = (now_s - last_upd) / 60
        regen = diff_minutes * getattr(config, 'REGEN_RATE', 1.0)
        cur_e = min(getattr(config, 'MAX_ENERGY', 100), (energy or 0) + regen)

        # 3. Vérification Anti-Spam (80ms)
        if (now_ms - (last_click or 0)) < 80:
            return JSONResponse(status_code=400, content={"error": "Too fast"})

        # 4. Vérification Énergie
        if cur_e < 1:
            return JSONResponse(status_code=400, content={"error": "No energy"})

        # --- CALCUL RÉCOMPENSE ---
        c.execute("SELECT SUM(COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users")
        total_supply = c.fetchone()[0] or 0
        reward = 0.05 if total_supply < 10000000 else 0.025

        # 5. MISE À JOUR
        field = f"p_{token_type}"
        # On s'assure que le field est valide pour éviter l'injection SQL
        if field not in ["p_genesis", "p_unity", "p_veo"]:
            return JSONResponse(status_code=400, content={"error": "Invalid token"})

        c.execute(f"""
            UPDATE users 
            SET {field} = COALESCE({field}, 0) + %s, 
                energy = %s, 
                last_energy_update = %s, 
                last_click_time = %s 
            WHERE user_id = %s
        """, (reward, cur_e - 1, now_s, now_ms, uid))
        
        conn.commit()
        return {"ok": True, "reward": reward, "new_energy": cur_e - 1}

    except Exception as e:
        print(f"❌ Erreur Mining: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        c.close()
        conn.close()
