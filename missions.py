import time
from database import get_db_conn

async def process_stake(uid):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users WHERE user_id = %s", (uid,))
    total = c.fetchone()[0] or 0
    if total >= 100:
        c.execute("UPDATE users SET p_genesis=p_genesis-34, p_unity=p_unity-33, p_veo=p_veo-33, staked_amount=COALESCE(staked_amount,0)+100 WHERE user_id=%s", (uid,))
        conn.commit()
        success = True
    else:
        success = False
    c.close()
    conn.close()
    return success

async def process_daily(uid):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET p_genesis = COALESCE(p_genesis,0) + 5, streak = COALESCE(streak,0) + 1 WHERE user_id = %s", (uid,))
    conn.commit()
    c.close()
    conn.close()
    return True
