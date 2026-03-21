import time
from data_conx import get_db_conn

def init_db_structure():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        cols = [
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"),
            ("streak", "INTEGER DEFAULT 0"),
            ("last_streak_date", "TEXT"),
            ("ref_claimed", "INTEGER DEFAULT 0"),
            ("last_energy_update", "BIGINT"),
            ("referred_by", "BIGINT"),
            ("ref_count", "INTEGER DEFAULT 0")
        ]
        for col, dtype in cols:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit()
        c.close(); conn.close()

def get_user_full(uid):
    conn = get_db_conn(); c = conn.cursor()
    c.execute("""SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, 
                 last_energy_update, streak, staked_amount, ref_claimed 
                 FROM users WHERE user_id=%s""", (uid,))
    res = c.fetchone()
    c.close(); conn.close()
    return res

def get_leaderboard():
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT name, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) as total FROM users ORDER BY total DESC LIMIT 8")
    res = c.fetchall()
    c.close(); conn.close()
    return res

def get_total_network_score():
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT SUM(COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users")
    res = c.fetchone()[0] or 0
    c.close(); conn.close()
    return res


def init_db_structure():
    conn = get_db_conn()
    if conn:
        c = conn.cursor()
        # Liste ultra-complète des colonnes
        cols = [
            ("p_genesis", "DOUBLE PRECISION DEFAULT 0"),
            ("p_unity", "DOUBLE PRECISION DEFAULT 0"),
            ("p_veo", "DOUBLE PRECISION DEFAULT 0"),
            ("energy", "INTEGER DEFAULT 100"),
            ("last_energy_update", "BIGINT"),
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"),
            ("streak", "INTEGER DEFAULT 0"),
            ("ref_count", "INTEGER DEFAULT 0"),
            ("ref_claimed", "INTEGER DEFAULT 0")
        ]
        for col, dtype in cols:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except:
                pass # La colonne existe déjà
        conn.commit()
        c.close(); conn.close()
