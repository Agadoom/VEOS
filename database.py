import psycopg2, os, time
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

def get_db_conn():
    # Connexion à PostgreSQL via l'URL Railway
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db_structure():
    conn = get_db_conn()
    c = conn.cursor()
    try:
        # 1. Table Users (La base de ton empire) 🛰️
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            p_genesis DOUBLE PRECISION DEFAULT 0,
            p_unity DOUBLE PRECISION DEFAULT 0,
            p_veo DOUBLE PRECISION DEFAULT 0,
            energy DOUBLE PRECISION DEFAULT 100,
            last_energy_update INTEGER,
            streak INTEGER DEFAULT 0,
            referrer_id BIGINT,
            last_login_date TEXT,
            turbo_until TIMESTAMP DEFAULT NULL,
            multiplier DOUBLE PRECISION DEFAULT 1.0,
            wallet TEXT DEFAULT NULL
        )""")

        # --- 🚀 FIX CRITIQUE : AJOUT DES COLONNES MANQUANTES ---
        # Si la table existe déjà, on force l'ajout des nouvelles colonnes
        cols_to_add = [
            ("turbo_until", "TIMESTAMP DEFAULT NULL"),
            ("multiplier", "DOUBLE PRECISION DEFAULT 1.0"),
            ("last_login_date", "TEXT"),
            ("wallet", "TEXT")
        ]
        
        for col_name, col_type in cols_to_add:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            except Exception as e:
                print(f"ℹ️ Info: Column {col_name} check: {e}")

        # 2. Table Tokens (Pour ton Launchpad)
        c.execute("""CREATE TABLE IF NOT EXISTS community_tokens (
            id SERIAL PRIMARY KEY, 
            creator_id BIGINT, 
            name TEXT NOT NULL, 
            symbol TEXT NOT NULL, 
            price DOUBLE PRECISION DEFAULT 0.0001, 
            mcap DOUBLE PRECISION DEFAULT 0, 
            created_at BIGINT
        )""")

        # 3. Table Loterie (Tickets) 🎟️
        c.execute("""CREATE TABLE IF NOT EXISTS lottery_tickets (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            tickets_count INTEGER DEFAULT 0,
            week_number INTEGER,
            UNIQUE(user_id, week_number)
        )""")
        
        # 4. Table Stats Globales (Burn 🔥)
        c.execute("""CREATE TABLE IF NOT EXISTS global_stats (
            id SERIAL PRIMARY KEY,
            total_burned NUMERIC DEFAULT 0
        )""")
        
        c.execute("INSERT INTO global_stats (id, total_burned) VALUES (1, 0) ON CONFLICT DO NOTHING")

        conn.commit()
        print("✅ Database structure synchronized with Multiplier & Turbo!")
    except Exception as e:
        print(f"❌ Error init_db: {e}")
    finally:
        c.close(); conn.close()

def get_user_full(uid):
    conn = get_db_conn()
    c = conn.cursor()
    try:
        # On récupère les colonnes dans l'ordre pour ton API
        c.execute("""
            SELECT p_genesis, p_unity, p_veo, name, energy, 
                   last_energy_update, streak, referrer_id, last_login_date, multiplier 
            FROM users WHERE user_id=%s
        """, (uid,))
        res = c.fetchone()
        
        if not res: 
            now = int(time.time())
            c.execute("""
                INSERT INTO users (user_id, name, energy, last_energy_update, streak, p_genesis, multiplier) 
                VALUES (%s, 'New Citizen', 100, %s, 0, 0, 1.0)
            """, (uid, now))
            conn.commit()
            return (0.0, 0.0, 0.0, 'New Citizen', 100.0, now, 0, None, None, 1.0)
        
        return res
    except Exception as e:
        print(f"❌ Error get_user_full: {e}")
        return None
    finally:
        c.close(); conn.close()
