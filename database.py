import psycopg2
import os
import time

def get_db_conn():
    # Utilise DATABASE_URL (Railway/Render) ou tes accès locaux
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

        # Table des actifs possédés par les utilisateurs (C'EST ICI QUE CA CRASHAIT)
        c.execute("""CREATE TABLE IF NOT EXISTS user_community_assets (
            user_id BIGINT,
            token_id INTEGER,
            amount DOUBLE PRECISION DEFAULT 0,
            PRIMARY KEY (user_id, token_id)
        )""")

        # Table de l'activité (Historique des transactions)
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
        print("Base de données initialisée avec succès !")
    except Exception as e:
        print(f"DB Error Init: {e}")
    finally:
        c.close()
        conn.close()

# --- FONCTIONS UTILISATEURS ---

def get_user_full(uid):
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("""SELECT p_genesis, p_unity, p_veo, 0, name, energy, 
                     last_energy_update, streak, 0 FROM users WHERE user_id=%s""", (uid,))
        return c.fetchone()
    finally:
        c.close(); conn.close()

def get_leaderboard():
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("""SELECT name, (COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) as total 
                     FROM users ORDER BY total DESC LIMIT 10""")
        return c.fetchall()
    finally:
        c.close(); conn.close()

def get_total_network_score():
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT SUM(COALESCE(p_genesis,0)+COALESCE(p_unity,0)+COALESCE(p_veo,0)) FROM users")
        res = c.fetchone()
        return res[0] if res and res[0] else 0
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
        return [
            {
                "id": r[0], "name": r[1], "sym": r[2], "price": r[3], 
                "mcap": r[4], "logo": r[5], "banner": r[6], 
                "desc": r[7], "web": r[8], "x": r[9]
            } for r in res
        ]
    finally:
        c.close(); conn.close()

def deploy_token(uid, name, symbol, desc, logo, banner, web, x):
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res or float(res[0] or 0) < 1000:
            return False, "Solde insuffisant (1000 WPT requis)"

        now = int(time.time())
        c.execute("UPDATE users SET p_genesis = p_genesis - 1000 WHERE user_id = %s", (uid,))
        c.execute("""INSERT INTO community_tokens (creator_id, name, symbol, description, logo_url, banner_url, website, twitter_x, created_at) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                  (uid, name, symbol, desc, logo, banner, web, x, now))
        conn.commit()
        return True, "Token lancé !"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        c.close(); conn.close()

def buy_token(uid, token_id, amount_wpt):
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT p_genesis, name FROM users WHERE user_id = %s", (uid,))
        u = c.fetchone()
        if not u or u[0] < amount_wpt: return False, "Solde Genesis insuffisant."
        user_name = u[1]

        c.execute("SELECT price, mcap, creator_id FROM community_tokens WHERE id = %s", (token_id,))
        t = c.fetchone()
        if not t: return False, "Token introuvable."
        
        cur_price = t[0]
        tokens_bought = amount_wpt / cur_price
        new_price = cur_price * (1 + (amount_wpt / 20000)) # Bonding curve
        
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (amount_wpt, uid))
        c.execute("UPDATE community_tokens SET price = %s, mcap = mcap + %s WHERE id = %s", (new_price, amount_wpt, token_id))
        
        c.execute("""INSERT INTO user_community_assets (user_id, token_id, amount) VALUES (%s, %s, %s)
                     ON CONFLICT (user_id, token_id) DO UPDATE SET amount = user_community_assets.amount + %s""",
                  (uid, token_id, tokens_bought, tokens_bought))

        c.execute("INSERT INTO token_activity (token_id, user_id, user_name, type, amount_wpt, created_at) VALUES (%s, %s, %s, %s, %s, %s)", 
                  (token_id, uid, user_name, 'BUY', amount_wpt, int(time.time())))
        
        conn.commit()
        return True, "Achat validé !"
    except Exception as e:
        conn.rollback(); return False, str(e)
    finally:
        c.close(); conn.close()

def sell_token(uid, token_id):
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT amount FROM user_community_assets WHERE user_id = %s AND token_id = %s", (uid, token_id))
        res = c.fetchone()
        if not res or res[0] <= 0: return False, "Tu ne possèdes pas ce token."
        amt = res[0]

        c.execute("SELECT price, mcap FROM community_tokens WHERE id = %s", (token_id,))
        t = c.fetchone()
        gain_wpt = amt * t[0]
        
        c.execute("UPDATE user_community_assets SET amount = 0 WHERE user_id = %s AND token_id = %s", (uid, token_id))
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (gain_wpt, uid))
        
        new_price = max(0.00001, t[0] * 0.95)
        c.execute("UPDATE community_tokens SET price = %s, mcap = GREATEST(0, mcap - %s) WHERE id = %s", (new_price, gain_wpt, token_id))
        
        conn.commit()
        return True, f"Vendu ! +{round(gain_wpt, 2)} WPT"
    finally:
        c.close(); conn.close()

def get_token_activity(token_id):
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT user_name, type, amount_wpt, created_at FROM token_activity WHERE token_id = %s ORDER BY created_at DESC LIMIT 10", (token_id,))
        res = c.fetchall()
        return [{"name": r[0], "type": r[1], "amt": r[2], "time": r[3]} for r in res]
    finally:
        c.close(); conn.close()
