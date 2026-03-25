import psycopg2
import os
import time

def get_db_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db_structure():
    conn = get_db_conn()
    c = conn.cursor()
    try:
        # 1. Création/Mise à jour de la table users
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            p_genesis DOUBLE PRECISION DEFAULT 0,
            p_unity DOUBLE PRECISION DEFAULT 0,
            p_veo DOUBLE PRECISION DEFAULT 0,
            energy INTEGER DEFAULT 100,
            last_energy_update INTEGER,
            last_click_time BIGINT,
            streak INTEGER DEFAULT 0,
            referrer_id BIGINT,
            last_login_date TEXT
        )""")

        # SÉCURITÉ : On s'assure que les colonnes ajoutées tardivement existent
        columns = [
            ("referrer_id", "BIGINT"),
            ("last_login_date", "TEXT"),
            ("streak", "INTEGER DEFAULT 0")
        ]
        for col_name, col_type in columns:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            except:
                pass

        # 2. Table des tokens communautaires
        c.execute("""CREATE TABLE IF NOT EXISTS community_tokens (
            id SERIAL PRIMARY KEY, 
            creator_id BIGINT, 
            name TEXT NOT NULL, 
            symbol TEXT NOT NULL, 
            description TEXT,
            logo_url TEXT,
            banner_url TEXT,
            website TEXT,
            twitter_x TEXT,
            price DOUBLE PRECISION DEFAULT 0.0001, 
            mcap DOUBLE PRECISION DEFAULT 0, 
            volume DOUBLE PRECISION DEFAULT 0, 
            created_at BIGINT
        )""")

        # 3. Table des actifs possédés
        c.execute("""CREATE TABLE IF NOT EXISTS user_community_assets (
            user_id BIGINT,
            token_id INTEGER,
            amount DOUBLE PRECISION DEFAULT 0,
            PRIMARY KEY (user_id, token_id)
        )""")

        # 4. Table de l'activité
        c.execute("""CREATE TABLE IF NOT EXISTS token_activity (
            id SERIAL PRIMARY KEY,
            token_id INTEGER,
            user_id BIGINT,
            user_name TEXT,
            type TEXT,
            amount_wpt DOUBLE PRECISION,
            created_at INTEGER
        )""")
        
        conn.commit()
        print("🚀 Database structure verified and updated!")
    except Exception as e:
        print(f"DB Error Init: {e}")
    finally:
        c.close(); conn.close()

# --- FONCTIONS UTILISATEURS ---

def get_user_full(uid):
    conn = get_db_conn(); c = conn.cursor()
    try:
        # Ordre des index : 0:genesis, 1:unity, 2:veo, 3:unused, 4:name, 
        # 5:energy, 6:last_upd, 7:streak, 8:unused, 9:referrer, 10:last_login
        c.execute("""SELECT p_genesis, p_unity, p_veo, 0, name, energy, 
                     last_energy_update, streak, 0, referrer_id, last_login_date 
                     FROM users WHERE user_id=%s""", (uid,))
        res = c.fetchone()
        if not res: 
            now = int(time.time())
            c.execute("INSERT INTO users (user_id, name, energy, last_energy_update, streak) VALUES (%s, 'New Citizen', 100, %s, 0)", (uid, now))
            conn.commit()
            return (0, 0, 0, 0, 'New Citizen', 100, now, 0, 0, None, None)
        return res
    finally:
        c.close(); conn.close()

def get_community_tokens():
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("""SELECT id, name, symbol, price, mcap, logo_url, 
                     banner_url, description, website, twitter_x 
                     FROM community_tokens ORDER BY mcap DESC""")
        res = c.fetchall()
        return [
            {
                "id": r[0], "name": r[1], "sym": r[2], 
                "price": float(r[3] or 0), "mcap": float(r[4] or 0), 
                "logo": r[5] or "", "banner": r[6] or "",
                "desc": r[7], "web": r[8], "x": r[9]
            } for r in res
        ]
    finally:
        c.close(); conn.close()

def add_referral_reward(new_user_id, referrer_id):
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (referrer_id,))
        if c.fetchone():
            c.execute("UPDATE users SET p_genesis = p_genesis + 500 WHERE user_id = %s", (referrer_id,))
            c.execute("UPDATE users SET p_genesis = p_genesis + 100, referrer_id = %s WHERE user_id = %s", (referrer_id, new_user_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"Referral Error: {e}")
        conn.rollback()
    finally:
        c.close(); conn.close()
    return False
