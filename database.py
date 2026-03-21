import time
from data_conx import get_db_conn

def init_db_structure():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        # Liste des colonnes nécessaires
        cols = [
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"),
            ("streak", "INTEGER DEFAULT 0"),
            ("last_streak_date", "TEXT"),
            ("ref_claimed", "INTEGER DEFAULT 0"),
            ("last_energy_update", "BIGINT"),
            ("referred_by", "BIGINT")
        ]
        for col, dtype in cols:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except:
                pass # La colonne existe déjà
        conn.commit()
        c.close()
        conn.close()

def get_user(uid):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("""SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, 
                 last_energy_update, streak, staked_amount, ref_claimed 
                 FROM users WHERE user_id=%s""", (uid,))
    res = c.fetchone()
    c.close()
    conn.close()
    return res

def save_mine(uid, token, amount, new_energy, now):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute(f"UPDATE users SET p_{token}=COALESCE(p_{token},0)+%s, energy=%s, last_energy_update=%s WHERE user_id=%s", 
              (amount, new_energy, now, uid))
    conn.commit()
    c.close()
    conn.close()
