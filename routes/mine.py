from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import database
import config
import time

router = APIRouter(prefix="/api/mine", tags=["Mining"])

# --- 1. ROUTE DE SYNCHRONISATION (Update énergie au chargement) ---
@router.get("/sync/{uid}")
async def sync_energy(uid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT energy, last_energy_update FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res:
            return {"error": "User not found"}
        
        energy, last_upd = res
        now_s = int(time.time())
        
        # Calcul de la recharge basée sur le temps écoulé
        # On récupère REGEN_RATE (ex: 1% par minute) et MAX_ENERGY (ex: 100)
        regen_rate = getattr(config, 'REGEN_RATE', 1.0)
        max_energy = getattr(config, 'MAX_ENERGY', 100)
        
        last_upd_s = last_upd if last_upd else now_s
        diff_minutes = (now_s - last_upd_s) / 60
        
        # Formule : Energie actuelle + (Minutes écoulées * Taux de recharge)
        calculated_energy = (energy or 0) + (diff_minutes * regen_rate)
        new_energy = min(max_energy, calculated_energy)
        
        # On sauvegarde tout de suite pour "figer" le temps
        c.execute("""
            UPDATE users 
            SET energy = %s, last_energy_update = %s 
            WHERE user_id = %s
        """, (new_energy, now_s, uid))
        
        conn.commit()
        return {
            "ok": True, 
            "energy": round(new_energy, 2), 
            "max_energy": max_energy,
            "display_energy": int(new_energy)
        }
    except Exception as e:
        print(f"❌ Erreur Sync Energy: {e}")
        return {"error": str(e)}
    finally:
        c.close(); conn.close()

# --- 2. ROUTE D'ACTION (Le Clic de Minage) ---
@router.post("")
async def mine_action(request: Request):
    try:
        data = await request.json()
        uid = data.get("user_id")
        token_type = data.get("token_type") # genesis, unity ou veo
        
        if not uid or not token_type:
            return JSONResponse(status_code=400, content={"error": "Data missing"})

        conn = database.get_db_conn()
        c = conn.cursor()
        
        # On récupère les infos vitales
        c.execute("""
            SELECT energy, last_energy_update, last_click_time, streak, p_genesis, p_unity, p_veo 
            FROM users WHERE user_id = %s
        """, (uid,))
        res = c.fetchone()
        
        if not res:
            return JSONResponse(status_code=400, content={"error": "User not found"})

        energy, last_upd, last_click, streak, p_gen, p_uni, p_veo = res
        now_ms = int(time.time() * 1000)
        now_s = now_ms // 1000
        
        # --- A. RECHARGE TEMPS RÉEL (Calcul de sécurité avant le clic) ---
        regen_rate = getattr(config, 'REGEN_RATE', 1.0)
        max_energy = getattr(config, 'MAX_ENERGY', 100)
        diff_minutes = (now_s - (last_upd or now_s)) / 60
        current_energy = min(max_energy, (energy or 0) + (diff_minutes * regen_rate))

        # --- B. VÉRIFICATIONS ANTI-CHEAT ---
        # 1. Anti-Spam (80ms entre chaque clic)
        if (now_ms - (last_click or 0)) < 80:
            return JSONResponse(status_code=400, content={"error": "Too fast! Calma."})
        
        # 2. Vérification Energie
        if current_energy < 1:
            return JSONResponse(status_code=400, content={"error": "Out of energy. Wait for recharge."})

        # --- C. CALCUL DES GAINS ---
        base_reward = 0.05
        # Bonus Streak : +5% par jour de connexion (max +50%)
        streak_bonus = 1 + (min(streak or 0, 10) * 0.05)
        final_reward = base_reward * streak_bonus

        # --- D. MISE À JOUR BASE DE DONNÉES ---
        valid_fields = {"genesis": "p_genesis", "unity": "p_unity", "veo": "p_veo"}
        db_field = valid_fields.get(token_type)
        
        if not db_field:
            return JSONResponse(status_code=400, content={"error": "Invalid token type"})

        c.execute(f"""
            UPDATE users 
            SET {db_field} = {db_field} + %s, 
                energy = %s, 
                last_energy_update = %s, 
                last_click_time = %s 
            WHERE user_id = %s
        """, (final_reward, current_energy - 1, now_s, now_ms, uid))
        
        conn.commit()
        
        return {
            "ok": True, 
            "reward": round(final_reward, 4), 
            "new_energy": int(current_energy - 1)
        }

    except Exception as e:
        print(f"❌ Critical Mine Error: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
    finally:
        if 'c' in locals(): c.close()
        if 'conn' in locals(): conn.close()
