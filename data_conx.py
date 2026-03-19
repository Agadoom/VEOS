import os
import psycopg2
import logging

# On récupère l'URL de Railway
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_conn():
    """Établit la connexion à PostgreSQL avec SSL obligatoire pour Railway."""
    try:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    except Exception as e:
        logging.error(f"Erreur de connexion PG: {e}")
        return None

def init_db():
    """Initialise les tables PostgreSQL."""
    conn = get_db_conn()
    if not conn: return
    try:
        c = conn.cursor()
        # BIGINT est crucial pour les ID Telegram
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id BIGINT PRIMARY KEY, name TEXT, 
                      p_genesis REAL DEFAULT 0, p_unity REAL DEFAULT 0, 
                      p_veo REAL DEFAULT 0, ref_count INTEGER DEFAULT 0,
                      total_clicks INTEGER DEFAULT 0,
                      last_daily INTEGER DEFAULT 0, referred_by BIGINT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS logs 
                     (id SERIAL PRIMARY KEY, user_id BIGINT, 
                      token TEXT, amount REAL, timestamp INTEGER)''')
        conn.commit()
        logging.info("PostgreSQL Initialisé avec succès.")
    except Exception as e:
        logging.error(f"Erreur init_db: {e}")
    finally:
        c.close()
        conn.close()
