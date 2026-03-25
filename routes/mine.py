from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse # <--- Correction ici
import database, config, time

router = APIRouter(prefix="/api/mine", tags=["Mining"])

@router.post("")
async def mine_action(request: Request):
    data = await request.json()
    uid, token_type = data.get("user_id"), data.get("token")
    
    conn = database.get_db_conn()
    c = conn.cursor()
    c.execute("SELECT energy, last_energy_update, last_click_time FROM users WHERE user_id = %s", (uid,))
    res = c.fetchone()
    
    now_ms = int(time.time() * 1000)
    now_s = now_ms // 1000
    
    if res and (now_ms - (res[2] or 0)) >= 80: # Anti-click spam 80ms
        cur_e = min(config.MAX_ENERGY, (res[0] or 0) + ((now_s - (res[1] or now_s))/60) * config.REGEN_RATE)
        
        if cur_e >= 1:
            # Update the specific token (genesis, unity, or veo)
            field = f"p_{token_type}"
            c.execute(f"""
                UPDATE users 
                SET {field} = COALESCE({field}, 0) + 0.05, 
                    energy = %s, 
                    last_energy_update = %s, 
                    last_click_time = %s 
                WHERE user_id = %s
            """, (cur_e - 1, now_s, now_ms, uid))
            conn.commit()
            c.close()
            conn.close()
            return {"ok": True}
            
    c.close()
    conn.close()
    return JSONResponse(status_code=400, content={"error": "Not enough energy or too fast"})
