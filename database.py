import psycopg2, os, time
from psycopg2.extras import RealDictCursor

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

        # 2. Table Tokens (Mise à jour avec les nouveaux champs)
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

        # --- SÉCURITÉ CRITIQUE : AJOUT DES COLONNES MANQUANTES ---
        # Si la table existait déjà, ces colonnes n'y sont pas. On les force ici.
        columns = [
            ("community_tokens", "description", "TEXT"),
            ("community_tokens", "website_url", "TEXT"),
            ("community_tokens", "twitter_url", "TEXT"),
            ("community_tokens", "logo", "TEXT"),
            ("community_tokens", "banner", "TEXT"),
            ("community_tokens", "creator_id", "BIGINT"),
            ("community_tokens", "supply", "DOUBLE PRECISION DEFAULT 0")
        ]
        
        for table, col, col_type in columns:
            try:
                c.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}")
            except Exception as e:
                print(f"Info: Colonne {col} déjà présente ou erreur mineure.")

        conn.commit()
        print("🚀 Database structure verified and updated with social links!")
    except Exception as e:
        print(f"❌ DB Error Init: {e}")
    finally:
        c.close(); conn.close()

def get_community_tokens():
    conn = get_db_conn()
    c = conn.cursor()
    try:
        # On sélectionne EXACTEMENT ce que list_tokens attend
        c.execute("""
            SELECT id, name, symbol, price, mcap, logo, banner, description, website_url, twitter_url 
            FROM community_tokens 
            ORDER BY id DESC
        """)
        res = c.fetchall()
        return [
            {
                "id": r[0], 
                "name": r[1], 
                "symbol": r[2], 
                "price": float(r[3] or 0.0001), 
                "mcap": float(r[4] or 0), 
                "logo": r[5] or "", 
                "banner": r[6] or "",
                "description": r[7] or "No description provided.",
                "website": r[8] or "",
                "twitter": r[9] or ""
            } for r in res
        ]
    except Exception as e:
        print(f"❌ Error fetching tokens: {e}")
        return []
    finally:
        c.close(); conn.close()
