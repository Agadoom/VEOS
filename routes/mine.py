from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import database
import config
import time

router = APIRouter(prefix="/api/mine", tags=["Mining"])

# --- 1. SYNCHRONISATION & RECHARGE ---
@router.get("/sync/{uid}")
async def sync_energy(uid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        # On récupère l'énergie et le multiplicateur (Magnet/Trend)
        c.execute("SELECT energy, last_energy_update, multiplier FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res: return {"error": "User not found"}
        
        energy, last_upd, multiplier = res
        now_s = int(time.time())
        
        # Calcul de la recharge (ex: 1% par minute)
        regen_rate = getattr(config, 'REGEN_RATE', 1.0)
        max_energy = getattr(config, 'MAX_ENERGY', 100)
        
        diff_s = now_s - (last_upd or now_s)
        regen = (diff_s / 60) * regen_rate
        
        new_energy = min(max_energy, (energy or 0) + regen)
        
        c.execute("UPDATE users SET energy = %s, last_energy_update = %s WHERE user_id = %s", 
                  (new_energy, now_s, uid))
        conn.commit()
        
        return {
            "ok": True, 
            "energy": round(new_energy, 2), 
            "multiplier": multiplier or 1.0,
            "max_energy": max_energy
        }
    finally:
        c.close(); conn.close()

# --- 2. ACTION DE MINAGE AVEC BOOSTERS ---
@router.post("")
async def mine_action(request: Request):
    try:
        data = await request.json()
        uid = data.get("user_id")
        token_type = data.get("token_type") 
        
        conn = database.get_db_conn()
        c = conn.cursor()
        
        # Récupération complète avec Multiplicateur et Turbo
        c.execute("""
            SELECT energy, last_energy_update, last_click_time, streak, multiplier, turbo_until 
            FROM users WHERE user_id = %s
        """, (uid,))
        res = c.fetchone()
        
        if not res: return JSONResponse(status_code=400, content={"error": "User not found"})

        energy, last_upd, last_click, streak, multiplier, turbo_until = res
        now_ms = int(time.time() * 1000)
        now_s = now_ms // 1000

        # Anti-Spam
        if (now_ms - (last_click or 0)) < 80:
            return JSONResponse(status_code=400, content={"error": "Too fast"})

        # Recharge temps réel
        regen_rate = getattr(config, 'REGEN_RATE', 1.0)
        max_energy = getattr(config, 'MAX_ENERGY', 100)
        current_energy = min(max_energy, (energy or 0) + ((now_s - last_upd) / 60 * regen_rate))

        if current_energy < 1:
            return JSONResponse(status_code=400, content={"error": "Low energy"})

        # --- CALCUL DES BOOSTS (Le "Magnet" et le "Trend") ---
        base_reward = 0.05
        
        # 1. Bonus Streak (Connexion quotidienne)
        streak_boost = 1 + (min(streak or 0, 10) * 0.05)
        
        # 2. Bonus Multiplier (C'est ici que le Liquidity Magnet agit !)
        # Si multiplier = 2.0, l'investisseur gagne 2x plus.
        mag_boost = multiplier or 1.0
        
        # 3. Bonus Turbo (Payé en Stars)
        turbo_boost = 2.0 if turbo_until and turbo_until > datetime.now() else 1.0
        
        final_reward = base_reward * streak_boost * mag_boost * turbo_boost

        # Mise à jour des balances
        valid_fields = {"genesis": "p_genesis", "unity": "p_unity", "veo": "p_veo"}
        db_field = valid_fields.get(token_type)
        
        c.execute(f"""
            UPDATE users 
            SET {db_field} = {db_field} + %s, 
                energy = %s, 
                last_energy_update = %s, 
                last_click_time = %s 
            WHERE user_id = %s
        """, (final_reward, current_energy - 1, now_s, now_ms, uid))
        
        conn.commit()
        return {"ok": True, "reward": round(final_reward, 4), "new_energy": int(current_energy - 1)}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        c.close(); conn.close()
