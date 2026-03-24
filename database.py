import time
from data_conx import get_db_conn

def init_db_structure():
    conn = get_db_conn()
    if not conn: return
    conn.rollback() 
    try:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, name TEXT)")
        conn.commit()
        
        cols = [
            ("p_genesis", "DOUBLE PRECISION DEFAULT 0"),
            ("p_unity", "DOUBLE PRECISION DEFAULT 0"),
            ("p_veo", "DOUBLE PRECISION DEFAULT 0"),
            ("energy", "INTEGER DEFAULT 100"),
            ("last_energy_update", "BIGINT"),
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"),
            ("streak", "INTEGER DEFAULT 0"),
            ("last_click_time", "BIGINT DEFAULT 0")
        ]
        for col, dtype in cols:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
                conn.commit()
            except: conn.rollback()

        c.execute("""
            CREATE TABLE IF NOT EXISTS community_tokens (
                id SERIAL PRIMARY KEY, creator_id BIGINT, name TEXT, symbol TEXT, 
                logo TEXT, price DOUBLE PRECISION DEFAULT 0.0001, 
                reserve_wpt DOUBLE PRECISION DEFAULT 500, holders INTEGER DEFAULT 1, 
                volume DOUBLE PRECISION DEFAULT 0, created_at BIGINT
            )
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ DB Error: {e}")
    finally:
        c.close(); conn.close()

def get_user_full(uid):
    conn = get_db_conn()
    try:
        c = conn.cursor()
        c.execute("""SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, 
                     last_energy_update, streak, staked_amount FROM users WHERE user_id=%s""", (uid,))
        return c.fetchone()
    except: return None
    finally: conn.close()

def get_tokens_ordered(sort_type="new"):
    conn = get_db_conn(); c = conn.cursor()
    query = "SELECT name, symbol, logo, price, holders, reserve_wpt, volume FROM community_tokens "
    if sort_type == "new": query += "ORDER BY id DESC"
    elif sort_type == "mcap": query += "ORDER BY reserve_wpt DESC"
    else: query += "ORDER BY volume DESC" # Pour l'onglet "By Mislocap" (Volume)
    c.execute(query)
    res = c.fetchall()
    c.close(); conn.close()
    return res

def get_total_network_score():
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT SUM(COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users")
    res = c.fetchone()
    return res[0] if res and res[0] else 0
