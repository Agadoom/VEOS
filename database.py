from data_conx import get_db_conn
import time

def init_db_structure():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        # On s'assure que les colonnes de base et les nouvelles existent
        cols = [
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"),
            ("streak", "INTEGER DEFAULT 0"),
            ("last_streak_date", "TEXT"),
            ("ref_claimed", "INTEGER DEFAULT 0"),
            ("last_energy_update", "BIGINT"),
            ("energy", "INTEGER DEFAULT 100")
        ]
        for col, dtype in cols:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except:
                pass
        conn.commit()
        c.close()
        conn.close()

def get_user_data(uid):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("""SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, 
                 last_energy_update, streak, staked_amount, ref_claimed 
                 FROM users WHERE user_id=%s""", (uid,))
    res = c.fetchone()
    c.close()
    conn.close()
    return res

def register_user(uid, name, ref_id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = %s", (uid,))
    if not c.fetchone():
        c.execute("""INSERT INTO users (user_id, name, referred_by, energy, last_energy_update) 
                     VALUES (%s, %s, %s, 100, %s)""", 
                  (uid, name, ref_id if ref_id != uid else None, int(time.time())))
        if ref_id and ref_id != uid:
            c.execute("UPDATE users SET ref_count = COALESCE(ref_count,0) + 1 WHERE user_id = %s", (ref_id,))
    conn.commit()
    c.close()
    conn.close()
