import psycopg2
import os
import time

def get_db_conn():
    # Remplace par ta DATABASE_URL Railway si nécessaire
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db_structure():
    conn = get_db_conn()
    conn.rollback() # Nettoie les transactions en cours
    c = conn.cursor()
    try:
        # Table Utilisateurs
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY, 
            name TEXT, 
            referred_by BIGINT,
            ref_count INTEGER DEFAULT 0,
            ref_claimed INTEGER DEFAULT 0,
            p_genesis DOUBLE PRECISION DEFAULT 0,
            p_unity DOUBLE PRECISION DEFAULT 0,
            p_veo DOUBLE PRECISION DEFAULT 0,
            energy INTEGER DEFAULT 100,
            last_energy_update BIGINT,
            last_click_time BIGINT DEFAULT 0,
            staked_amount DOUBLE PRECISION DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_login_date TEXT
        )""")
        
        # Table Tokens Communautaires (Launcher)
          # Table Tokens : On force des valeurs par défaut pour éviter le "0" ou le vide
        c.execute("""CREATE TABLE IF NOT EXISTS community_tokens (
            id SERIAL PRIMARY KEY, 
            creator_id BIGINT, 
            name TEXT NOT NULL, 
            symbol TEXT NOT NULL, 
            logo TEXT, 
            price DOUBLE PRECISION DEFAULT 0.0001, 
            reserve_wpt DOUBLE PRECISION DEFAULT 500, 
            holders INTEGER DEFAULT 1, 
            volume DOUBLE PRECISION DEFAULT 0, 
            created_at BIGINT
        )""")
        conn.commit()
    except Exception as e:
        print(f"DB Init Error: {e}")
    finally:
        c.close(); conn.close()

def get_user_full(uid):
    conn = get_db_conn(); c = conn.cursor()
    # ORDRE CRITIQUE : 0:gen, 1:uni, 2:veo, 3:ref, 4:name, 5:energy, 6:last_upd, 7:streak, 8:staked
    c.execute("""SELECT p_genesis, p_unity, p_veo, ref_count, name, energy, 
                 last_energy_update, streak, staked_amount FROM users WHERE user_id=%s""", (uid,))
    res = c.fetchone()
    c.close(); conn.close()
    return res


def get_leaderboard():
    conn = get_db_conn(); c = conn.cursor()
    c.execute("""SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as total 
                 FROM users ORDER BY total DESC LIMIT 10""")
    res = c.fetchall()
    c.close(); conn.close()
    return res

def get_total_network_score():
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT SUM(COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users")
    res = c.fetchone()
    c.close(); conn.close()
    return res[0] if res and res[0] else 0

def get_tokens_ordered(sort_type="new"):
    conn = get_db_conn(); c = conn.cursor()
    # Tri SQL strict
    if sort_type == "mcap": order = "reserve_wpt DESC"
    elif sort_type == "vol": order = "volume DESC"
    else: order = "id DESC" # Le plus récent en haut
    
    c.execute(f"SELECT name, symbol, logo, price, holders, reserve_wpt, volume FROM community_tokens ORDER BY {order}")
    res = c.fetchall()
    c.close(); conn.close()
    return res

