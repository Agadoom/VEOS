import psycopg2
import os
import time

def get_db_conn():
    # Utilise DATABASE_URL (Railway/Render) ou tes accès locaux
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db_structure():
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("DROP TABLE IF EXISTS community_tokens CASCADE") 
        c.execute("""CREATE TABLE community_tokens (
            id SERIAL PRIMARY KEY, 
            creator_id BIGINT, 
            name TEXT NOT NULL, 
            symbol TEXT NOT NULL, 
            description TEXT,
            logo_url TEXT,   -- Stockera le Base64 du logo
            banner_url TEXT, -- Stockera le Base64 de la bannière
            website TEXT,
            twitter_x TEXT,
            price DOUBLE PRECISION DEFAULT 0.0001, 
            mcap DOUBLE PRECISION DEFAULT 0, 
            volume DOUBLE PRECISION DEFAULT 0, 
            created_at BIGINT
        )""")
        conn.commit()
    except Exception as e: print(f"DB Error: {e}")
    finally: c.close(); conn.close()

# N'oublie pas de mettre à jour la fonction de déploiement pour accepter ces nouveaux champs
def deploy_token(uid, name, symbol, desc, logo, banner, web, x):
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        bal = c.fetchone()[0]
        if bal < 1000: return False, "1000 WPT requis"

        now = int(time.time())
        c.execute("UPDATE users SET p_genesis = p_genesis - 1000 WHERE user_id = %s", (uid,))
        c.execute("""INSERT INTO community_tokens (creator_id, name, symbol, description, logo_url, banner_url, website, twitter_x, created_at) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                  (uid, name, symbol, desc, logo, banner, web, x, now))
        conn.commit()
        return True, "Token lancé !"
    except Exception as e: return False, str(e)
    finally: c.close(); conn.close()



# --- FONCTIONS UTILISATEURS ---

def get_user_full(uid):
    conn = get_db_conn(); c = conn.cursor()
    try:
        # Ordre pour main.py : gen, uni, veo, ref, name, energy, last_upd, streak, staked
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

# --- FONCTIONS LAUNCHER (DEV SPÉCIAL) ---

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
    conn = get_db_conn()
    c = conn.cursor()
    try:
        # 1. Vérifier si l'utilisateur a assez de WPT (1000 Genesis)
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res or float(res[0] or 0) < 1000:
            return False, "Solde insuffisant (1000 WPT requis)"

        now = int(time.time())

        # 2. Déduire les 1000 WPT
        c.execute("UPDATE users SET p_genesis = p_genesis - 1000 WHERE user_id = %s", (uid,))

        # 3. Insérer le nouveau token avec tous les champs (Logo/Banner en Base64)
        c.execute("""
            INSERT INTO community_tokens 
            (creator_id, name, symbol, description, logo_url, banner_url, website, twitter_x, price, mcap, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0.0001, 0, %s)
        """, (uid, name, symbol, desc, logo, banner, web, x, now))
        
        conn.commit()
        return True, "Token déployé avec succès !"
    except Exception as e:
        conn.rollback()
        print(f"Erreur Deploy: {e}")
        return False, str(e)
    finally:
        c.close()
        conn.close()



def buy_token(uid, token_id, amount_wpt):
    conn = get_db_conn(); c = conn.cursor()
    try:
        # 1. Check solde
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        res = c.fetchone()
        if not res or res[0] < amount_wpt: return False, "Solde Genesis insuffisant."

        # 2. Infos Token
        c.execute("SELECT price, mcap, creator_id FROM community_tokens WHERE id = %s", (token_id,))
        t = c.fetchone()
        if not t: return False, "Token introuvable."
        
        cur_price = t[0]
        creator_id = t[2]
        
        # 3. Calcul Bonding Curve simple
        # Le prix augmente de façon proportionnelle à l'achat
        tokens_bought = amount_wpt / cur_price
        fee = amount_wpt * 0.02 # 2% de frais
        
        new_price = cur_price * (1 + (amount_wpt / 10000))
        new_mcap = t[1] + amount_wpt

        # 4. Updates
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (amount_wpt, uid))
        c.execute("UPDATE users SET p_genesis = p_genesis + %s WHERE user_id = %s", (fee/2, creator_id)) # Creator Fee
        c.execute("UPDATE community_tokens SET price = %s, mcap = %s, volume = volume + %s WHERE id = %s", 
                  (new_price, new_mcap, amount_wpt, token_id))
        
        # Portfolio update
        c.execute("""INSERT INTO user_portfolio (user_id, token_id, amount) VALUES (%s, %s, %s)
                     ON CONFLICT (user_id, token_id) DO UPDATE SET amount = user_portfolio.amount + %s""",
                  (uid, token_id, tokens_bought, tokens_bought))
        
        conn.commit()
        return True, "Achat validé !"
    except Exception as e:
        conn.rollback(); return False, str(e)
    finally:
        c.close(); conn.close()
