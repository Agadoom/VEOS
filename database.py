import psycopg2, os, time
from psycopg2.extras import RealDictCursor

def get_db_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db_structure():
    conn = get_db_conn()
    c = conn.cursor()
    try:
        # 1. Table Users
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            p_genesis DOUBLE PRECISION DEFAULT 0,
            p_unity DOUBLE PRECISION DEFAULT 0,
            p_veo DOUBLE PRECISION DEFAULT 0,
            energy INTEGER DEFAULT 100,
            last_energy_update INTEGER,
            streak INTEGER DEFAULT 0,
            referrer_id BIGINT,
            last_login_date TEXT
        )""")

        # 2. Table Tokens
        c.execute("""CREATE TABLE IF NOT EXISTS community_tokens (
            id SERIAL PRIMARY KEY, 
            creator_id BIGINT, 
            name TEXT NOT NULL, 
            symbol TEXT NOT NULL, 
            description TEXT,
            website_url TEXT,
            twitter_url TEXT,
            logo TEXT,
            banner TEXT,
            price DOUBLE PRECISION DEFAULT 0.0001, 
            mcap DOUBLE PRECISION DEFAULT 0, 
            supply DOUBLE PRECISION DEFAULT 0,
            created_at BIGINT
        )""")

        # 3. Table Assets
        c.execute("""CREATE TABLE IF NOT EXISTS user_community_assets (
            user_id BIGINT,
            token_id INTEGER,
            amount DOUBLE PRECISION DEFAULT 0,
            PRIMARY KEY (user_id, token_id)
        )""")

        conn.commit()
        print("🚀 Database structure verified!")
    except Exception as e:
        print(f"❌ DB Error Init: {e}")
    finally:
        c.close(); conn.close()

# --- LA FONCTION QUI MANQUAIT POUR FIXER LE PROFIL ---
def get_user_full(uid):
    conn = get_db_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT p_genesis, p_unity, p_veo, name, energy, 
                   last_energy_update, streak, referrer_id, last_login_date 
            FROM users WHERE user_id=%s
        """, (uid,))
        res = c.fetchone()
        
        if not res: 
            # Si l'user n'existe pas, on le crée
            now = int(time.time())
            c.execute("""
                INSERT INTO users (user_id, name, energy, last_energy_update, streak, p_genesis) 
                VALUES (%s, 'New Citizen', 100, %s, 0, 0)
            """, (uid, now))
            conn.commit()
            return (0.0, 0.0, 0.0, 'New Citizen', 100, now, 0, None, None)
        
        return res
    except Exception as e:
        print(f"❌ Error get_user_full: {e}")
        return None
    finally:
        c.close(); conn.close()

def get_community_tokens():
    conn = get_db_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT id, name, symbol, price, mcap, logo, banner, description, website_url, twitter_url 
            FROM community_tokens 
            ORDER BY id DESC
        """)
        res = c.fetchall()
        return [
            {
                "id": r[0], "name": r[1], "symbol": r[2], 
                "price": float(r[3] or 0.0001), "mcap": float(r[4] or 0), 
                "logo": r[5] or "", "banner": r[6] or "",
                "description": r[7] or "No description provided.",
                "website": r[8] or "", "twitter": r[9] or ""
            } for r in res
        ]
    except Exception as e:
        print(f"❌ Error fetching tokens: {e}")
        return []
    finally:
        c.close(); conn.close()



def get_energy_recharge_rate(user_id):
    conn = get_db_conn()
    c = conn.cursor()
    try:
        # On vérifie si le Turbo est encore actif
        c.execute("SELECT turbo_until FROM users WHERE user_id = %s", (user_id,))
        res = c.fetchone()
        
        import datetime
        now = datetime.datetime.now()
        
        # Si turbo_until existe et n'est pas encore passé
        if res and res[0] and res[0] > now:
            return 3.0  # Vitesse x3 🚀
        else:
            return 1.0  # Vitesse normale
    finally:
        c.close(); conn.close()
