import os
import psycopg2
import logging

# On récupère la variable
DATABASE_URL = os.getenv("DATABASE_URL")

# DEBUG : Ceci apparaîtra dans tes logs Railway au démarrage
print(f"--- DEBUG DATABASE ---")
if DATABASE_URL:
    print(f"URL Trouvée: Oui (Début: {DATABASE_URL[:15]}...)")
else:
    print("URL Trouvée: NON (Vérifie tes variables Railway)")

def get_db_conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    try:
        # On force sslmode=require pour les connexions externes Railway
        return psycopg2.connect(url, sslmode='require')
    except Exception as e:
        logging.error(f"Erreur PG Connection: {e}")
        return None

def init_db():
    conn = get_db_conn()
    if not conn:
        logging.error("Échec initialisation : DATABASE_URL non accessible.")
        return
    try:
        c = conn.cursor()
        
        # 1. Création de la table USERS avec la colonne referred_by
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id BIGINT PRIMARY KEY, 
                      name TEXT, 
                      p_genesis REAL DEFAULT 0, 
                      p_unity REAL DEFAULT 0, 
                      p_veo REAL DEFAULT 0, 
                      ref_count INTEGER DEFAULT 0,
                      last_daily INTEGER DEFAULT 0,
                      total_clicks INTEGER DEFAULT 0,
                      referred_by BIGINT)''')
        
        # 2. MIGRATIONS : On ajoute les colonnes si elles manquent sur une base déjà existante
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ref_count INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_daily INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_clicks INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by BIGINT") # <-- AJOUT ICI
# Dans init_db(), ajoutez cette ligne dans la section MIGRATIONS
c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS wallet_address TEXT")

        
        # 3. Création de la table LOGS
        c.execute('''CREATE TABLE IF NOT EXISTS logs 
                     (id SERIAL PRIMARY KEY, 
                      user_id BIGINT, 
                      token TEXT, 
                      amount REAL, 
                      timestamp INTEGER)''')
        
        conn.commit()
        logging.info("✅ Base PostgreSQL mise à jour (Colonnes : OK, Parrainage : OK)")
        
    except Exception as e:
        logging.error(f"Erreur init_db: {e}")
    finally:
        if conn:
            c.close()
            conn.close()
