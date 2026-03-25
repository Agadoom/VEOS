import psycopg2
import os
import time

def get_db_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db_structure():
    conn = get_db_conn()
    c = conn.cursor()
    try:
        # Table des utilisateurs
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            p_genesis DOUBLE PRECISION DEFAULT 0,
            p_unity DOUBLE PRECISION DEFAULT 0,
            p_veo DOUBLE PRECISION DEFAULT 0,
            energy INTEGER DEFAULT 100,
            last_energy_update INTEGER,
            last_click_time BIGINT,
            streak INTEGER DEFAULT 0
            referrer_id BIGINT
        )""")

        # Table des tokens communautaires
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

        # Table des actifs possédés
        c.execute("""CREATE TABLE IF NOT EXISTS user_community_assets (
            user_id BIGINT,
            token_id INTEGER,
            amount DOUBLE PRECISION DEFAULT 0,
            PRIMARY KEY (user_id, token_id)
        )""")

        # Table de l'activité
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
        print("Database structure verified/updated.")
    except Exception as e:
        print(f"DB Error Init: {e}")
    finally:
        c.close(); conn.close()

# --- FONCTIONS UTILISATEURS ---

def get_user_full(uid):
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("""SELECT p_genesis, p_unity, p_veo, 0, name, energy, 
                     last_energy_update, streak, 0 FROM users WHERE user_id=%s""", (uid,))
        res = c.fetchone()
        if not res: # Auto-create user if missing
            c.execute("INSERT INTO users (user_id, name, energy) VALUES (%s, 'New User', 100)", (uid,))
            conn.commit()
            return (0, 0, 0, 0, 'New User', 100, int(time.time()), 0, 0)
        return res
    finally:
        c.close(); conn.close()

# --- FONCTIONS LAUNCHER ---

def get_community_tokens():
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("""SELECT id, name, symbol, price, mcap, logo_url, 
                     banner_url, description, website, twitter_x 
                     FROM community_tokens ORDER BY mcap DESC""")
        res = c.fetchall()
        return [{"id": r[0], "name": r[1], "sym": r[2], "price": r[3], "mcap": r[4], "logo": r[5], "banner": r[6], "desc": r[7], "web": r[8], "x": r[9]} for r in res]
    finally:
        c.close(); conn.close()

def deploy_token(uid, name, symbol, desc, logo, banner, web, x):
    """Lancé après validation du paiement Stars dans main.py"""
    conn = get_db_conn(); c = conn.cursor()
    try:
        now = int(time.time())
        c.execute("""INSERT INTO community_tokens (creator_id, name, symbol, description, logo_url, banner_url, website, twitter_x, created_at, mcap) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)""", 
                  (uid, name, symbol, desc, logo, banner, web, x, now))
        conn.commit()
        return True
    except Exception as e:
        print(f"Deploy Error: {e}")
        return False
    finally:
        c.close(); conn.close()

def buy_token(uid, token_id, qty):
    """Lancé après validation hybride (WPT déduits + Stars payés) dans main.py"""
    conn = get_db_conn(); c = conn.cursor()
    try:
        # On récupère le prix actuel
        c.execute("SELECT price, mcap, name FROM community_tokens WHERE id = %s", (token_id,))
        t = c.fetchone()
        if not t: return False
        
        cur_price = t[0]
        cost_wpt = qty * cur_price # Simulation de l'impact
        
        # Bonding Curve : Le prix augmente de 0.1% par achat
        new_price = cur_price * 1.001 
        
        # Mise à jour du Wallet Asset
        c.execute("""INSERT INTO user_community_assets (user_id, token_id, amount) VALUES (%s, %s, %s)
                     ON CONFLICT (user_id, token_id) DO UPDATE SET amount = user_community_assets.amount + %s""",
                  (uid, token_id, qty, qty))
        
        # Mise à jour du Token (Prix et Marketcap)
        c.execute("UPDATE community_tokens SET price = %s, mcap = mcap + %s WHERE id = %s", (new_price, qty * cur_price, token_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Buy Error: {e}")
        conn.rollback(); return False
    finally:
        c.close(); conn.close()


def add_referral_reward(new_user_id, referrer_id):
    conn = get_db_conn(); c = conn.cursor()
    try:
        # On vérifie si le parrain existe
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (referrer_id,))
        if c.fetchone():
            # Récompense : 500 WPT pour le parrain, 100 WPT pour le nouvel ami
            c.execute("UPDATE users SET p_genesis = p_genesis + 500 WHERE user_id = %s", (referrer_id,))
            c.execute("UPDATE users SET p_genesis = p_genesis + 100, referrer_id = %s WHERE user_id = %s", (referrer_id, new_user_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"Referral Error: {e}")
    finally:
        c.close(); conn.close()
    return False

