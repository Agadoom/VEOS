from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import database, config, time

router = APIRouter(prefix="/api/mine", tags=["Mining"])

@router.post("")
async def mine_action(request: Request):
    data = await request.json()
    uid = data.get("user_id")
    # FIX ICI : On utilise 'token_type' car c'est ce que ton JS envoie
    token_type = data.get("token_type") 
    
    if not uid or not token_type:
        return JSONResponse(status_code=400, content={"error": "Missing data (UID or Token)"})

    conn = database.get_db_conn()
    c = conn.cursor()
    
    try:
        # On récupère aussi le streak pour le bonus
        c.execute("SELECT energy, last_energy_update, last_click_time, streak FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        
        if not res:
            return JSONResponse(status_code=400, content={"error": "User not found"})

        energy, last_upd, last_click, streak = res
        now_ms = int(time.time() * 1000)
        now_s = now_ms // 1000
        
        # 1. Régénération d'énergie
        l_upd = last_upd if last_upd else now_s
        diff_minutes = (now_s - l_upd) / 60
        cur_e = min(getattr(config, 'MAX_ENERGY', 100), (energy or 0) + (diff_minutes * getattr(config, 'REGEN_RATE', 1.0)))

        # 2. Anti-Spam (80ms) et Energie
        if (now_ms - (last_click or 0)) < 80:
            return JSONResponse(status_code=400, content={"error": "Too fast"})
        if cur_e < 1:
            return JSONResponse(status_code=400, content={"error": "Insufficient energy"})

        # --- 🚀 CALCUL RÉCOMPENSE AVEC STREAK BOOST ---
        base_reward = 0.05 # Gain de base
        # Bonus de 5% par jour de streak (max +50%)
        boost = 1 + (min(streak or 0, 10) * 0.05)
        final_reward = base_reward * boost

        # 3. Sécurité Injection SQL
        valid_fields = {"genesis": "p_genesis", "unity": "p_unity", "veo": "p_veo"}
        db_field = valid_fields.get(token_type)
        
        if not db_field:
            return JSONResponse(status_code=400, content={"error": "Invalid token type"})

        # 4. Mise à jour finale
        c.execute(f"""
            UPDATE users 
            SET {db_field} = COALESCE({db_field}, 0) + %s, 
                energy = %s, 
                last_energy_update = %s, 
                last_click_time = %s 
            WHERE user_id = %s
        """, (final_reward, cur_e - 1, now_s, now_ms, uid))
        
        conn.commit()
        return {"ok": True, "reward": round(final_reward, 4), "new_energy": int(cur_e - 1)}

    except Exception as e:
        print(f"❌ Erreur Mining: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        c.close(); conn.close()

