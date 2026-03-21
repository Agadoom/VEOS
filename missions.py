import time
import config
from database import get_db_conn

def get_badge_info(score):
    if score >= 500: return "💎 Diamond", 1000, "#00D1FF"
    if score >= 150: return "🥇 Gold", 500, "#FFD700"
    if score >= 50:  return "🥈 Silver", 150, "#C0C0C0"
    return "🥉 Bronze", 50, "#CD7F32"

async def register_user(uid, name, ref_id):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
    if not c.fetchone():
        c.execute("""INSERT INTO users (user_id, name, referred_by, energy, last_energy_update, staked_amount, streak) 
                     VALUES (%s, %s, %s, %s, %s, 0, 0)""", 
                  (uid, name, ref_id if ref_id != uid else None, config.MAX_ENERGY, int(time.time())))
        if ref_id and ref_id != uid:
            c.execute("UPDATE users SET ref_count = COALESCE(ref_count,0) + 1 WHERE user_id = %s", (ref_id,))
    conn.commit(); c.close(); conn.close()
async def process_boost_energy(uid, max_energy):
    conn = get_db_conn()
    c = conn.cursor()
    # Vérifier le solde total
    c.execute("SELECT (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users WHERE user_id=%s", (uid,))
    balance = c.fetchone()[0] or 0
    
    if balance >= 50: # Prix du boost
        # On déduit le prix (réparti sur les 3 assets) et on remet l'énergie au max
        c.execute("""UPDATE users SET 
                     p_genesis=p_genesis-17, p_unity=p_unity-17, p_veo=p_veo-16, 
                     energy=%s, last_energy_update=%s 
                     WHERE user_id=%s""", (max_energy, int(time.time()), uid))
        conn.commit()
        success = True
    else:
        success = False
    
    c.close(); conn.close()
    return success
