import psycopg2, os, time

def get_db_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db_structure():
    conn = get_db_conn(); c = conn.cursor()
    try:
        # Table Users
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY, name TEXT, referred_by BIGINT,
            p_genesis DOUBLE PRECISION DEFAULT 0, p_unity DOUBLE PRECISION DEFAULT 0,
            p_veo DOUBLE PRECISION DEFAULT 0, energy INTEGER DEFAULT 100,
            last_energy_update BIGINT, last_click_time BIGINT DEFAULT 0,
            streak INTEGER DEFAULT 0
        )""")
        
        # Table Tokens : Ajout MCAP pour la Bonding Curve
        c.execute("""CREATE TABLE IF NOT EXISTS community_tokens (
            id SERIAL PRIMARY KEY, creator_id BIGINT, 
            name TEXT NOT NULL, symbol TEXT NOT NULL, 
            price DOUBLE PRECISION DEFAULT 0.0001, 
            mcap DOUBLE PRECISION DEFAULT 0, 
            volume DOUBLE PRECISION DEFAULT 0, 
            created_at BIGINT
        )""")
        
        # Table Portfolio (Pour savoir qui possède quoi)
        c.execute("""CREATE TABLE IF NOT EXISTS user_portfolio (
            user_id BIGINT, token_id INTEGER, amount DOUBLE PRECISION DEFAULT 0,
            PRIMARY KEY(user_id, token_id)
        )""")
        conn.commit()
    except Exception as e: print(f"DB Error: {e}")
    finally: c.close(); conn.close()

def buy_token(uid, token_id, amount_wpt):
    conn = get_db_conn(); c = conn.cursor()
    try:
        c.execute("SELECT p_genesis FROM users WHERE user_id = %s", (uid,))
        bal = c.fetchone()[0]
        if bal < amount_wpt: return False, "Solde WPT insuffisant"

        c.execute("SELECT price, mcap, creator_id FROM community_tokens WHERE id = %s", (token_id,))
        t = c.fetchone()
        cur_price = t[0]; creator_id = t[2]

        # Calcul tokens reçus et frais
        tokens_out = amount_wpt / cur_price
        fee = amount_wpt * 0.02

        # Bonding Curve : Prix augmente de 0.1% par unité de volume relative
        new_price = cur_price * (1 + (amount_wpt / 5000))
        
        c.execute("UPDATE users SET p_genesis = p_genesis - %s WHERE user_id = %s", (amount_wpt, uid))
        c.execute("UPDATE community_tokens SET price = %s, mcap = mcap + %s, volume = volume + %s WHERE id = %s", (new_price, amount_wpt, amount_wpt, token_id))
        
        # Mise à jour portfolio
        c.execute("INSERT INTO user_portfolio (user_id, token_id, amount) VALUES (%s, %s, %s) ON CONFLICT (user_id, token_id) DO UPDATE SET amount = user_portfolio.amount + %s", (uid, token_id, tokens_out, tokens_out))
        
        conn.commit()
        return True, f"Achat réussi : {tokens_out:.2f} tokens"
    except Exception as e: return False, str(e)
    finally: c.close(); conn.close()

# Ajoute cette fonction pour lister les tokens dans l'API


def get_user_full(uid):
    conn = get_db_conn()
    c = conn.cursor()
    try:
        # L'ordre doit correspondre à ce que main.py attend :
        # 0:gen, 1:uni, 2:veo, 3:ref, 4:name, 5:energy, 6:last_upd, 7:streak, 8:staked
        c.execute("""SELECT p_genesis, p_unity, p_veo, 0, name, energy, 
                     last_energy_update, streak, 0 FROM users WHERE user_id=%s""", (uid,))
        res = c.fetchone()
        return res
    except Exception as e:
        print(f"Error get_user_full: {e}")
        return None
    finally:
        c.close()
        conn.close()




def get_community_tokens():
    conn = get_db_conn(); c = conn.cursor()
    c.execute("SELECT id, name, symbol, price, mcap FROM community_tokens ORDER BY mcap DESC")
    res = c.fetchall(); c.close(); conn.close()
    return [{"id":r[0], "name":r[1], "sym":r[2], "price":r[3], "mcap":r[4]} for r in res]
