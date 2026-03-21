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
