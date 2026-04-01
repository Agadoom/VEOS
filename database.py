import psycopg2, os, time
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

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
            energy DOUBLE PRECISION DEFAULT 100,
            last_energy_update INTEGER,
            streak INTEGER DEFAULT 0,
            referrer_id BIGINT,
            last_login_date TEXT,
            turbo_until TIMESTAMP DEFAULT NULL,
            multiplier DOUBLE PRECISION DEFAULT 1.0,
            wallet TEXT DEFAULT NULL
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
            created_at BIGINT
        )""")

        # 3. Table Assets (Celle qui manquait !) 💎
        c.execute("""CREATE TABLE IF NOT EXISTS user_community_assets (
            user_id BIGINT,
            token_id INTEGER,
            amount DOUBLE PRECISION DEFAULT 0,
            PRIMARY KEY (user_id, token_id)
        )""")

        # 4. Table Loterie
        c.execute("""CREATE TABLE IF NOT EXISTS lottery_tickets (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            tickets_count INTEGER DEFAULT 0,
            week_number INTEGER,
            UNIQUE(user_id, week_number)
        )""")
        
        # 5. Table Stats Globales
        c.execute("""CREATE TABLE IF NOT EXISTS global_stats (
            id SERIAL PRIMARY KEY,
            total_burned NUMERIC DEFAULT 0
        )""")
        
        c.execute("INSERT INTO global_stats (id, total_burned) VALUES (1, 0) ON CONFLICT DO NOTHING")

        # Mise à jour des colonnes si déjà existantes
        c.execute("ALTER TABLE community_tokens ADD COLUMN IF NOT EXISTS logo TEXT")
        c.execute("ALTER TABLE community_tokens ADD COLUMN IF NOT EXISTS banner TEXT")

        conn.commit()
        print("✅ Database structure fully synchronized!")
    except Exception as e:
        print(f"❌ Error init_db: {e}")
    finally:
        c.close(); conn.close()

def get_user_full(uid):
    conn = get_db_conn()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT p_genesis, p_unity, p_veo, name, energy, 
                   last_energy_update, streak, referrer_id, last_login_date, multiplier 
            FROM users WHERE user_id=%s
        """, (uid,))
        return c.fetchone()
    finally:
        c.close(); conn.close()
