import os
import psycopg2
import logging
import time

# Récupération de l'URL (Assure-toi de coller l'URL publique en texte brut sur Railway)
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_conn():
    """Établit la connexion à PostgreSQL avec gestion d'erreurs."""
    if not DATABASE_URL:
        logging.error("DATABASE_URL est absente des variables d'environnement !")
        return None
    
    try:
        # sslmode='require' est obligatoire pour les connexions Railway hors réseau interne
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        logging.error(f"Erreur de connexion PG: {e}")
        return None

def init_db():
    """Initialise les tables si elles n'existent pas au démarrage."""
    # On attend 2 secondes pour laisser le temps à la base de respirer au reboot
    time.sleep(2)
    
    conn = get_db_conn()
    if not conn:
        logging.error("Impossible d'initialiser la base : connexion échouée.")
        return

    try:
        c = conn.cursor()
        
        # Table Users (Note l'utilisation de BIGINT pour les ID Telegram)
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id BIGINT PRIMARY KEY, 
                      name TEXT, 
                      p_genesis REAL DEFAULT 0, 
                      p_unity REAL DEFAULT 0, 
                      p_veo REAL DEFAULT 0, 
                      ref_count INTEGER DEFAULT 0,
                      total_clicks INTEGER DEFAULT 0,
                      last_daily INTEGER DEFAULT 0, 
                      referred_by BIGINT)''')
        
        # Table Logs (SERIAL permet l'auto-incrémentation sur Postgres)
        c.execute('''CREATE TABLE IF NOT EXISTS logs 
                     (id SERIAL PRIMARY KEY, 
                      user_id BIGINT, 
                      token TEXT, 
                      amount REAL, 
                      timestamp INTEGER)''')
        
        conn.commit()
        logging.info("✅ PostgreSQL Initialisé : Tables créées ou déjà présentes.")
    except Exception as e:
        logging.error(f"Erreur lors du CREATE TABLE : {e}")
    finally:
        c.close()
        conn.close()
