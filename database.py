import time
from data_conx import get_db_conn

def init_db_structure():
    conn = get_db_conn()
    if not conn: return
    try:
        c = conn.cursor()
        # On s'assure que la table users existe d'abord
        c.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, name TEXT)")
        
        cols = [
            ("p_genesis", "DOUBLE PRECISION DEFAULT 0"),
            ("p_unity", "DOUBLE PRECISION DEFAULT 0"),
            ("p_veo", "DOUBLE PRECISION DEFAULT 0"),
            ("energy", "INTEGER DEFAULT 100"),
            ("last_energy_update", "BIGINT"),
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"),
            ("streak", "INTEGER DEFAULT 0"),
            ("last_streak_date", "TEXT"),
            ("ref_count", "INTEGER DEFAULT 0"),
            ("ref_claimed", "INTEGER DEFAULT 0"),
            ("last_login_date", "TEXT"),
            ("last_click_time", "BIGINT DEFAULT 0")
        ]
        for col, dtype in cols:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except:
                pass 

        c.execute("""
            CREATE TABLE IF NOT EXISTS community_tokens (
                id SERIAL PRIMARY KEY,
                creator_id BIGINT,
                name TEXT,
                symbol TEXT,
                logo TEXT,
                price DOUBLE PRECISION DEFAULT 0.0001,
                reserve_wpt DOUBLE PRECISION DEFAULT 500,
                holders INTEGER DEFAULT 1,
                created_at BIGINT
            )
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ DB Init Error: {e}")
    finally:
        c.close(); conn.close()

def get_user_full(uid):
    conn = get_db_conn()
    if not conn: return None
    try:
        c = conn.cursor()
        c.execute("""SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, 
                     last_energy_update, streak, staked_amount, ref_claimed 
                     FROM users WHERE user_id=%s""", (uid,))
        return c.fetchone()
    except:
        conn.rollback(); return None
    finally:
        c.close(); conn.close()

def get_leaderboard():
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT name, (COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) as total FROM users ORDER BY total DESC LIMIT 8")
        return c.fetchall()
    except:
        conn.rollback(); return []
    finally:
        c.close(); conn.close()

def get_total_network_score():
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT SUM(COALESCE(p_genesis,0) + COALESCE(p_unity,0) + COALESCE(p_veo,0)) FROM users")
        res = c.fetchone()
        return res[0] if res and res[0] else 0
    except:
        conn.rollback(); return 0
    finally:
        c.close(); conn.close()
