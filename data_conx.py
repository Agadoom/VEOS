import os
import psycopg2
import logging

# Config des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    try:
        return psycopg2.connect(url, sslmode='require')
    except Exception as e:
        logger.error(f"DB Connection Error: {e}")
        return None

def init_db():
    conn = get_db_conn()
    if not conn:
        logger.error("Could not connect to DB for init.")
        return
    try:
        c = conn.cursor()
        
        # Création de la table principale
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id BIGINT PRIMARY KEY, 
                      name TEXT, 
                      p_genesis REAL DEFAULT 0, 
                      p_unity REAL DEFAULT 0, 
                      p_veo REAL DEFAULT 0, 
                      ref_count INTEGER DEFAULT 0,
                      last_daily INTEGER DEFAULT 0,
                      referred_by BIGINT,
                      energy INTEGER DEFAULT 100,
                      last_energy_update INTEGER,
                      staked_amount DOUBLE PRECISION DEFAULT 0,
                      streak INTEGER DEFAULT 0,
                      last_streak_date TEXT,
                      wallet_address TEXT)''')
        
        # Migration automatique (ajoute les colonnes si elles manquent)
        cols_to_check = [
            ("energy", "INTEGER DEFAULT 100"),
            ("last_energy_update", "INTEGER"),
            ("staked_amount", "DOUBLE PRECISION DEFAULT 0"),
            ("streak", "INTEGER DEFAULT 0"),
            ("last_streak_date", "TEXT"),
            ("wallet_address", "TEXT"),
            ("referred_by", "BIGINT")
        ]
        
        for col, dtype in cols_to_check:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            except:
                pass # La colonne existe déjà
        
        conn.commit()
        logger.info("✅ Database Synchronized Successfully.")
    except Exception as e:
        logger.error(f"Init DB Error: {e}")
    finally:
        if conn:
            c.close()
            conn.close()
