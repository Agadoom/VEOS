import os
import psycopg2
import logging

# On récupère la variable
DATABASE_URL = os.getenv("DATABASE_URL")

# DEBUG : Ceci apparaîtra dans tes logs Railway au démarrage
print(f"--- DEBUG DATABASE ---")
print(f"URL Trouvée: {bool(DATABASE_URL)}")
if DATABASE_URL:
    print(f"Début de l'URL: {DATABASE_URL[:15]}...")

def get_db_conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    try:
        # On force sslmode=require pour les connexions externes Railway
        return psycopg2.connect(url, sslmode='require')
    except Exception as e:
        logging.error(f"Erreur PG: {e}")
        return None

def init_db():
    conn = get_db_conn()
    if not conn:
        logging.error("Échec initialisation : DATABASE_URL non accessible.")
        return
    try:
        c = conn.cursor()
        # On crée la table avec TOUTES les colonnes nécessaires
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id BIGINT PRIMARY KEY, 
                      name TEXT, 
                      p_genesis REAL DEFAULT 0, 
                      p_unity REAL DEFAULT 0, 
                      p_veo REAL DEFAULT 0, 
                      ref_count INTEGER DEFAULT 0,
                      last_daily INTEGER DEFAULT 0,
                      total_clicks INTEGER DEFAULT 0)''')
        
        # --- SÉCURITÉ : On ajoute les colonnes si elles manquent (Migration) ---
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ref_count INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_daily INTEGER DEFAULT 0")
        
        c.execute('''CREATE TABLE IF NOT EXISTS logs 
                     (id SERIAL PRIMARY KEY, user_id BIGINT, token TEXT, amount REAL, timestamp INTEGER)''')
        conn.commit()
        logging.info("✅ Base PostgreSQL mise à jour avec toutes les colonnes.")
    except Exception as e:
        logging.error(f"Erreur init_db: {e}")
    finally:
        c.close()
        conn.close()

