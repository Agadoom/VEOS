from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import database, config, time

router = APIRouter(prefix="/api/mine", tags=["Mining"])

@router.post("")
async def mine_action(request: Request):
    data = await request.json()
    uid, token_type = data.get("user_id"), data.get("token")
    
    conn = database.get_db_conn()
    c = conn.cursor()
    
    # 1. On récupère les infos de l'utilisateur
    c.execute("SELECT energy, last_energy_update, last_click_time FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    
    now_ms = int(time.time() * 1000)
    now_s = now_ms // 1000
    
    # Anti-spam : 80ms entre deux clics
    if res and (now_ms - (res[2] or 0)) >= 80:
        cur_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now_s - (res[1] or now_s))/60) * config.REGEN_RATE)
        
        if cur_e >= 1:
            # --- NOUVEAU : CALCUL DE LA RÉCOMPENSE (HALVING) ---
            # On calcule le total miné pour savoir si on réduit la récompense
            c.execute("SELECT SUM(COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users")
            total_supply = c.fetchone()[0] or 0
            
            # Si le total dépasse 10 millions, on divise la récompense par 2 (0.025 au lieu de 0.05)
            reward = 0.05 if total_supply < 10000000 else 0.025
            # --------------------------------------------------

            # Mise à jour du token spécifique (genesis, unity, ou veo)
            field = f"p_{token_type}"
            c.execute(f"""
                UPDATE users 
                SET {field} = COALESCE({field}, 0) + %s, 
                    energy = %s, 
                    last_energy_update = %s, 
                    last_click_time = %s 
                WHERE user_id = %s
            """, (reward, cur_e - 1, now_s, now_ms, uid))
            
            conn.commit()
            c.close()
            conn.close()
            return {"ok": True, "reward": reward} # On renvoie la récompense pour le front
            
    c.close()
    conn.close()
    return JSONResponse(status_code=400, content={"error": "Not enough energy or too fast"})
