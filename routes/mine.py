from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import database
import config
import time
from datetime import datetime # <--- IL MANQUAIT CELUI-LÀ !

router = APIRouter(prefix="/api/mine", tags=["Mining"])

# --- 1. SYNCHRONISATION & RECHARGE ---
@router.get("/sync/{uid}")
async def sync_energy(uid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT energy, last_energy_update, multiplier FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res: return {"error": "User not found"}
        
        energy, last_upd, multiplier = res
        now_s = int(time.time())
        
        regen_rate = getattr(config, 'REGEN_RATE', 1.0)
        max_energy = getattr(config, 'MAX_ENERGY', 100)
        
        # Calcul de la recharge
        last_upd_s = last_upd if last_upd else now_s
        diff_minutes = (now_s - last_upd_s) / 60
        new_energy = min(max_energy, (energy or 0) + (diff_minutes * regen_rate))
        
        c.execute("UPDATE users SET energy = %s, last_energy_update = %s WHERE user_id = %s", 
                  (new_energy, now_s, uid))
        conn.commit()
        
        return {
            "ok": True, 
            "energy": round(new_energy, 2), 
            "multiplier": multiplier or 1.0,
            "max_energy": max_energy
        }
    except Exception as e:
        print(f"❌ Error Sync: {e}")
        return {"error": str(e)}
    finally:
        c.close(); conn.close()

# --- 2. ACTION DE MINAGE ---
@router.post("")
async def mine_action(request: Request):
    try:
        data = await request.json()
        # FIX INDENTATION & KEY NAMES
        uid = data.get("user_id") or data.get("uid")
        token_type = data.get("token_type") or "genesis"
        
        if not uid:
            return JSONResponse(status_code=400, content={"error": "User ID missing in request"})

        conn = database.get_db_conn()
        c = conn.cursor()
        
        c.execute("""
            SELECT energy, last_energy_update, last_click_time, streak, multiplier, turbo_until 
            FROM users WHERE user_id = %s
        """, (uid,))
        res = c.fetchone()
        
        if not res: 
            c.close(); conn.close()
            return JSONResponse(status_code=400, content={"error": "User not found in database"})

        energy, last_upd, last_click, streak, multiplier, turbo_until = res
        now_ms = int(time.time() * 1000)
        now_s = now_ms // 1000

        # Anti-Spam (80ms)
        if last_click and (now_ms - last_click) < 80:
            c.close(); conn.close()
            return JSONResponse(status_code=400, content={"error": "Too fast"})

        # --- CALCUL ÉNERGIE SÉCURISÉ ---
        regen_rate = getattr(config, 'REGEN_RATE', 1.0)
        max_energy = getattr(config, 'MAX_ENERGY', 100)
        
        # Si last_upd est None, on prend le temps actuel
        l_upd = last_upd if last_upd else now_s
        diff_minutes = (now_s - l_upd) / 60
        
        current_energy = min(float(max_energy), float(energy or 0) + (diff_minutes * regen_rate))

        if current_energy < 1:
            c.close(); conn.close()
            return JSONResponse(status_code=400, content={"error": "Low energy"})

        # --- CALCUL RÉCOMPENSE ---
        base_reward = 0.05
        streak_boost = 1 + (min(streak or 0, 10) * 0.05)
        mag_boost = float(multiplier or 1.0)
        
        # Turbo check
        is_turbo = False
        if turbo_until and isinstance(turbo_until, datetime):
            if turbo_until > datetime.now():
                is_turbo = True
        
        turbo_boost = 2.0 if is_turbo else 1.0
        final_reward = base_reward * streak_boost * mag_boost * turbo_boost

        # --- MISE À JOUR ---
        valid_fields = {"genesis": "p_genesis", "unity": "p_unity", "veo": "p_veo"}
        db_field = valid_fields.get(token_type, "p_genesis")
        
        c.execute(f"""
            UPDATE users 
            SET {db_field} = COALESCE({db_field}, 0) + %s, 
                energy = %s, 
                last_energy_update = %s, 
                last_click_time = %s 
            WHERE user_id = %s
        """, (final_reward, current_energy - 1, now_s, now_ms, uid))
        
        conn.commit()
        return {
            "ok": True, 
            "reward": round(final_reward, 4), 
            "new_energy": int(current_energy - 1),
            "multiplier": mag_boost # On renvoie le multiplier pour le JS !
        }

    except Exception as e:
        print(f"❌ Critical Mine Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if 'c' in locals(): c.close()
        if 'conn' in locals(): conn.close()




@router.post("/burn")
async def burn_wpt(request: Request):
    try:
        data = await request.json()
        uid = data.get("user_id")
        amount = float(data.get("amount", 0))

        if amount <= 0: return {"ok": False, "error": "Invalid amount"}

        conn = database.get_db_conn()
        c = conn.cursor()

        # 1. Vérifier si l'utilisateur a assez de WPT (p_genesis)
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res or res[0] < amount:
            return {"ok": False, "error": "Insufficient balance"}

        # 2. Soustraire le montant et mettre à jour le global_burned (optionnel)
        c.execute("""
            UPDATE users 
            SET p_genesis = p_genesis - %s 
            WHERE user_id = %s
        """, (amount, uid))
        
        conn.commit()
        return {"ok": True, "new_balance": res[0] - amount}

    except Exception as e:
        print(f"Burn Error: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        c.close(); conn.close()
