import psycopg2, os, time

def get_db_conn():
    # Assure-toi que DATABASE_URL est bien configurée dans tes variables d'environnement Railway
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
            logo TEXT,
            banner TEXT,
            price DOUBLE PRECISION DEFAULT 0.0001, 
            mcap DOUBLE PRECISION DEFAULT 0, 
            supply DOUBLE PRECISION DEFAULT 0,
            created_at BIGINT
        )""")

        # 3. Table Assets (Possessions des utilisateurs)
        # Utilisation de PRIMARY KEY pour gérer le ON CONFLICT plus tard
        c.execute("""CREATE TABLE IF NOT EXISTS user_community_assets (
            user_id BIGINT,
            token_id INTEGER,
            amount DOUBLE PRECISION DEFAULT 0,
            PRIMARY KEY (user_id, token_id)
        )""")

        # SÉCURITÉ : Forcer l'ajout des colonnes si la table existait déjà sans elles
        cols_to_check = [
            ("community_tokens", "logo", "TEXT"),
            ("community_tokens", "banner", "TEXT"),
            ("community_tokens", "description", "TEXT"),
            ("community_tokens", "creator_id", "BIGINT"),
            ("community_tokens", "supply", "DOUBLE PRECISION DEFAULT 0")
        ]
        for table, col, col_type in cols_to_check:
            try:
                c.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}")
            except Exception:
                pass

        conn.commit()
        print("🚀 Database structure verified and updated!")
    except Exception as e:
        print(f"❌ DB Error Init: {e}")
    finally:
        c.close(); conn.close()

# --- FONCTIONS DE RÉCUPÉRATION ---

def get_community_tokens():
    conn = get_db_conn()
    c = conn.cursor()
    try:
        # On sélectionne les noms de colonnes exacts
        c.execute("""SELECT id, name, symbol, price, mcap, logo, 
                     banner, description FROM community_tokens ORDER BY id DESC""")
        res = c.fetchall()
        return [
            {
                "id": r[0], 
                "name": r[1], 
                "symbol": r[2], 
                "price": float(r[3] or 0), 
                "mcap": float(r[4] or 0), 
                "logo": r[5] or "", 
                "banner": r[6] or "",
                "desc": r[7] or ""
            } for r in res
        ]
    except Exception as e:
        print(f"❌ Error fetching tokens: {e}")
        return []
    finally:
        c.close(); conn.close()
