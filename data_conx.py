import os
import psycopg2
import logging

# On récupère l'URL injectée par Railway
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_conn():
    """Établit la connexion à PostgreSQL."""
    if not DATABASE_URL:
        logging.error("DATABASE_URL est manquante dans les variables Railway !")
        return None
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    """Initialise les tables si elles n'existent pas."""
    conn = get_db_conn()
    if conn:
        try:
            c = conn.cursor()
            # Table des utilisateurs
            c.execute('''CREATE TABLE IF NOT EXISTS users 
                         (user_id BIGINT PRIMARY KEY, name TEXT, 
                          p_genesis REAL DEFAULT 0, p_unity REAL DEFAULT 0, 
                          p_veo REAL DEFAULT 0, ref_count INTEGER DEFAULT 0,
                          total_clicks INTEGER DEFAULT 0)''')
            # Table des logs de transaction
            c.execute('''CREATE TABLE IF NOT EXISTS logs 
                         (id SERIAL PRIMARY KEY, user_id BIGINT, 
                          token TEXT, amount REAL, timestamp INTEGER)''')
            conn.commit()
            logging.info("Base de données PostgreSQL initialisée.")
        except Exception as e:
            logging.error(f"Erreur d'initialisation : {e}")
        finally:
            conn.close()
