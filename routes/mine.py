from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import database, config, time

router = APIRouter(prefix="/api/mine", tags=["Mining"])

@router.get("/sync/{uid}")
async def sync_energy(uid: int):
    conn = database.get_db_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT energy, last_energy_update FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res: return {"error": "User not found"}
        
        energy, last_upd = res
        now_s = int(time.time())
        
        # Calcul de la recharge (on utilise config.REGEN_RATE qui est souvent 1% par minute)
        diff_s = now_s - (last_upd or now_s)
        # REGEN_RATE % par minute => (diff_s / 60) * REGEN_RATE
        regen = (diff_s / 60) * getattr(config, 'REGEN_RATE', 1.0)
        
        new_energy = min(getattr(config, 'MAX_ENERGY', 100), (energy or 0) + regen)
        
        # Sauvegarde immédiate du nouvel état
        c.execute("UPDATE users SET energy = %s, last_energy_update = %s WHERE user_id = %s", 
                  (new_energy, now_s, uid))
        conn.commit()
        
        return {"ok": True, "energy": int(new_energy), "max_energy": config.MAX_ENERGY}
    finally:
        c.close(); conn.close()


